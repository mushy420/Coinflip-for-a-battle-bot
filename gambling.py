import discord
from discord.ext import commands
import random
import asyncio
from typing import Optional, Union, Literal
from discord import ButtonStyle, Interaction
from discord.ui import Button, View

class CoinflipButton(Button):
    def __init__(self, choice: str, bet_amount: int, user_id: int, emoji: str):
        super().__init__(
            style=ButtonStyle.primary if choice == "heads" else ButtonStyle.danger,
            label=choice.capitalize(),
            emoji=emoji,
            custom_id=f"coinflip_{choice}_{bet_amount}"
        )
        self.choice = choice
        self.bet_amount = bet_amount
        self.user_id = user_id
        
    async def callback(self, interaction: Interaction):
        # Only the original user can use the button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        # Disable all buttons in the view
        for item in self.view.children:
            item.disabled = True
        
        # Get the bot instance
        bot = interaction.client
        
        try:
            # Get user's current balance
            user_balance = await bot.get_cog("Economy").get_balance(self.user_id)
            
            # Check if user has enough money
            if self.bet_amount > user_balance:
                await interaction.response.edit_message(
                    content=f"You don't have enough yen! Your balance: {user_balance} yen",
                    view=self.view
                )
                return
                
            # Respond to show we're flipping
            await interaction.response.edit_message(
                content=f"Flipping coin... {interaction.user.mention} bet **{self.bet_amount} yen** on **{self.choice}**",
                view=self.view
            )
            
            # Artificial delay for suspense
            await asyncio.sleep(2)
            
            # Determine the result
            result = random.choice(["heads", "tails"])
            
            # Check if the user won
            won = (self.choice == result)
            
            # Calculate winnings/losses
            if won:
                winnings = self.bet_amount
                await bot.get_cog("Economy").update_balance(self.user_id, winnings)
                result_text = f"**YOU WON {winnings} yen!** 🎉"
                color = discord.Color.green()
            else:
                loss = -self.bet_amount
                await bot.get_cog("Economy").update_balance(self.user_id, loss)
                result_text = f"**YOU LOST {self.bet_amount} yen!** 😭"
                color = discord.Color.red()
                
            # Get updated balance
            new_balance = await bot.get_cog("Economy").get_balance(self.user_id)
            
            # Create result embed
            embed = discord.Embed(
                title=f"🎲 Coin Flip Result: **{result.upper()}** 🎲",
                description=f"{interaction.user.mention} bet **{self.bet_amount} yen** on **{self.choice}**",
                color=color
            )
            embed.add_field(name="Result", value=result_text, inline=False)
            embed.add_field(name="New Balance", value=f"{new_balance} yen", inline=False)
            
            # Add a gif or image based on result
            if result == "heads":
                embed.set_thumbnail(url="https://i.imgur.com/HavOS7J.gif")
            else:
                embed.set_thumbnail(url="https://i.imgur.com/XnAHCmz.gif")
                
            # Add play again button
            play_again_view = CoinflipAgainView(self.bet_amount, interaction.user.id)
            
            await interaction.edit_original_response(content=None, embed=embed, view=play_again_view)
            
        except Exception as e:
            # Log the error
            print(f"Error in coinflip button callback: {e}")
            await interaction.edit_original_response(content=f"An error occurred: {str(e)}", view=None)

class CoinflipAgainView(View):
    def __init__(self, bet_amount: int, user_id: int):
        super().__init__(timeout=60)
        self.bet_amount = bet_amount
        self.user_id = user_id
        self.add_item(Button(
            style=ButtonStyle.success,
            label="Play Again",
            emoji="🔄",
            custom_id=f"coinflip_again_{bet_amount}"
        ))
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

class CoinflipView(View):
    def __init__(self, bet_amount: int, user_id: int):
        super().__init__(timeout=30)
        # Add heads button
        self.add_item(CoinflipButton("heads", bet_amount, user_id, "🪙"))
        # Add tails button
        self.add_item(CoinflipButton("tails", bet_amount, user_id, "💰"))

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = set()  # To prevent users from having multiple games at once
        
        # Register the button handler
        bot.add_listener(self.on_button_click, "on_interaction")
    
    async def on_button_click(self, interaction: Interaction):
        if not interaction.data or not interaction.data.get("custom_id"):
            return
            
        custom_id = interaction.data["custom_id"]
        
        # Handle "Play Again" button
        if custom_id.startswith("coinflip_again_"):
            try:
                bet_amount = int(custom_id.split("_")[-1])
                
                # Create new coinflip view
                view = CoinflipView(bet_amount, interaction.user.id)
                
                # Show new game options
                await interaction.response.edit_message(
                    content=f"Choose heads or tails! Betting {bet_amount} yen...",
                    embed=None,
                    view=view
                )
            except Exception as e:
                print(f"Error handling play again button: {e}")
                await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @commands.command(name="cf", aliases=["coinflip"])
    async def coinflip(self, ctx, amount: str, choice: Optional[str] = None):
        """
        Flip a coin to win or lose yen
        Usage: !cf <amount> [heads/tails]
        If you don't specify heads/tails, you'll get buttons to choose.
        Aliases: !coinflip
        """
        user_id = ctx.author.id
        
        # Check if user already has an ongoing game
        if user_id in self.ongoing_games:
            await ctx.send("You already have an ongoing game!")
            return
            
        # Process and validate the bet amount
        try:
            # Handle 'all' as a special case
            if amount.lower() == "all":
                user_balance = await self.bot.get_cog("Economy").get_balance(user_id)
                bet_amount = user_balance
            else:
                bet_amount = int(amount)
        except ValueError:
            await ctx.send("Please enter a valid amount to bet!")
            return
            
        # Validate the bet amount
        if bet_amount <= 0:
            await ctx.send("You can't bet zero or negative yen!")
            return
            
        # Get user's current balance
        user_balance = await self.bot.get_cog("Economy").get_balance(user_id)
        
        # Check if user has enough money
        if bet_amount > user_balance:
            await ctx.send(f"You don't have enough yen! Your balance: {user_balance} yen")
            return
            
        # Mark user as having an ongoing game
        self.ongoing_games.add(user_id)
        
        try:
            # If choice is provided, proceed with the old method
            if choice:
                # Normalize the choice input
                choice = choice.lower()
                if choice in ["h", "head", "heads"]:
                    choice = "heads"
                elif choice in ["t", "tail", "tails"]:
                    choice = "tails"
                else:
                    await ctx.send("Please choose either 'heads' or 'tails'!")
                    self.ongoing_games.remove(user_id)
                    return
                    
                # Create the initial embed
                embed = discord.Embed(
                    title="🎲 Coin Flip Gambling 🎲",
                    description=f"{ctx.author.mention} bet **{bet_amount} yen** on **{choice}**",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Flipping coin...", value="Good luck!", inline=False)
                message = await ctx.send(embed=embed)
                
                # Simulate coin flip with suspense
                await asyncio.sleep(2)
                
                # Determine the result
                result = random.choice(["heads", "tails"])
                
                # Check if the user won
                won = (choice == result)
                
                # Calculate winnings/losses
                if won:
                    winnings = bet_amount
                    await self.bot.get_cog("Economy").update_balance(user_id, winnings)
                    result_text = f"**YOU WON {winnings} yen!** 🎉"
                    color = discord.Color.green()
                else:
                    loss = -bet_amount
                    await self.bot.get_cog("Economy").update_balance(user_id, loss)
                    result_text = f"**YOU LOST {bet_amount} yen!** 😭"
                    color = discord.Color.red()
                    
                # Get updated balance
                new_balance = await self.bot.get_cog("Economy").get_balance(user_id)
                
                # Update the embed with results
                embed = discord.Embed(
                    title=f"🎲 Coin Flip Result: **{result.upper()}** 🎲",
                    description=f"{ctx.author.mention} bet **{bet_amount} yen** on **{choice}**",
                    color=color
                )
                embed.add_field(name="Result", value=result_text, inline=False)
                embed.add_field(name="New Balance", value=f"{new_balance} yen", inline=False)
                
                # Add a gif based on result
                if result == "heads":
                    embed.set_thumbnail(url="https://i.imgur.com/HavOS7J.gif")
                else:
                    embed.set_thumbnail(url="https://i.imgur.com/XnAHCmz.gif")
                
                # Add play again button
                play_again_view = CoinflipAgainView(bet_amount, user_id)
                
                await message.edit(embed=embed, view=play_again_view)
            else:
                # Create the button view
                view = CoinflipView(bet_amount, user_id)
                
                # Send a message with buttons
                await ctx.send(
                    f"{ctx.author.mention}, you're betting **{bet_amount} yen**. Choose heads or tails!",
                    view=view
                )
        except Exception as e:
            # Log and display the error
            print(f"Error in coinflip command: {e}")
            await ctx.send(f"An error occurred: {str(e)}")
        finally:
            # Always remove user from ongoing games set when done
            self.ongoing_games.remove(user_id)

async def setup(bot):
    await bot.add_cog(Gambling(bot))

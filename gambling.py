"""
Gambling module for Discord bot with coinflip functionality.
Uses MongoDB for data storage and wallet.py for economy management.
"""
import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from typing import Optional
from discord import ButtonStyle, Interaction, SelectOption
from discord.ui import Button, View, Modal, TextInput

import wallet  # Import wallet.py for economy management
import motor.motor_asyncio
from pymongo import MongoClient

# ---------- CONFIGURABLE SETTINGS ----------
# MongoDB connection URI - replace with your MongoDB connection string
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "discord_bot"
COLLECTION_NAME = "gambling_stats"

# Coinflip settings
DEFAULT_TIMEOUT = 60  # Seconds for button timeout
WIN_MULTIPLIER = 2.0  # Amount multiplier when user wins (2.0 = double)
HEADS_GIF_URL = "https://i.imgur.com/HavOS7J.gif"  # GIF for heads result
TAILS_GIF_URL = "https://i.imgur.com/XnAHCmz.gif"  # GIF for tails result
# -------------------------------------------

# Initialize MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]
gambling_stats = db[COLLECTION_NAME]

class AmountModal(Modal, title="Bet Amount"):
    """Modal for entering bet amount"""
    
    amount_input = TextInput(
        label="Enter amount to bet",
        placeholder="Enter a number",
        required=True,
        min_length=1,
        max_length=10
    )
    
    def __init__(self, choice: str, user_id: int):
        super().__init__(timeout=DEFAULT_TIMEOUT)
        self.choice = choice  # 'heads' or 'tails'
        self.user_id = user_id
    
    async def on_submit(self, interaction: Interaction):
        try:
            # Validate the amount
            bet_amount = int(self.amount_input.value)
            if bet_amount <= 0:
                await interaction.response.send_message("You can't bet zero or negative amounts!", ephemeral=True)
                return
            
            # Check if user has sufficient balance
            balance = await wallet.get_balance(self.user_id)
            if bet_amount > balance:
                await interaction.response.send_message(f"You don't have enough money! Your balance: {balance}", ephemeral=True)
                return
                
            # Start the coinflip game
            await interaction.response.defer()
            await process_coinflip(interaction, self.choice, bet_amount)
            
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)
        except Exception as e:
            print(f"Error in amount modal: {e}")
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

class CoinflipView(View):
    """View with heads and tails buttons"""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=DEFAULT_TIMEOUT)
        self.user_id = user_id
        
        # Add heads button
        heads_button = Button(
            style=ButtonStyle.primary, 
            label="Heads",
            emoji="🪙",
            custom_id="coinflip_heads"
        )
        heads_button.callback = self.heads_callback
        self.add_item(heads_button)
        
        # Add tails button
        tails_button = Button(
            style=ButtonStyle.success, 
            label="Tails",
            emoji="💰",
            custom_id="coinflip_tails"
        )
        tails_button.callback = self.tails_callback
        self.add_item(tails_button)
    
    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure only the original user can use the buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True
        
    async def heads_callback(self, interaction: Interaction):
        """Handle heads button click"""
        await interaction.response.send_modal(AmountModal("heads", self.user_id))
    
    async def tails_callback(self, interaction: Interaction):
        """Handle tails button click"""
        await interaction.response.send_modal(AmountModal("tails", self.user_id))

async def process_coinflip(interaction: Interaction, choice: str, bet_amount: int):
    """Process the coinflip game logic"""
    user_id = interaction.user.id
    
    try:
        # Create initial embed
        embed = discord.Embed(
            title="🎲 Coin Flip Gambling 🎲",
            description=f"{interaction.user.mention} bet **{bet_amount}** on **{choice}**",
            color=discord.Color.gold()
        )
        embed.add_field(name="Flipping coin...", value="Good luck!", inline=False)
        await interaction.followup.send(embed=embed)
        
        # Artificial delay for suspense
        await asyncio.sleep(2)
        
        # Determine the result (50/50 chance)
        result = random.choice(["heads", "tails"])
        
        # Check if the user won
        won = (choice == result)
        
        # Calculate winnings/losses and update balance
        if won:
            winnings = int(bet_amount * WIN_MULTIPLIER)
            new_balance = await wallet.add_money(user_id, winnings - bet_amount)  # Subtract bet amount since we're adding the winnings
            result_text = f"**YOU WON {winnings}!** 🎉"
            color = discord.Color.green()
        else:
            await wallet.remove_money(user_id, bet_amount)
            new_balance = await wallet.get_balance(user_id)
            result_text = f"**YOU LOST {bet_amount}!** 😭"
            color = discord.Color.red()
        
        # Update gambling stats in database
        await update_gambling_stats(user_id, won, bet_amount)
        
        # Create result embed
        embed = discord.Embed(
            title=f"🎲 Coin Flip Result: **{result.upper()}** 🎲",
            description=f"{interaction.user.mention} bet **{bet_amount}** on **{choice}**",
            color=color
        )
        embed.add_field(name="Result", value=result_text, inline=False)
        embed.add_field(name="New Balance", value=f"{new_balance}", inline=False)
        
        # Add a gif based on result
        if result == "heads":
            embed.set_thumbnail(url=HEADS_GIF_URL)
        else:
            embed.set_thumbnail(url=TAILS_GIF_URL)
        
        # Create Play Again button
        view = View(timeout=DEFAULT_TIMEOUT)
        play_again = Button(
            style=ButtonStyle.secondary,
            label="Play Again",
            emoji="🔄",
            custom_id=f"coinflip_again_{interaction.user.id}"
        )
        
        async def play_again_callback(interaction: Interaction):
            if interaction.user.id != user_id:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
            
            # Start a new game
            new_view = CoinflipView(user_id)
            await interaction.response.send_message(
                f"{interaction.user.mention}, choose heads or tails!",
                view=new_view
            )
            
        play_again.callback = play_again_callback
        view.add_item(play_again)
        
        # Send the result
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        print(f"Error in coinflip game: {e}")
        await interaction.followup.send(f"An error occurred: {str(e)}")

async def update_gambling_stats(user_id: int, won: bool, amount: int):
    """Update gambling statistics in MongoDB"""
    try:
        # Find user stats document
        stats = await gambling_stats.find_one({"user_id": user_id})
        
        if stats:
            # Update existing stats
            update_data = {
                "$inc": {
                    "total_games": 1,
                    "wins": 1 if won else 0,
                    "losses": 0 if won else 1,
                    "total_bet": amount,
                    "total_won": amount * WIN_MULTIPLIER if won else 0,
                    "total_lost": 0 if won else amount
                }
            }
            await gambling_stats.update_one({"user_id": user_id}, update_data)
        else:
            # Create new stats document
            new_stats = {
                "user_id": user_id,
                "total_games": 1,
                "wins": 1 if won else 0,
                "losses": 0 if won else 1,
                "total_bet": amount,
                "total_won": amount * WIN_MULTIPLIER if won else 0,
                "total_lost": 0 if won else amount
            }
            await gambling_stats.insert_one(new_stats)
    except Exception as e:
        print(f"Error updating gambling stats: {e}")

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = set()  # Track ongoing games
    
    @commands.hybrid_command(name="cf", aliases=["coinflip"])
    async def coinflip(self, ctx):
        """
        Start a coinflip gambling game
        Usage: /cf or !cf
        """
        user_id = ctx.author.id
        
        # Check if user already has an ongoing game
        if user_id in self.ongoing_games:
            await ctx.send("You already have an ongoing game!")
            return
            
        # Mark user as having an ongoing game
        self.ongoing_games.add(user_id)
        
        try:
            # Create view with heads and tails buttons
            view = CoinflipView(user_id)
            
            # Send message with buttons
            await ctx.send(
                f"{ctx.author.mention}, choose heads or tails!",
                view=view
            )
        except Exception as e:
            print(f"Error in coinflip command: {e}")
            await ctx.send(f"An error occurred: {str(e)}")
        finally:
            # Remove user from ongoing games when finished
            self.ongoing_games.remove(user_id)
    
    @commands.hybrid_command(name="gambling_stats")
    async def gambling_stats(self, ctx, user: Optional[discord.Member] = None):
        """
        View gambling statistics
        Usage: /gambling_stats or !gambling_stats [user]
        """
        target_user = user or ctx.author
        user_id = target_user.id
        
        try:
            # Get user stats from database
            stats = await gambling_stats.find_one({"user_id": user_id})
            
            if not stats:
                await ctx.send(f"{target_user.mention} hasn't played any gambling games yet!")
                return
                
            # Create stats embed
            embed = discord.Embed(
                title=f"🎲 Gambling Statistics for {target_user.display_name}",
                color=discord.Color.blue()
            )
            
            # Add stats to embed
            embed.add_field(name="Total Games", value=str(stats.get("total_games", 0)), inline=True)
            embed.add_field(name="Wins", value=str(stats.get("wins", 0)), inline=True)
            embed.add_field(name="Losses", value=str(stats.get("losses", 0)), inline=True)
            
            win_rate = stats.get("wins", 0) / stats.get("total_games", 1) * 100
            embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)
            
            embed.add_field(name="Total Bet", value=str(stats.get("total_bet", 0)), inline=True)
            embed.add_field(name="Total Won", value=str(stats.get("total_won", 0)), inline=True)
            embed.add_field(name="Total Lost", value=str(stats.get("total_lost", 0)), inline=True)
            
            # Calculate profit/loss
            profit = stats.get("total_won", 0) - stats.get("total_lost", 0)
            embed.add_field(
                name="Profit/Loss", 
                value=f"**+{profit}** 📈" if profit >= 0 else f"**{profit}** 📉", 
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"Error fetching gambling stats: {e}")
            await ctx.send(f"An error occurred: {str(e)}")

async def setup(bot):
    await bot.add_cog(Gambling(bot))

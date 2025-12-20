from discord.ext import commands
import discord

class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        await self.bot.process_commands(message)

async def setup(bot):
    await bot.add_cog(Core(bot))

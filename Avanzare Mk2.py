import threading
import discord
from discord.ext import commands
from flask import Flask

from bot.config import BOT_TOKEN

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"ログイン完了: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="/help でコマンド確認"))

# Cogs 読み込み
COGS = [
    "bot.cogs.invite_watch",
    "bot.cogs.auth",
    "bot.cogs.ticket",
    "bot.cogs.role_panel",
    "bot.cogs.global_chat",
    "bot.cogs.help",
]

async def load_cogs():
    for c in COGS:
        await bot.load_extension(c)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.loop.create_task(load_cogs())
    bot.run(BOT_TOKEN)

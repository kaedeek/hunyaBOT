import threading
import os
import discord
from discord.ext import commands
from flask import Flask, request
import json

from bot.config import BOT_TOKEN
from bot.cogs.auth import AuthCog

# ===============================
# Flask（OAuth callback用）
# ===============================
app = Flask(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
AUTH_CODES_PATH = os.path.join(DATA_DIR, "auth_codes.json")

# 認証コード読み込み
try:
    with open(AUTH_CODES_PATH, "r", encoding="utf-8") as f:
        auth_codes = json.load(f)
except:
    auth_codes = {}

def save_auth_codes():
    with open(AUTH_CODES_PATH, "w", encoding="utf-8") as f:
        json.dump(auth_codes, f, indent=2, ensure_ascii=False)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")  # user_id

    if not code or not state:
        return "❌ 認証に失敗しました"

    auth_codes[state] = code
    save_auth_codes()

    return "✅ 認証完了しました。Discordに戻ってください。"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )

# ===============================
# Discord Bot
# ===============================
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# Flaskを別スレッドで起動
threading.Thread(target=run_flask, daemon=True).start()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Render / Replit の公開URL
    redirect_base_url = os.environ.get("REDIRECT_URI")
    if not redirect_base_url:
        raise RuntimeError("REDIRECT_URI が設定されていません")

    # Cog登録
    await bot.add_cog(AuthCog(bot, redirect_base_url))

    # スラッシュ / ハイブリッド同期
    await bot.tree.sync()

    print("✅ Commands synced")

# ===============================
# 起動
# ===============================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN が設定されていません")

    bot.run(BOT_TOKEN)

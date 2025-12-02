"""
フニャBOT 完全統合版（グローバルチャット + ロールパネル + 統計）
要: python, discord.py v2.x, pillow
Replit: pip install pillow
"""
import os, json, asyncio, threading, io
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from flask import Flask
import discord
from discord.ext import commands, tasks
from discord import app_commands

# Pillow import
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# ----------------------------
# Intents & Bot
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# データファイル
# ----------------------------
DATA_FILE = "global_chat_data.json"
ROLE_PANEL_FILE = "role_panels.json"
STATS_FILE = "stats_data.json"

data: Dict[str, Any] = {"global_channels": {}, "global_mute": {}, "global_ban": []}
role_panels: Dict[str, Any] = {}
stats_data: Dict[str, Any] = {"daily_messages": {}, "stats_channel_id": {}, "last_stats_message": {}}

# ----------------------------
# ファイル I/O
# ----------------------------
def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def load_all_data():
    global data, role_panels, stats_data
    data = load_json(DATA_FILE, data)
    role_panels = load_json(ROLE_PANEL_FILE, role_panels)
    stats_data = load_json(STATS_FILE, stats_data)
    stats_data.setdefault("daily_messages", {})
    stats_data.setdefault("stats_channel_id", {})
    stats_data.setdefault("last_stats_message", {})

def save_all_data():
    save_json(DATA_FILE, data)
    save_json(ROLE_PANEL_FILE, role_panels)
    save_json(STATS_FILE, stats_data)

load_all_data()

# ----------------------------
# ユーティリティ
# ----------------------------
async def safe_call(coro, delay=0.2):
    while True:
        try:
            res = await coro
            await asyncio.sleep(delay)
            return res
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                await asyncio.sleep(getattr(e, "retry_after", 1))
            elif getattr(e, "status", None) == 404:
                return None
            else:
                raise

def is_text_sendable(ch):
    return isinstance(ch, (discord.TextChannel, discord.Thread))

def is_messageable(ch):
    return isinstance(ch, (discord.abc.Messageable, discord.TextChannel, discord.Thread))

# ----------------------------
# グローバルチャット転送
# ----------------------------
async def broadcast_global_message(channel, author, content, attachments):
    try:
        guild_id = str(channel.guild.id)
    except Exception:
        return
    for g_name, ch_list in data.get("global_channels", {}).items():
        if f"{guild_id}:{channel.id}" in ch_list:
            for target in list(ch_list):
                try:
                    tgt_guild_id, tgt_ch_id = map(int, target.split(":"))
                except Exception:
                    continue
                if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                    continue
                tgt_guild = bot.get_guild(tgt_guild_id)
                if not tgt_guild:
                    continue
                tgt_channel = tgt_guild.get_channel(tgt_ch_id)
                if not tgt_channel:
                    continue
                # mute/ban
                if str(author.id) in data.get("global_ban", []):
                    continue
                if g_name in data.get("global_mute", {}) and str(author.id) in data["global_mute"].get(g_name, []):
                    continue
                try:
                    if not is_text_sendable(tgt_channel):
                        continue
                    embed = discord.Embed(description=content or "(添付のみ)", color=discord.Color.blue())
                    embed.set_author(name=f"{author.display_name}@{channel.guild.name}", icon_url=author.display_avatar.url)
                    await safe_call(tgt_channel.send(embed=embed))
                    for a in attachments:
                        await safe_call(tgt_channel.send(a.url))
                except Exception:
                    continue

# ----------------------------
# メッセージカウント
# ----------------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    if message.guild:
        guild_id_str = str(message.guild.id)
        date_str = message.created_at.astimezone(timezone.utc).date().isoformat()
        guild_daily = stats_data["daily_messages"].setdefault(guild_id_str, {})
        guild_daily[date_str] = guild_daily.get(date_str, 0) + 1
        stats_data["daily_messages"][guild_id_str] = guild_daily
        save_json(STATS_FILE, stats_data)

    await bot.process_commands(message)

# ----------------------------
# on_ready
# ----------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} 起動")
    try:
        stats_loop.start()
    except RuntimeError:
        pass
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Command sync error:", e)

# ----------------------------
# Flask 部分
# ----------------------------
app = Flask("フニャBOT")

@app.route("/")
def home():
    return "I'm alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ----------------------------
# BOT 起動
# ----------------------------
TOKEN = os.environ.get("DISCORD_TOKEN")
assert TOKEN is not None, "DISCORD_TOKEN が設定されていません"
bot.run(TOKEN)

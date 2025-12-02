# pyright: reportMissingImports=false
"""
完全統合版フニャBOT（グローバルチャット + 統計 + 経済 + ロール購入 + Flask常駐）
要: python, discord.py v2.x, pillow, flask
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import io
import threading

# Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

# Flask
from flask import Flask

# ----------------------------
# INTENTS & BOT
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# ファイル定義
# ----------------------------
DATA_FILE = "global_chat_data.json"
ROLE_PANEL_FILE = "role_panels.json"
STATS_FILE = "stats_data.json"
ECONOMY_FILE = "economy_data.json"

# ----------------------------
# アプリデータ
# ----------------------------
data: Dict[str, Any] = {"global_channels": {}, "global_mute": {}, "global_ban": []}
role_panels: Dict[str, Any] = {}
stats_data: Dict[str, Any] = {"daily_messages": {}, "stats_channel_id": {}, "last_stats_message": {}}
economy_data: Dict[str, Any] = {}

# ----------------------------
# ファイル入出力
# ----------------------------
def save_json(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=4, ensure_ascii=False)

def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_app_data(): save_json(DATA_FILE, data)
def load_app_data(): global data; data = load_json(DATA_FILE, data)
def save_role_panels(): save_json(ROLE_PANEL_FILE, role_panels)
def load_role_panels(): global role_panels; role_panels = load_json(ROLE_PANEL_FILE, role_panels)
def save_stats_data(): save_json(STATS_FILE, stats_data)
def load_stats_data(): 
    global stats_data
    stats_data = load_json(STATS_FILE, stats_data)
    stats_data.setdefault("daily_messages", {})
    stats_data.setdefault("stats_channel_id", {})
    stats_data.setdefault("last_stats_message", {})

def save_economy(): save_json(ECONOMY_FILE, economy_data)
def load_economy(): global economy_data; economy_data = load_json(ECONOMY_FILE, economy_data)

# 初期ロード
load_app_data()
load_role_panels()
load_stats_data()
load_economy()

# ----------------------------
# safe_call
# ----------------------------
async def safe_call(coro, delay: float = 0.2):
    while True:
        try:
            res = await coro
            await asyncio.sleep(delay)
            return res
        except discord.HTTPException as e:
            status = getattr(e, "status", None)
            if status == 429:
                retry = getattr(e, "retry_after", 1)
                await asyncio.sleep(retry)
            elif status == 404:
                return None
            else:
                raise

# ----------------------------
# チャンネル判定
# ----------------------------
def is_text_sendable(ch):
    return isinstance(ch, (discord.TextChannel, discord.Thread))

# ----------------------------
# グローバルチャット転送
# ----------------------------
async def broadcast_global_message(channel: discord.abc.GuildChannel, author: discord.Member, content: str, attachments):
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
                if str(author.id) in data.get("global_ban", []):
                    continue
                if g_name in data.get("global_mute", {}) and str(author.id) in data["global_mute"].get(g_name, []):
                    continue

                try:
                    if not is_text_sendable(tgt_channel):
                        continue
                    embed = discord.Embed(description=content or "(添付のみ)", color=discord.Color.blue())
                    embed.set_author(name=f"{author.display_name}@{channel.guild.name}", icon_url=author.display_avatar.url)
                    for a in attachments:
                        if a.content_type and a.content_type.startswith("image"):
                            embed.set_image(url=a.url)
                    await safe_call(tgt_channel.send(embed=embed))
                except Exception:
                    continue

# ----------------------------
# on_message
# ----------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    # 統計
    if message.guild:
        guild_id_str = str(message.guild.id)
        date_str = message.created_at.astimezone(timezone.utc).date().isoformat()
        stats_data.setdefault("daily_messages", {})
        guild_daily = stats_data["daily_messages"].setdefault(guild_id_str, {})
        guild_daily[date_str] = guild_daily.get(date_str, 0) + 1
        save_stats_data()

    # 経済ポイント (3メッセージに1回)
    if message.guild:
        user_id = str(message.author.id)
        today = message.created_at.date().isoformat()
        economy_data.setdefault("daily_message_count", {}).setdefault(user_id, {})
        user_counts = economy_data["daily_message_count"][user_id]
        user_counts[today] = user_counts.get(today, 0) + 1

        if user_counts[today] % 3 == 0:
            economy_data.setdefault("balances", {})
            economy_data["balances"][user_id] = economy_data["balances"].get(user_id, 0) + 1
            save_economy()

    await bot.process_commands(message)

# ----------------------------
# 経済系コマンド / ロール購入
# ----------------------------
@bot.tree.command(name="balance", description="自分のフニャを確認")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    points = economy_data.get("balances", {}).get(user_id, 0)
    await interaction.response.send_message(f"あなたのふにゃ: {points}")

@bot.tree.command(name="buy_role", description="管理者: このロールをふにゃで購入可能にする")
@app_commands.describe(role="販売するロール", price="価格（ポイント）")
async def buy_role(interaction: discord.Interaction, role: discord.Role, price: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者専用コマンドです", ephemeral=True)
        return
    guild_id = str(interaction.guild.id)
    economy_data.setdefault("shop", {}).setdefault(guild_id, {})[str(role.id)] = price
    save_economy()
    await interaction.response.send_message(f"{role.name} を {price} ふにゃで購入可能にしました", ephemeral=True)

@bot.tree.command(name="buyrole", description="ロールを購入します")
@app_commands.describe(role="購入したいロール", cost="必要なフニャ数")
async def buyrole_cmd(interaction: discord.Interaction, role: discord.Role, cost: int):
    user = interaction.user
    user_id = str(user.id)
    balance = economy_data.setdefault("balances", {}).get(user_id, 0)
    if balance < cost:
        await interaction.response.send_message(f"フニャが足りません！ 必要: {cost}、所持: {balance}", ephemeral=True)
        return
    economy_data["balances"][user_id] = balance - cost
    save_economy()
    try:
        await user.add_roles(role)
    except Exception as e:
        await interaction.response.send_message(f"ロール付与エラー: {e}", ephemeral=True)
        return
    await interaction.response.send_message(f"{role.name} を購入しました！残りフニャ: {economy_data['balances'][user_id]}")

# ----------------------------
# Flask常駐
# ----------------------------
app = Flask("フニャBOT")

@app.route("/")
def home():
    return "フニャBOT稼働中"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ----------------------------
# 起動
# ----------------------------
TOKEN = os.environ.get("DISCORD_TOKEN")
assert TOKEN, "DISCORD_TOKEN が設定されていません"
bot.run(TOKEN)

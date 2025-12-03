# pyright: reportMissingImports=false
import os
import threading
import json
from datetime import timezone
from flask import Flask

import discord
from discord.ext import commands

# ----------------------------
# Flask (Render用)
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# Flask を別スレッドで起動
threading.Thread(target=run_flask).start()

# ----------------------------
# Discord BOT 準備
# ----------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# ファイルとデータ
# ----------------------------
DATA_FILE = "global_chat_data.json"
ECON_FILE = "economy_data.json"
SHOP_FILE = "shop_data.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

data = load_json(DATA_FILE, {"global_channels": {}})
economy_data = load_json(ECON_FILE, {"balances": {}, "daily_message_count": {}})
shop_data = load_json(SHOP_FILE, {})

# ----------------------------
# グローバルチャット転送
# ----------------------------
async def broadcast_global_message(channel, author, content, attachments):
    guild_id = str(channel.guild.id)

    for room, ch_list in data["global_channels"].items():
        for target in ch_list:
            tgt_guild_id, tgt_ch_id = map(int, target.split(":"))

            # 同じチャンネルには送らない
            if tgt_guild_id == channel.guild.id and tgt_ch_id == channel.id:
                continue

            tgt_guild = bot.get_guild(tgt_guild_id)
            if not tgt_guild:
                continue
            tgt_channel = tgt_guild.get_channel(tgt_ch_id)
            if not tgt_channel:
                continue

            # メッセージ送信
            embed = discord.Embed(
                description=content or "(添付のみ)",
                color=discord.Color.blue()
            )
            embed.set_author(
                name=f"{author.display_name} @ {channel.guild.name}",
                icon_url=author.display_avatar.url
            )

            await tgt_channel.send(embed=embed)

            for a in attachments:
                await tgt_channel.send(a.url)


# ----------------------------
# on_message
# ----------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # グローバルチャット
    await broadcast_global_message(message.channel, message.author, message.content, message.attachments)

    # 経済：3回に1コイン
    user_id = str(message.author.id)
    today = message.created_at.date().isoformat()
    econ_counts = economy_data.setdefault("daily_message_count", {}).setdefault(user_id, {})
    econ_counts[today] = econ_counts.get(today, 0) + 1

    # 3回に1回
    if econ_counts[today] % 3 == 0:
        balances = economy_data.setdefault("balances", {})
        balances[user_id] = balances.get(user_id, 0) + 1

    save_json(ECON_FILE, economy_data)

    await bot.process_commands(message)

# ----------------------------
# グローバルチャット管理
# ----------------------------
@bot.tree.command(name="global_create", description="グローバルチャット部屋を作成")
async def global_create(interaction: discord.Interaction, name: str):
    if name in data["global_channels"]:
        await interaction.response.send_message("既に存在しています。", ephemeral=True)
        return

    data["global_channels"][name] = []
    save_json(DATA_FILE, data)

    await interaction.response.send_message(f"グローバルチャット `{name}` を作成しました！", ephemeral=True)

@bot.tree.command(name="global_join", description="このチャンネルをグローバルチャットに参加させる")
async def global_join(interaction: discord.Interaction, name: str):
    if name not in data["global_channels"]:
        await interaction.response.send_message("そのグローバルチャットは存在しません。", ephemeral=True)
        return

    ch = interaction.channel
    identifier = f"{ch.guild.id}:{ch.id}"

    if identifier in data["global_channels"][name]:
        await interaction.response.send_message("このチャンネルはすでに参加しています。", ephemeral=True)
        return

    data["global_channels"][name].append(identifier)
    save_json(DATA_FILE, data)
    await interaction.response.send_message(f"このチャンネルを `{name}` に参加させました！", ephemeral=True)

# ----------------------------
# 経済
# ----------------------------
@bot.tree.command(name="balance", description="コイン残高を表示")
async def balance(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    bal = economy_data.get("balances", {}).get(user_id, 0)
    await interaction.response.send_message(f"💰 あなたのコイン：{bal}", ephemeral=True)

# ----------------------------
# ロールショップ
# ----------------------------
@bot.tree.command(name="shop_add", description="ロールを商品として登録")
async def shop_add(interaction: discord.Interaction, role: discord.Role, price: int):
    shop_data[str(role.id)] = price
    save_json(SHOP_FILE, shop_data)
    await interaction.response.send_message(f"ロール `{role.name}` を {price} コインで登録しました。", ephemeral=True)

@bot.tree.command(name="shop_buy", description="ロールを購入")
async def shop_buy(interaction: discord.Interaction, role: discord.Role):
    user_id = str(interaction.user.id)

    if str(role.id) not in shop_data:
        await interaction.response.send_message("そのロールはショップにありません。", ephemeral=True)
        return

    price = shop_data[str(role.id)]
    bal = economy_data.get("balances", {}).get(user_id, 0)

    if bal < price:
        await interaction.response.send_message("コインが足りません！", ephemeral=True)
        return

    # ロール付与
    await interaction.user.add_roles(role)

    economy_data["balances"][user_id] -= price
    save_json(ECON_FILE, economy_data)

    await interaction.response.send_message(f"ロール `{role.name}` を購入しました！", ephemeral=True)



# ----------------------------
# BOT起動
# ----------------------------
TOKEN = os.environ.get("DISCORD_TOKEN")
bot.run(TOKEN)

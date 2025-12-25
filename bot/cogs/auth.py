import json
import os
import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ui import View
from flask import Flask, request
import threading

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

# ===============================
# データ保存
# ===============================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load(name, default):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(name, data):
    with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

auth_data     = load("auth", {})          # {guild_id: role_id}
banned_guilds = load("banned_guilds", []) # [guild_id]
auth_codes    = load("auth_codes", {})    # {user_id: code}

# ===============================
# OAuth URL
# ===============================
def make_oauth_url(user_id: int):
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=identify%20guilds"
        f"&state={user_id}"
    )

# ===============================
# Flaskサーバー（OAuthコード受け取り用）
# ===============================
app = Flask("auth_server")

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")  # user_id
    if not code or not state:
        return "無効なリクエスト", 400

    auth_codes[state] = code
    save("auth_codes", auth_codes)

    return "認証コードを受け取りました。Botでの処理をお待ちください。"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask, daemon=True).start()

# ===============================
# Discord Cog
# ===============================
class AuthCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.auth_loop.start()

    # ---------------------------
    # /auth コマンド
    # ---------------------------
    @discord.app_commands.command(name="auth", description="認証を開始します")
    async def auth(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        url = make_oauth_url(interaction.user.id)
        view = View(timeout=300)
        view.add_item(
            discord.ui.Button(
                label="認証する",
                style=discord.ButtonStyle.url,
                url=url
            )
        )

        await interaction.followup.send(
            "下のボタンから認証してください。",
            view=view,
            ephemeral=True
        )

    # ---------------------------
    # 自動認証ループ
    # ---------------------------
    @tasks.loop(seconds=5)
    async def auth_loop(self):
        for user_id, code in list(auth_codes.items()):
            user = self.bot.get_user(int(user_id))
            if not user:
                continue

            # token取得
            async with self.session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                }
            ) as resp:
                token = await resp.json()

            if "access_token" not in token:
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            access_token = token["access_token"]

            # guilds取得
            async with self.session.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as resp:
                guilds = await resp.json()

            user_guilds = {g["id"] for g in guilds}

            # 禁止サーバーチェック
            if any(b in user_guilds for b in banned_guilds):
                try:
                    await user.send("❌ 禁止サーバーに参加しているため認証できません")
                except discord.Forbidden:
                    pass
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            # ロール付与
            for guild in self.bot.guilds:
                try:
                    member = await guild.fetch_member(int(user_id))
                except discord.NotFound:
                    continue

                role_id = auth_data.get(str(guild.id))
                if not role_id:
                    continue

                role = guild.get_role(role_id)
                if role:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        print(f"権限不足: {guild.name} の {role.name}")
                    except discord.HTTPException as e:
                        print(f"ロール付与失敗: {e}")

            try:
                await user.send("✅ 認証が完了しました！")
            except discord.Forbidden:
                pass

            del auth_codes[user_id]
            save("auth_codes", auth_codes)

    @auth_loop.before_loop
    async def before_auth_loop(self):
        await self.bot.wait_until_ready()

    # ---------------------------
    # 管理コマンド
    # ---------------------------
    @discord.app_commands.command(name="set_auth_role")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        auth_data[str(interaction.guild.id)] = role.id
        save("auth", auth_data)
        await interaction.response.send_message("✅ 認証ロールを設定しました", ephemeral=True)

    @discord.app_commands.command(name="ban_server_add")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ban_server_add(self, interaction: discord.Interaction, guild_id: str):
        if guild_id not in banned_guilds:
            banned_guilds.append(guild_id)
            save("banned_guilds", banned_guilds)
        await interaction.response.send_message("✅ 禁止サーバーを追加しました", ephemeral=True)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

# ===============================
# setup
# ===============================
async def setup(bot):
    await bot.add_cog(AuthCog(bot))

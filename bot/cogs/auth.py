import json
import os
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View
from flask import request

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

auth_data = load("auth", {})
banned_guilds = load("banned_guilds", [])

# ===============================
# OAuth URL
# ===============================
OAUTH_URL = (
    "https://discord.com/api/oauth2/authorize"
    f"?client_id={CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    "&response_type=code"
    "&scope=identify%20guilds"
)

# ===============================
# Cog
# ===============================
class AuthCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===============================
    # /auth 認証ボタン
    # ===============================
    @discord.app_commands.command(name="auth", description="認証を開始します")
    async def auth(self, interaction: discord.Interaction):

        class AuthView(View):
            def __init__(self):
                super().__init__()
                self.add_item(
                    discord.ui.Button(
                        label="認証する",
                        style=discord.ButtonStyle.url,
                        url=OAUTH_URL
                    )
                )

        await interaction.response.send_message(
            "ボタンを押して認証してください",
            view=AuthView(),
            ephemeral=True
        )

    # ===============================
    # /verify 認証コード処理
    # ===============================
    @discord.app_commands.command(name="verify", description="認証コードを入力します")
    async def verify(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)

        # トークン取得
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                }
            ) as resp:
                token_data = await resp.json()

        if "access_token" not in token_data:
            await interaction.followup.send("❌ 認証に失敗しました")
            return

        access_token = token_data["access_token"]

        # ユーザーが参加しているサーバー取得
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as resp:
                user_guilds = await resp.json()

        user_guild_ids = {g["id"] for g in user_guilds}

        # 禁止サーバーチェック
        for banned in banned_guilds:
            if banned in user_guild_ids:
                try:
                    await interaction.guild.kick(
                        interaction.user,
                        reason="禁止サーバーに参加しています"
                    )
                except:
                    pass

                await interaction.followup.send(
                    "❌ 禁止されているサーバーに参加しているため認証できません"
                )
                return

        # ロール付与
        guild_id = str(interaction.guild.id)
        role_id = auth_data.get(guild_id)
        role = interaction.guild.get_role(role_id) if role_id else None

        if role:
            await interaction.user.add_roles(role)
            await interaction.followup.send("✅ 認証完了！ロールを付与しました")
        else:
            await interaction.followup.send("⚠️ 認証ロールが設定されていません")

    # ===============================
    # /set_auth_role
    # ===============================
    @discord.app_commands.command(name="set_auth_role", description="認証ロールを設定")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        auth_data[str(interaction.guild.id)] = role.id
        save("auth", auth_data)
        await interaction.response.send_message(
            "✅ 認証ロールを設定しました",
            ephemeral=True
        )

    # ===============================
    # 禁止サーバー管理
    # ===============================
    @discord.app_commands.command(name="ban_server_add", description="禁止サーバーを追加")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ban_server_add(self, interaction: discord.Interaction, guild_id: str):
        if guild_id not in banned_guilds:
            banned_guilds.append(guild_id)
            save("banned_guilds", banned_guilds)

        await interaction.response.send_message(
            f"✅ サーバーID `{guild_id}` を禁止リストに追加しました",
            ephemeral=True
        )

    @discord.app_commands.command(name="ban_server_remove", description="禁止サーバーを削除")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ban_server_remove(self, interaction: discord.Interaction, guild_id: str):
        if guild_id in banned_guilds:
            banned_guilds.remove(guild_id)
            save("banned_guilds", banned_guilds)

        await interaction.response.send_message(
            f"✅ サーバーID `{guild_id}` を禁止リストから削除しました",
            ephemeral=True
        )

    @discord.app_commands.command(name="ban_server_list", description="禁止サーバー一覧")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ban_server_list(self, interaction: discord.Interaction):
        if not banned_guilds:
            await interaction.response.send_message(
                "禁止サーバーは設定されていません",
                ephemeral=True
            )
            return

        text = "\n".join(banned_guilds)
        await interaction.response.send_message(
            f"🚫 禁止サーバー一覧:\n{text}",
            ephemeral=True
        )

# ===============================
# setup
# ===============================
async def setup(bot):
    await bot.add_cog(AuthCog(bot))

import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="help", description="Botのコマンド一覧を表示します")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📘 Bot コマンド一覧",
            description="このBotで使用できるコマンド一覧です",
            color=0x5865F2
        )

        # ===== 認証 =====
        embed.add_field(
            name="🔐 認証",
            value=(
                "`/auth` - 認証ボタンを表示\n"
                "`/verify` - 認証を実行\n"
                "`/set_auth_role` - 認証後に付与するロールを設定"
            ),
            inline=False
        )

        # ===== ロールパネル =====
        embed.add_field(
            name="🎭 ロールパネル",
            value=(
                "`/role_panel_create` - ロールパネルを作成\n"
                "`/role_panel_add` - ロールを追加\n"
                "`/role_panel_remove` - ロールを削除\n"
                "`/role_panel_toggle` - ロールのON/OFF切り替え"
            ),
            inline=False
        )

        # ===== チケット =====
        embed.add_field(
            name="🎫 チケット",
            value=(
                "`/ticket_create` - チケットパネル作成\n"
                "`/ticket_setup` - チケット設定\n"
                "🎟️ ボタンでチケット作成\n"
                "❌ ボタンでチケットを閉じる"
            ),
            inline=False
        )

        # ===== グローバルチャット =====
        embed.add_field(
            name="🌐 グローバルチャット",
            value=(
                "`/global_create` - グローバルチャット作成\n"
                "`/global_join` - チャンネルを参加させる"
            ),
            inline=False
        )

        embed.set_footer(text="Avanzare Mk.2")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))

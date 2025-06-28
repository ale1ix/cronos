# Guardar en: /cogs/ck_cog.py (Lógica de CK revisada)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3



# --- Modal para el Motivo del CK Voluntario ---
class VoluntaryCKModal(discord.ui.Modal, title="Solicitud de CK Voluntario"):
    reason = discord.ui.TextInput(
        label="Motivo de tu CK",
        style=discord.TextStyle.paragraph,
        placeholder="Explica brevemente por qué decides terminar con tu personaje (ej: fin de la historia, cambio de personaje, etc.)",
        required=True
    )

    def __init__(self, ck_cog):
        super().__init__()
        self.ck_cog = ck_cog

    async def on_submit(self, interaction: discord.Interaction):
        # Lógica para procesar la solicitud de CK voluntario
        # Por ahora, simplemente lo registraremos. Podría requerir aprobación de admin.
        
        # Guardar en la base de datos (puedes ampliar la tabla si quieres)
        embed = discord.Embed(
            title="📄 Solicitud de CK Voluntario Registrada",
            description=f"El usuario {interaction.user.mention} ha solicitado un CK voluntario.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Motivo", value=self.reason.value)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        # Enviar a un canal de logs o de admins
        ck_channel_id = self.ck_cog.get_config(interaction.guild.id, 'ck_requests_channel')
        if ck_channel_id and (channel := interaction.guild.get_channel(ck_channel_id)):
            await channel.send(embed=embed)

        await interaction.response.send_message("Tu solicitud de CK voluntario ha sido registrada. Un administrador se pondrá en contacto contigo.", ephemeral=True)


class CkCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    def get_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None
        
    @app_commands.command(name="solicitar-ck", description="Inicia el proceso para realizar un CK voluntario sobre tu propio personaje.")
    async def solicitar_ck(self, interaction: discord.Interaction):
        # Muestra el formulario para que el usuario explique su motivo
        modal = VoluntaryCKModal(self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="ejecutar-ck", description="[Admin] Aplica un CK a un usuario, eliminando sus datos de rol.")
    async def ejecutar_ck(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        
        
        # Aquí iría la lógica de borrado de datos.
        # Por ejemplo:
        # 1. Borrar su dinero de la tabla 'economia'
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM economia WHERE user_id = ?", (usuario.id,))
        
        # 2. Borrar su DNI de la tabla 'dnis'
        cursor.execute("DELETE FROM dnis WHERE user_id = ? AND server_id = ?", (usuario.id, interaction.guild.id))
        
        # 3. Borrar sus propiedades
        cursor.execute("UPDATE propiedades SET propietario_id = NULL, en_venta = TRUE WHERE propietario_id = ?", (usuario.id,))
        
        # 4. Limpiar antecedentes
        cursor.execute("DELETE FROM antecedentes WHERE user_id = ?", (usuario.id,))
        
        # 5. Limpiar multas activas
        cursor.execute("DELETE FROM multas_activas WHERE user_id = ?", (usuario.id,))
        
        self.db.commit()

        # Anuncio público del CK
        records_channel_id = self.get_config(interaction.guild.id, 'justice_records_channel')
        if records_channel_id and (channel := self.bot.get_channel(records_channel_id)):
            embed = discord.Embed(
                title="💀 Character Kill Ejecutado 💀",
                description=f"El personaje de **{usuario.display_name}** ha llegado a su fin.",
                color=0x000000 # Negro
            )
            embed.add_field(name="Usuario", value=usuario.mention, inline=True)
            embed.add_field(name="Admin a Cargo", value=interaction.user.mention, inline=True)
            embed.add_field(name="Motivo", value=motivo, inline=False)
            embed.set_thumbnail(url="https://i.imgur.com/g3v4A3e.png") # Icono de calavera
            await channel.send(embed=embed)
        
        await interaction.followup.send(f"✅ CK ejecutado con éxito sobre {usuario.mention}. Todos sus datos de personaje han sido borrados.")

async def setup(bot: commands.Bot):
    await bot.add_cog(CkCog(bot))
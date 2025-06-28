# Guardar en: /cogs/alerta_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime

class AlertaCiudad(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    def get_config(self, server_id: int, key: str):
        """Obtiene un valor de la tabla de configuración del servidor."""
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None

    async def actualizar_alerta(self, nivel: str, razon: str, guild: discord.Guild):
        channel_id = self.get_config(guild.id, 'city_alert_channel')
        message_id = self.get_config(guild.id, 'city_alert_message_id')

        if not all([channel_id, message_id]):
            print(f"Alerta no configurada para el servidor {guild.name}")
            return

        colores = { "VERDE": discord.Color.green(), "AMARILLO": discord.Color.yellow(), "NARANJA": discord.Color.orange(), "ROJO": discord.Color.red() }
        embed = discord.Embed(
            title=f"NIVEL DE ALERTA: {nivel}",
            description=f"**Razón:** {razon}",
            color=colores.get(nivel, discord.Color.default())
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text="Última actualización")
        embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        try:
            channel = await self.bot.fetch_channel(int(channel_id))
            message = await channel.fetch_message(int(message_id))
            await message.edit(embed=embed)
        except (discord.NotFound, discord.Forbidden) as e:
            print(f"Error al actualizar mensaje de alerta en {guild.name}: {e}")
        
    @app_commands.command(name="alerta", description="[Gobierno] Cambia el nivel de alerta de la ciudad.")
    @app_commands.choices(nivel=[
        app_commands.Choice(name="✅ Verde - Calma", value="VERDE"),
        app_commands.Choice(name="🟡 Amarillo - Precaución", value="AMARILLO"),
        app_commands.Choice(name="🟠 Naranja - Actividad sospechosa", value="NARANJA"),
        app_commands.Choice(name="🔴 Rojo - Peligro Inminente", value="ROJO"),
    ])

    async def alerta(self, interaction: discord.Interaction, nivel: app_commands.Choice[str], razon: str):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'government'):
            await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
            return
        await self.actualizar_alerta(nivel.value, razon, interaction.guild)
        await interaction.response.send_message(f"Nivel de alerta cambiado a **{nivel.name}**.", ephemeral=True)
        
        if nivel.value in ["NARANJA", "ROJO"]:
            rol_policia_id = self.get_config(interaction.guild.id, 'police_role')
            if rol_policia_id:
                rol_policia = interaction.guild.get_role(rol_policia_id)
                canal_alerta_id = self.get_config(interaction.guild.id, 'city_alert_channel')
                if rol_policia and canal_alerta_id:
                    canal_alerta = self.bot.get_channel(canal_alerta_id)
                    await canal_alerta.send(f"{rol_policia.mention}, se requiere su atención. Nivel de alerta elevado.", allowed_mentions=discord.AllowedMentions(roles=True))

async def setup(bot: commands.Bot):
    await bot.add_cog(AlertaCiudad(bot))
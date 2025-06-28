# Guardar en: /cogs/social_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

class Social(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    def get_config(self, server_id: int, key: str):
        """Obtiene un valor de la tabla de configuración del servidor."""
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return int(result[0]) if result else None

    @app_commands.command(name="anonimo", description="Envía un mensaje anónimo a un canal público.")
    async def anonimo(self, interaction: discord.Interaction, mensaje: str):
        # 1. Obtener los canales configurados
        public_channel_id = self.get_config(interaction.guild.id, 'anonymous_channel')
        logs_channel_id = self.get_config(interaction.guild.id, 'anonymous_logs_channel')

        if not public_channel_id or not logs_channel_id:
            return await interaction.response.send_message(
                "❌ El sistema de mensajes anónimos no está configurado en este servidor. "
                "Un administrador debe establecer 'anonymous_channel' y 'anonymous_logs_channel'.",
                ephemeral=True
            )
        
        # 2. Intentar obtener los objetos de canal
        try:
            public_channel = await self.bot.fetch_channel(public_channel_id)
            logs_channel = await self.bot.fetch_channel(logs_channel_id)
        except (discord.NotFound, discord.Forbidden):
            return await interaction.response.send_message(
                "❌ Error: Uno de los canales configurados para mensajes anónimos ya no existe o no tengo acceso.",
                ephemeral=True
            )

        # 3. Crear y enviar el mensaje anónimo público
        public_embed = discord.Embed(
            description=f"```{mensaje}```",
            color=discord.Color.dark_grey()
        )
        public_embed.set_author(name="Mensaje Anónimo")
        
        try:
            await public_channel.send(embed=public_embed)
        except discord.Forbidden:
             return await interaction.response.send_message(
                f"❌ Error: No tengo permisos para enviar mensajes en {public_channel.mention}.",
                ephemeral=True
            )

        # 4. Crear y enviar el log para los administradores
        log_embed = discord.Embed(
            title="Nuevo Mensaje Anónimo Enviado",
            color=discord.Color.orange()
        )
        log_embed.add_field(name="Autor Original", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        log_embed.add_field(name="Contenido del Mensaje", value=f"```{mensaje}```", inline=False)
        
        try:
            await logs_channel.send(embed=log_embed)
        except discord.Forbidden:
            # Informar al usuario que el log falló, pero el mensaje público se envió
            return await interaction.response.send_message(
                "✅ Tu mensaje anónimo fue enviado, pero no se pudo registrar en los logs por falta de permisos.",
                ephemeral=True
            )

        # 5. Confirmar al usuario que todo salió bien
        await interaction.response.send_message("✅ Tu mensaje anónimo ha sido enviado.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
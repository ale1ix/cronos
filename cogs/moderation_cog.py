# Guardar en: /cogs/moderation_cog.py (VERSIÓN CON /sancionar SIMPLE)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime
from typing import Optional

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    async def has_permission(self, interaction: discord.Interaction, role_type: str) -> bool:
        """Verifica si el usuario tiene un rol de moderador o superior (admin)."""
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog: return False
        return await config_cog.has_permission(interaction, role_type) or await config_cog.has_permission(interaction, 'admin')

    async def registrar_sancion(self, interaction: discord.Interaction, usuario: discord.Member, tipo: str, razon: str, duracion_seg: Optional[int] = None):
        """Función central para guardar sanciones en la DB."""
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO sanciones (server_id, user_id, moderator_id, tipo, razon, duracion_segundos) VALUES (?, ?, ?, ?, ?, ?)",
            (interaction.guild.id, usuario.id, interaction.user.id, tipo, razon, duracion_seg)
        )
        self.db.commit()

    # --- NUEVO COMANDO /sancionar (solo para avisos) ---
    @app_commands.command(name="sancionar", description="[Mod] Registra un aviso (warn) para un usuario.")
    async def sancionar_warn(self, interaction: discord.Interaction, usuario: discord.Member, razon: str):
        if not await self.has_permission(interaction, 'moderator'):
            return await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)

        if usuario.id == interaction.user.id:
            return await interaction.response.send_message("❌ No te puedes sancionar a ti mismo.", ephemeral=True)
        
        # Guardamos el aviso en la base de datos
        await self.registrar_sancion(interaction, usuario, "aviso", razon)

        # Intentamos avisar al usuario por DM
        try:
            await usuario.send(f"Has recibido un aviso en el servidor **{interaction.guild.name}**.\n**Razón:** {razon}")
        except discord.Forbidden:
            pass # Si el usuario tiene los DMs cerrados, no hacemos nada

        await interaction.response.send_message(f"✅ Se ha registrado un aviso para {usuario.mention}. Razón: {razon}", ephemeral=True)


    # --- Grupo de Comandos de Gestión ---
    sanciones_group = app_commands.Group(name="sanciones", description="Gestiona las sanciones de los usuarios.")

    @sanciones_group.command(name="ver", description="[Mod] Muestra el historial de sanciones de un usuario.")
    async def sanciones_ver(self, interaction: discord.Interaction, usuario: discord.Member):
        if not await self.has_permission(interaction, 'moderator'):
            return await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
        # ... (código sin cambios)
        cursor = self.db.cursor()
        cursor.execute("SELECT sancion_id, moderator_id, tipo, razon, duracion_segundos, timestamp, activa FROM sanciones WHERE server_id = ? AND user_id = ? ORDER BY timestamp DESC", (interaction.guild.id, usuario.id))
        records = cursor.fetchall()
        if not records:
            return await interaction.response.send_message(f"{usuario.mention} no tiene sanciones en su historial.", ephemeral=True)
        embed = discord.Embed(title=f"Historial de Sanciones de {usuario.display_name}", color=discord.Color.orange())
        embed.set_thumbnail(url=usuario.display_avatar.url)
        for sancion_id, mod_id, tipo, razon, dur_seg, ts_str, activa in records[:10]:
            mod_user = interaction.guild.get_member(mod_id) or f"ID: {mod_id}"
            ts_dt = datetime.datetime.fromisoformat(ts_str)
            estado = "✅ Activa" if activa else "❌ Expirada/Anulada"
            duracion_str = f"Duración: {datetime.timedelta(seconds=dur_seg)}" if dur_seg else ""
            embed.add_field(name=f"ID `{sancion_id}` | {tipo.capitalize()} | <t:{int(ts_dt.timestamp())}:D>", value=f"**Razón:** {razon or 'No especificada.'}\n**Moderador:** {mod_user.mention}\n{duracion_str} - **{estado}**", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @sanciones_group.command(name="quitar", description="[Mod] Anula una sanción activa del historial de un usuario.")
    async def sanciones_quitar(self, interaction: discord.Interaction, usuario: discord.Member, id_sancion: int, razon_anulacion: str):
        if not await self.has_permission(interaction, 'moderator'):
            return await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
        # ... (código sin cambios)
        cursor = self.db.cursor()
        cursor.execute("UPDATE sanciones SET activa = FALSE WHERE sancion_id = ? AND user_id = ? AND activa = TRUE", (id_sancion, usuario.id))
        if cursor.rowcount > 0:
            self.db.commit()
            if usuario.is_timed_out():
                await usuario.timeout(None, reason=f"Sanción #{id_sancion} anulada por {interaction.user.name}")
            await interaction.response.send_message(f"✅ Sanción #{id_sancion} de {usuario.mention} anulada. Razón: {razon_anulacion}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró una sanción activa con ID #{id_sancion} para {usuario.mention}.", ephemeral=True)

    # --- Comandos Directos de Sanción (sin cambios) ---
    @app_commands.command(name="timeout", description="[Mod] Aísla a un usuario por un tiempo determinado.")
    async def timeout(self, interaction: discord.Interaction, usuario: discord.Member, duracion: str, razon: str):
        # ... (código sin cambios)
        if not await self.has_permission(interaction, 'moderator'): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        try:
            value = int(duracion[:-1]); unit = duracion[-1].lower()
            if unit == 's': delta = datetime.timedelta(seconds=value)
            elif unit == 'm': delta = datetime.timedelta(minutes=value)
            elif unit == 'h': delta = datetime.timedelta(hours=value)
            elif unit == 'd': delta = datetime.timedelta(days=value)
            else: raise ValueError
        except (ValueError, IndexError): return await interaction.response.send_message("Formato de duración inválido.", ephemeral=True)
        await usuario.timeout(delta, reason=razon)
        await self.registrar_sancion(interaction, usuario, "timeout", razon, delta.total_seconds())
        await interaction.response.send_message(f"✅ {usuario.mention} ha sido aislado por **{duracion}**. Razón: {razon}")

    @app_commands.command(name="kick", description="[Mod] Expulsa a un usuario del servidor.")
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, razon: str):
        # ... (código sin cambios)
        if not await self.has_permission(interaction, 'moderator'): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        await usuario.kick(reason=razon)
        await self.registrar_sancion(interaction, usuario, "kick", razon)
        await interaction.response.send_message(f"✅ {usuario.mention} ha sido expulsado. Razón: {razon}")

    @app_commands.command(name="ban", description="[Mod] Banea a un usuario del servidor.")
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, razon: str):
        # ... (código sin cambios)
        if not await self.has_permission(interaction, 'moderator'): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        await usuario.ban(reason=razon)
        await self.registrar_sancion(interaction, usuario, "ban", razon)
        await interaction.response.send_message(f"✅ {usuario.mention} ha sido baneado. Razón: {razon}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
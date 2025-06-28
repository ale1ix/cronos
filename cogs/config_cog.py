# Guardar en: /cogs/config_cog.py (VERSIÓN LIMPIA Y CORRECTA)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from typing import Literal

class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    async def has_permission(self, interaction: discord.Interaction, role_type: str) -> bool:
        cursor = self.db.cursor()
        cursor.execute("SELECT role_id FROM role_config WHERE server_id = ? AND role_type = ?", (interaction.guild.id, role_type))
        configured_roles_ids = {row[0] for row in cursor.fetchall()}
        if not configured_roles_ids: return False
        user_roles_ids = {role.id for role in interaction.user.roles}
        return not user_roles_ids.isdisjoint(configured_roles_ids)

    # --- GRUPOS DE CONFIGURACIÓN ---
    configurar = app_commands.Group(name="configurar", description="Configura todos los módulos del bot.", default_permissions=discord.Permissions(administrator=True))
    roles_subgroup = app_commands.Group(name="roles", description="Gestiona los roles de permisos.", parent=configurar)
    canales_subgroup = app_commands.Group(name="canales", description="Configura los canales de texto del bot.", parent=configurar)
    categorias_subgroup = app_commands.Group(name="categoria", description="Configura las categorías de canales del bot.", parent=configurar)
    tickets_subgroup = app_commands.Group(name="tickets", description="Configura el sistema de tickets.", parent=configurar)
    loteria_subgroup = app_commands.Group(name="loteria", description="Configura el sistema de lotería.", parent=configurar)

    # --- COMANDO PARA TICKETS ---
    @tickets_subgroup.command(name="establecer", description="Establece el rol de soporte Y la categoría para los tickets.")
    async def tickets_establecer(self, interaction: discord.Interaction, rol_soporte: discord.Role, categoria_tickets: discord.CategoryChannel):
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO server_config (server_id, key, value) VALUES (?, ?, ?)", (interaction.guild.id, 'ticket_support_role', rol_soporte.id))
        cursor.execute("REPLACE INTO server_config (server_id, key, value) VALUES (?, ?, ?)", (interaction.guild.id, 'ticket_category', categoria_tickets.id))
        self.db.commit()
        await interaction.response.send_message(f"✅ Sistema de tickets configurado.\n- **Rol de Soporte:** {rol_soporte.mention}\n- **Categoría:** `{categoria_tickets.name}`", ephemeral=True)

    @loteria_subgroup.command(name="establecer_precio", description="Establece el precio del ticket de lotería.")
    async def loteria_establecer_precio(self, interaction: discord.Interaction, precio: int):
        if precio <= 0:
            return await interaction.response.send_message("❌ El precio debe ser mayor que cero.", ephemeral=True)
        
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO server_config (server_id, key, value) VALUES (?, ?, ?)", (interaction.guild.id, 'lottery_ticket_cost', precio))
        self.db.commit()
        await interaction.response.send_message(f"✅ Precio del ticket de lotería establecido en **${precio:,}**.", ephemeral=True)

    # --- COMANDO PARA CATEGORÍAS (JUZGADOS) ---
    @categorias_subgroup.command(name="establecer", description="Establece una categoría de canales funcional.")
    async def categoria_establecer(self, interaction: discord.Interaction, 
                                   tipo_categoria: Literal['courts_category'],
                                   categoria: discord.CategoryChannel):
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO server_config (server_id, key, value) VALUES (?, ?, ?)", (interaction.guild.id, tipo_categoria, categoria.id))
        self.db.commit()
        await interaction.response.send_message(f"✅ Categoría para `{tipo_categoria}` establecida en **{categoria.name}**.", ephemeral=True)

    # --- COMANDOS DE ROLES ---
    @roles_subgroup.command(name="añadir", description="Añade un rol a una categoría de permisos.")
    async def roles_añadir(self, interaction: discord.Interaction, tipo: Literal['admin', 'police', 'government', 'moderator', 'juez'], rol: discord.Role):
        try:
            cursor = self.db.cursor()
            cursor.execute("INSERT INTO role_config (server_id, role_type, role_id) VALUES (?, ?, ?)", (interaction.guild.id, tipo, rol.id))
            self.db.commit()
            await interaction.response.send_message(f"✅ Rol {rol.mention} añadido a la categoría `{tipo}`.", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message(f"⚠️ Rol {rol.mention} ya está en la categoría `{tipo}`.", ephemeral=True)

    @roles_subgroup.command(name="quitar", description="Quita un rol de una categoría de permisos.")
    async def roles_quitar(self, interaction: discord.Interaction, tipo: Literal['admin', 'police', 'government', 'moderator', 'juez'], rol: discord.Role):
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM role_config WHERE server_id = ? AND role_type = ? AND role_id = ?", (interaction.guild.id, tipo, rol.id))
        self.db.commit()
        if cursor.rowcount > 0: await interaction.response.send_message(f"✅ Rol {rol.mention} quitado de la categoría `{tipo}`.", ephemeral=True)
        else: await interaction.response.send_message(f"❌ Rol {rol.mention} no estaba en la categoría `{tipo}`.", ephemeral=True)
    
    # --- COMANDO DE CANALES ---
    @canales_subgroup.command(name="establecer", description="Configura un canal de texto que usará el bot.")
    async def canales_establecer(self, interaction: discord.Interaction, 
                                 tipo_canal: Literal['dni_requests_channel', 'bot_logs_channel', 'justice_records_channel', 'city_alert_channel', 'ck_requests_channel', 'anonymous_channel', 'anonymous_logs_channel'], 
                                 canal: discord.TextChannel):
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO server_config (server_id, key, value) VALUES (?, ?, ?)", (interaction.guild.id, tipo_canal, canal.id))
        self.db.commit()
        await interaction.response.send_message(f"✅ Canal para `{tipo_canal}` establecido en {canal.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
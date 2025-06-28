# Guardar en: /cogs/tickets_cog.py (VERSIÓN LIMPIA Y CORRECTA)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime

# --- Modal para el Motivo del Ticket ---
class TicketReasonModal(discord.ui.Modal, title="Abrir un Ticket de Soporte"):
    reason = discord.ui.TextInput(
        label="Motivo del Ticket",
        style=discord.TextStyle.paragraph,
        placeholder="Describe brevemente tu problema o consulta...",
        required=True,
        max_length=500
    )
    def __init__(self, tickets_cog):
        super().__init__()
        self.tickets_cog = tickets_cog
    async def on_submit(self, interaction: discord.Interaction):
        await self.tickets_cog.create_ticket_channel(interaction, self.reason.value)

# --- Vista para el panel inicial de tickets ---
class TicketLauncherView(discord.ui.View):
    def __init__(self, tickets_cog):
        super().__init__(timeout=None)
        self.tickets_cog = tickets_cog
    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.success, emoji="📩", custom_id="ticket_launcher_button")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketReasonModal(self.tickets_cog)
        await interaction.response.send_modal(modal)

# --- Vista para cerrar un ticket dentro del canal ---
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cerrando el ticket en 5 segundos...", ephemeral=True)
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket cerrado por {interaction.user.name}")


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        # Añadimos las vistas persistentes para que funcionen tras reiniciar el bot
        self.bot.add_view(TicketLauncherView(self))
        self.bot.add_view(CloseTicketView())

    def get_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return int(result[0]) if result else None
        
    @app_commands.command(name="panel-tickets", description="[Admin] Envía el panel para abrir tickets en el canal actual.")
    async def panel_tickets(self, interaction: discord.Interaction, titulo: str, descripcion: str):
        # Para los permisos, depende del cog de configuración
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            return await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)

        embed = discord.Embed(title=titulo, description=descripcion, color=discord.Color.blue())
        embed.set_footer(text="Haz clic en el botón de abajo para recibir ayuda.")
        await interaction.channel.send(embed=embed, view=TicketLauncherView(self))
        await interaction.response.send_message("✅ Panel de tickets enviado.", ephemeral=True)

    async def create_ticket_channel(self, interaction: discord.Interaction, reason: str):
        await interaction.response.defer(ephemeral=True)
        support_role_id = self.get_config(interaction.guild.id, 'ticket_support_role')
        category_id = self.get_config(interaction.guild.id, 'ticket_category')
        
        if not support_role_id or not category_id:
            return await interaction.followup.send("❌ El sistema de tickets no ha sido configurado. Un admin debe usar `/configurar tickets establecer`.", ephemeral=True)
            
        category = interaction.guild.get_channel(category_id)
        support_role = interaction.guild.get_role(support_role_id)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            self.bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        try:
            channel_name = f"ticket-{interaction.user.name}"
            ticket_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)
        except discord.Forbidden:
            return await interaction.followup.send("❌ El bot no tiene permisos para crear canales en la categoría configurada.", ephemeral=True)
        
        embed = discord.Embed(title=f"Ticket de {interaction.user.display_name}", description=f"**Motivo:**\n>>> {reason}", color=discord.Color.green())
        await ticket_channel.send(f"¡Bienvenido {interaction.user.mention}! El equipo de {support_role.mention} te atenderá pronto.", embed=embed, view=CloseTicketView())
        await interaction.followup.send(f"✅ ¡Tu ticket ha sido creado! Ve a {ticket_channel.mention}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
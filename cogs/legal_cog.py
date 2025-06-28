# Guardar en: /cogs/legal_cog.py (VERSIÓN CORREGIDA Y FUNCIONAL)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime

class CloseDemandView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar Caso", style=discord.ButtonStyle.danger, emoji="⚖️", custom_id="close_demand_button")
    async def close_demand(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_cog = interaction.client.get_cog('ConfigCog')
        if not config_cog or not (await config_cog.has_permission(interaction, 'juez') or await config_cog.has_permission(interaction, 'admin')):
            return await interaction.response.send_message("🚫 Solo los jueces pueden cerrar el caso.", ephemeral=True)
        
        await interaction.response.send_message("El caso se archivará en 10 segundos...", ephemeral=True)
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=10))
        await interaction.channel.delete(reason=f"Caso cerrado por el juez {interaction.user.name}")

class Legal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        # La vista persistente se añade una sola vez al iniciar el bot
        self.bot.add_view(CloseDemandView())

    # --- FUNCIÓN CORREGIDA PARA OBTENER EL ROL DE JUEZ ---
    def get_juez_role_id(self, server_id: int):
        """Busca el rol de juez en la tabla correcta ('role_config')."""
        cursor = self.db.cursor()
        # Esta consulta apunta a la tabla correcta para los roles
        cursor.execute("SELECT role_id FROM role_config WHERE server_id = ? AND role_type = 'juez'", (server_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    # Esta función SÍ es correcta para buscar en la tabla 'server_config'
    def get_server_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None

    @app_commands.command(name="demandar", description="Inicia un proceso judicial contra otro ciudadano.")
    async def demandar(self, interaction: discord.Interaction, demandado: discord.Member, razon: str):
        if demandado.id == interaction.user.id:
            return await interaction.response.send_message("❌ No puedes demandarte a ti mismo.", ephemeral=True)
        if demandado.bot:
            return await interaction.response.send_message("❌ No puedes demandar a un bot.", ephemeral=True)

        # --- LÓGICA DE CONFIGURACIÓN ARREGLADA ---
        juez_role_id = self.get_juez_role_id(interaction.guild.id)
        courts_category_id = self.get_server_config(interaction.guild.id, 'courts_category')

        if not juez_role_id:
            return await interaction.response.send_message("❌ **Error de Configuración:** No se ha establecido un rol de 'juez'. Usa `/configurar roles añadir`.", ephemeral=True)
        if not courts_category_id:
            return await interaction.response.send_message("❌ **Error de Configuración:** No se ha establecido la categoría de juzgados. Usa `/configurar categoria establecer`.", ephemeral=True)
            
        category = interaction.guild.get_channel(courts_category_id)
        juez_role = interaction.guild.get_role(juez_role_id)

        if not category or not juez_role:
            return await interaction.response.send_message("❌ Error: La categoría de juzgados o el rol de juez configurado ya no existe en el servidor.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            demandado: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            juez_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            self.bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        try:
            channel_name = f"caso-{interaction.user.name}-vs-{demandado.name}"
            demand_channel = await category.create_text_channel(name=channel_name, overwrites=overwrites, reason=f"Demanda de {interaction.user.name}")
        except discord.Forbidden:
            return await interaction.followup.send("❌ El bot no tiene permisos para crear canales en la categoría de juzgados.", ephemeral=True)
        
        embed = discord.Embed(title=f"⚖️ Nuevo Proceso Judicial: Caso #{demand_channel.id}", color=discord.Color.from_rgb(139, 69, 19))
        embed.add_field(name="🧑‍⚖️ Demandante", value=interaction.user.mention, inline=True)
        embed.add_field(name="👤 Demandado", value=demandado.mention, inline=True)
        embed.add_field(name="📜 Razón de la Demanda", value=f"```{razon}```", inline=False)
        embed.set_footer(text="El equipo judicial tomará el caso. Mantened la compostura.")

        await demand_channel.send(f"Atención {juez_role.mention}, {interaction.user.mention}, {demandado.mention}. Se ha abierto un nuevo caso.", embed=embed, view=CloseDemandView())
        await interaction.followup.send(f"✅ Tu demanda ha sido presentada. Dirígete a {demand_channel.mention} para continuar.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Legal(bot))
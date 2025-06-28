# Guardar en: /cogs/dni_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import string
import datetime

# --- Formulario Emergente para la Solicitud de DNI ---
# Ya no pide la URL de la foto. La foto se pasa desde el comando.
class DNIApplicationModal(discord.ui.Modal, title="Solicitud de DNI de la Ciudad"):
    full_name = discord.ui.TextInput(label="Nombre Completo", placeholder="Ej: Juan Pérez García")
    date_of_birth = discord.ui.TextInput(label="Fecha de Nacimiento", placeholder="Ej: 01/01/1990")
    sex = discord.ui.TextInput(label="Sexo", placeholder="Ej: Masculino / Femenino")
    nationality = discord.ui.TextInput(label="Nacionalidad", placeholder="Ej: Española")

    def __init__(self, dni_cog, photo: discord.Attachment):
        super().__init__()
        self.dni_cog = dni_cog
        self.photo = photo

    async def on_submit(self, interaction: discord.Interaction):
        # Envía la solicitud al canal de admins para su aprobación
        await self.dni_cog.process_dni_application(interaction, self, self.photo)

# --- Vista con Botones para la Aprobación del DNI ---
# Le pasamos la foto como un objeto Attachment para procesarla después
class DNIApprovalView(discord.ui.View):
    def __init__(self, applicant: discord.Member, applicant_data, photo: discord.Attachment):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.applicant_data = applicant_data
        self.photo = photo

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.success, emoji="✅")
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        dni_cog = interaction.client.get_cog('DNICog')
        await dni_cog.approve_dni(interaction, self.applicant, self.applicant_data, self.photo)

    @discord.ui.button(label="Denegar", style=discord.ButtonStyle.danger, emoji="❌")
    async def denegar(self, interaction: discord.Interaction, button: discord.ui.Button):
        dni_cog = interaction.client.get_cog('DNICog')
        await dni_cog.deny_dni(interaction)

class DNICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

    def get_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None

    def generate_unique_dni_number(self, server_id: int):
        while True:
            number = ''.join(random.choices(string.digits, k=8))
            letter = "TRWAGMYFPDXBNJZSQVHLCKE"[int(number) % 23]
            dni_number = f"{number}{letter}"
            cursor = self.db.cursor()
            cursor.execute("SELECT 1 FROM dnis WHERE server_id = ? AND dni_number = ?", (server_id, dni_number))
            if not cursor.fetchone():
                return dni_number

    async def process_dni_application(self, interaction: discord.Interaction, modal: DNIApplicationModal, photo: discord.Attachment):
        admin_channel_id = self.get_config(interaction.guild.id, "dni_requests_channel")
        if not admin_channel_id:
            return await interaction.response.send_message("❌ Error: El canal de solicitudes de DNI no ha sido configurado.", ephemeral=True)
        
        admin_channel = self.bot.get_channel(admin_channel_id)
        
        embed = discord.Embed(title="Nueva Solicitud de DNI Pendiente", color=discord.Color.orange())
        embed.set_author(name=interaction.user, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Nombre Completo", value=modal.full_name.value, inline=False)
        embed.add_field(name="Fecha de Nacimiento", value=modal.date_of_birth.value, inline=True)
        embed.add_field(name="Sexo", value=modal.sex.value, inline=True)
        embed.add_field(name="Nacionalidad", value=modal.nationality.value, inline=True)
        embed.set_image(url=photo.url) # La URL temporal de Discord funciona para la vista previa
        embed.set_footer(text=f"ID de Usuario: {interaction.user.id}")

        applicant_data = {
            "full_name": modal.full_name.value,
            "date_of_birth": modal.date_of_birth.value,
            "sex": modal.sex.value,
            "nationality": modal.nationality.value,
        }
        view = DNIApprovalView(interaction.user, applicant_data, photo)
        await admin_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Tu solicitud de DNI ha sido enviada para su revisión.", ephemeral=True)

    async def approve_dni(self, interaction: discord.Interaction, applicant: discord.Member, applicant_data: dict, photo: discord.Attachment):
        # --- Lógica Clave: Subir la foto a un canal de logs para obtener un link permanente ---
        logs_channel_id = self.get_config(interaction.guild.id, "bot_logs_channel")
        if not logs_channel_id:
            return await interaction.response.send_message("❌ Error crítico: El canal de logs del bot no está configurado. No se puede guardar la foto del DNI.", ephemeral=True)
        
        logs_channel = self.bot.get_channel(logs_channel_id)
        photo_file = await photo.to_file()
        log_message = await logs_channel.send(f"Foto DNI para {applicant.mention} ({applicant.id})", file=photo_file)
        permanent_photo_url = log_message.attachments[0].url

        dni_number = self.generate_unique_dni_number(interaction.guild.id)
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO dnis (server_id, user_id, dni_number, full_name, date_of_birth, sex, nationality, photo_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (interaction.guild.id, applicant.id, dni_number, applicant_data['full_name'], applicant_data['date_of_birth'], applicant_data['sex'], applicant_data['nationality'], permanent_photo_url))
        self.db.commit()
        
        citizen_role_id = self.get_config(interaction.guild.id, "citizen_role")
        if citizen_role_id:
            citizen_role = interaction.guild.get_role(citizen_role_id)
            if citizen_role:
                await applicant.add_roles(citizen_role, reason="DNI Aprobado")
        
        original_embed = interaction.message.embeds[0]
        original_embed.title = "✅ Solicitud de DNI APROBADA"
        original_embed.color = discord.Color.green()
        original_embed.add_field(name="Aprobado por", value=interaction.user.mention, inline=False)
        original_embed.add_field(name="Nº DNI Asignado", value=f"`{dni_number}`")
        await interaction.message.edit(embed=original_embed, view=None)
        await interaction.response.send_message("Solicitud aprobada con éxito.", ephemeral=True)

    async def deny_dni(self, interaction: discord.Interaction):
        original_embed = interaction.message.embeds[0]
        original_embed.title = "❌ Solicitud de DNI DENEGADA"
        original_embed.color = discord.Color.red()
        original_embed.add_field(name="Denegado por", value=interaction.user.mention)
        await interaction.message.edit(embed=original_embed, view=None)
        await interaction.response.send_message("Solicitud denegada.", ephemeral=True)

    # --- Grupo Principal DNI ---
    dni_group = app_commands.Group(name="dni", description="Comandos relacionados con el DNI.")


    @dni_group.command(name="solicitar", description="Inicia el proceso para obtener tu DNI. Debes adjuntar una foto.")
    async def solicitar_dni(self, interaction: discord.Interaction, foto: discord.Attachment):
        cursor = self.db.cursor()
        cursor.execute("SELECT 1 FROM dnis WHERE server_id = ? AND user_id = ?", (interaction.guild.id, interaction.user.id))
        if cursor.fetchone():
            return await interaction.response.send_message("❌ Ya tienes un DNI aprobado en este servidor.", ephemeral=True)
            
        if not foto.content_type or not foto.content_type.startswith('image/'):
            return await interaction.response.send_message("❌ El archivo adjunto debe ser una imagen.", ephemeral=True)

        modal = DNIApplicationModal(self, foto)
        await interaction.response.send_modal(modal)

    @dni_group.command(name="mostrar", description="Muestra el DNI de un ciudadano.")
    async def dni(self, interaction: discord.Interaction, usuario: discord.Member):
        cursor = self.db.cursor()
        cursor.execute("SELECT dni_number, full_name, date_of_birth, sex, nationality, photo_url FROM dnis WHERE server_id = ? AND user_id = ?", (interaction.guild.id, usuario.id))
        result = cursor.fetchone()

        if not result:
            return await interaction.response.send_message(f"❌ {usuario.display_name} no tiene un DNI aprobado.", ephemeral=True)
        
        dni_number, full_name, dob, sex, nationality, photo_url = result
        
        embed = discord.Embed(title="Documento Nacional de Identidad", color=0x3498db)
        embed.set_author(name=f"República de {interaction.guild.name}", icon_url=interaction.guild.icon.url)
        embed.set_thumbnail(url=photo_url)
        
        embed.add_field(name="Apellidos y Nombre", value=f"**{full_name}**", inline=False)
        embed.add_field(name="Nacionalidad", value=nationality, inline=True)
        embed.add_field(name="Sexo", value=sex, inline=True)
        embed.add_field(name="Fecha de Nacimiento", value=dob, inline=True)
        embed.add_field(name="Número de Documento", value=f"`{dni_number}`", inline=False)
        
        # Obtenemos la fecha de creación del mensaje original para simular una fecha de expedición
        # Esto es un detalle, si el mensaje se borra, no funcionaría.
        try:
            exp_date = interaction.message.created_at.strftime('%d/%m/%Y')
        except:
            exp_date = "17/06/2036"
            
        embed.set_footer(text=f"Expedido el {exp_date}")
        
        await interaction.response.send_message(embed=embed)

    @dni_group.command(name="borrar", description="[Admin] Elimina permanentemente el DNI de un usuario.")
    async def borrar_dni(self, interaction: discord.Interaction, usuario: discord.Member):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM dnis WHERE user_id = ? AND server_id = ?", (usuario.id, interaction.guild.id))
        self.db.commit()
        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ DNI de {usuario.mention} eliminado con éxito.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ {usuario.mention} no tenía un DNI para eliminar.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DNICog(bot))
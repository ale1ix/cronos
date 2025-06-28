# Guardar en: /cogs/justicia_cog.py (VERSIÓN SIMPLE Y DIRECTA)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime
from typing import Optional



# --- VISTA (Simplificada para evitar errores de inicialización) ---
class CategorizedChargeView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, sospechoso: discord.Member, foto_url: str, silent_response: bool):
        super().__init__(timeout=300)
        self.original_interaction = interaction; self.sospechoso = sospechoso; self.foto_url = foto_url
        self.silent_response = silent_response; self.all_selected_charge_codes = set()
        self.justicia_cog = interaction.client.get_cog('Justicia'); self.update_category_select()
        self.confirm_button.callback = self.confirm_button_callback
    def update_category_select(self):
        category_options = self.justicia_cog.get_categories_for_server(self.original_interaction.guild.id)
        if not category_options:
            self.category_select.placeholder = "¡No hay categorías configuradas!"; self.category_select.disabled = True
            self.category_select.options = [discord.SelectOption(label="Error", value="no_cat")]
        else:
            self.category_select.options = category_options; self.category_select.disabled = False
            self.category_select.placeholder = "Paso 1: Elige una categoría..."
    def update_charge_selects(self, category: str):
        components_to_keep = [self.category_select, self.display_button, self.confirm_button]; self.clear_items()
        for item in components_to_keep: self.add_item(item)
        all_charges = self.justicia_cog.get_charges_for_category(self.original_interaction.guild.id, category)
        if not all_charges: return
        chunked_charges = [all_charges[i:i + 25] for i in range(0, len(all_charges), 25)]
        for i, charge_chunk in enumerate(chunked_charges):
            select = discord.ui.Select(placeholder=f"Selecciona cargos de '{category}' (Pág. {i+1})", min_values=1, max_values=len(charge_chunk), options=charge_chunk, row=i + 1)
            select.callback = self.charge_select_callback; self.add_item(select)
            if i >= 3: break 
    @discord.ui.select(placeholder="Paso 1: Elige una categoría...", row=0)
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.original_interaction.user.id: return await interaction.response.send_message("No eres el agente.", ephemeral=True)
        self.update_charge_selects(select.values[0]); await interaction.response.edit_message(view=self)
    async def charge_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_interaction.user.id: return await interaction.response.send_message("No eres el agente.", ephemeral=True)
        for code in interaction.data['values']: self.all_selected_charge_codes.add(code)
        self.display_button.label = f"Cargos añadidos: {len(self.all_selected_charge_codes)}"; self.confirm_button.disabled = False
        await interaction.response.edit_message(view=self)
    display_button = discord.ui.Button(label="Cargos añadidos: 0", style=discord.ButtonStyle.secondary, disabled=True, row=4)
    confirm_button = discord.ui.Button(label="Confirmar", style=discord.ButtonStyle.success, emoji="✅", row=4, disabled=True)
    async def confirm_button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.original_interaction.user.id: return await interaction.response.send_message("No eres el agente.", ephemeral=True)
        if not self.all_selected_charge_codes: return await interaction.response.send_message("Debes seleccionar al menos un cargo.", ephemeral=True)
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(content="Procesando...", view=self)
        await self.justicia_cog.execute_processing(interaction, self.sospechoso, self.foto_url, list(self.all_selected_charge_codes), self.silent_response)

# --- COG PRINCIPAL DE JUSTICIA (sin cambios en la lógica interna) ---
class Justicia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')

        # --- FUNCIÓN DE PERMISOS ---
    async def has_permission(self, interaction: discord.Interaction, role_type: str) -> bool:
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog: return False
        return await config_cog.has_permission(interaction, role_type) or await config_cog.has_permission(interaction, 'admin')

    # --- FUNCIÓN DE CONFIGURACIÓN ---
    def get_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None

    async def has_permission(self, interaction: discord.Interaction, role_type: str) -> bool:
        cursor = self.db.cursor()
        cursor.execute("SELECT role_id FROM role_config WHERE server_id = ? AND role_type = ?", (interaction.guild.id, role_type))
        configured_roles_ids = {row[0] for row in cursor.fetchall()}
        cursor.close()
        if not configured_roles_ids: return False
        user_roles_ids = {role.id for role in interaction.user.roles}
        return not user_roles_ids.isdisjoint(configured_roles_ids)

    # ... (El resto del código del COG va aquí, es idéntico al de la respuesta anterior) ...
    def get_config(self, server_id: int, key: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?", (server_id, key))
        result = cursor.fetchone()
        return result[0] if result else None
        
    def get_categories_for_server(self, server_id: int):
        cursor = self.db.cursor()
        cursor.execute("SELECT DISTINCT category FROM server_charges WHERE server_id = ? ORDER BY category", (server_id,))
        return [discord.SelectOption(label=row[0]) for row in cursor.fetchall()]

    def get_charges_for_category(self, server_id: int, category: str):
        cursor = self.db.cursor()
        cursor.execute("SELECT charge_code, description, fine_amount FROM server_charges WHERE server_id = ? AND category = ?", (server_id, category))
        options = []
        for code, desc, amount in cursor.fetchall():
            options.append(discord.SelectOption(label=f"{code} (${amount:,})", description=desc[:100], value=code))
        return options

    cargos_group = app_commands.Group(name="cargos", description="Gestiona el código penal del servidor.")

    @cargos_group.command(name="añadir", description="[Admin] Añade un nuevo cargo al código penal.")
    async def cargos_añadir(self, interaction: discord.Interaction, categoria: str, codigo: str, descripcion: str, multa: int, notas: str = None):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        if not await self.has_permission(interaction, 'admin'):
            return await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO server_charges (server_id, category, charge_code, description, fine_amount, extra_notes) VALUES (?, ?, ?, ?, ?, ?)", (interaction.guild.id, categoria.strip(), codigo.strip(), descripcion, multa, notas))
        self.db.commit()
        await interaction.response.send_message(f"✅ Cargo `{codigo}` añadido a la categoría `{categoria}`.", ephemeral=True)

    @cargos_group.command(name="quitar", description="[Admin] Elimina un cargo del código penal.")
    async def cargos_quitar(self, interaction: discord.Interaction, codigo: str):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM server_charges WHERE server_id = ? AND charge_code = ?", (interaction.guild.id, codigo))
        self.db.commit()
        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Cargo `{codigo}` eliminado.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró ningún cargo con el código `{codigo}`.", ephemeral=True)

    @cargos_group.command(name="listar", description="[Policía] Muestra todos los cargos del código penal.")
    async def cargos_listar(self, interaction: discord.Interaction):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'police'):
            await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("SELECT category, charge_code, description, fine_amount, extra_notes FROM server_charges WHERE server_id = ? ORDER BY category, charge_code", (interaction.guild.id,))
        all_charges = cursor.fetchall()
        if not all_charges: return await interaction.response.send_message("No hay cargos configurados en este servidor.", ephemeral=True)
        embed = discord.Embed(title=f"Código Penal de {interaction.guild.name}", color=discord.Color.dark_blue())
        charges_by_category = {}
        for cat, code, desc, fine, notes in all_charges:
            if cat not in charges_by_category: charges_by_category[cat] = []
            charges_by_category[cat].append((code, desc, fine, notes))
        for category, charges in charges_by_category.items():
            field_value = "".join(f"**{c[0]}**: {c[1]} - **${c[2]:,}**{' (*' + c[3] + '*)' if c[3] else ''}\n" for c in charges)
            embed.add_field(name=f" Categoria: {category}", value=field_value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="procesar", description="[Policía] Procesa a un sospechoso con foto y cargos del código penal.")
    async def procesar(self, interaction: discord.Interaction, sospechoso: discord.Member, foto_detenido: discord.Attachment):
        if not await self.has_permission(interaction, 'police'):
            return await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
            
        # --- INICIO DE LA VALIDACIÓN AÑADIDA ---
        if sospechoso.id == interaction.user.id:
            return await interaction.response.send_message("❌ No puedes procesarte a ti mismo.", ephemeral=True)
        if sospechoso.id == self.bot.user.id:
            return await interaction.response.send_message("❌ No puedes procesar al bot.", ephemeral=True)
        # --- FIN DE LA VALIDACIÓN AÑADIDA ---

        if not foto_detenido.content_type or not foto_detenido.content_type.startswith('image/'):
            return await interaction.response.send_message("❌ El archivo adjunto debe ser una imagen.", ephemeral=True)
        
        view = CategorizedChargeView(interaction, sospechoso, foto_detenido.url, silent_response=False)
        await interaction.response.send_message(f"Iniciando procesamiento de **{sospechoso.display_name}**.", view=view, ephemeral=True)

    @app_commands.command(name="multar", description="[Policía] Aplica una multa rápida seleccionando cargos.")
    async def multar(self, interaction: discord.Interaction, sospechoso: discord.Member):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'police'):
            await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
            return
        
        # --- INICIO DE LA VALIDACIÓN AÑADIDA ---
        if sospechoso.id == interaction.user.id:
            return await interaction.response.send_message("❌ No puedes multarte a ti mismo.", ephemeral=True)
        if sospechoso.id == self.bot.user.id:
            return await interaction.response.send_message("❌ No puedes multar al bot.", ephemeral=True)
        # --- FIN DE LA VALIDACIÓN AÑADIDA ---

        foto_url_generica = "https://i.imgur.com/UfxhVd2.png" 
        view = CategorizedChargeView(interaction, sospechoso, foto_url_generica, silent_response=True)
        await interaction.response.send_message(f"Iniciando multa rápida para **{sospechoso.display_name}**.", view=view, ephemeral=True)

    # ... (el resto de los comandos como ver-multas, mis-multas, etc.) ...


    multas_group = app_commands.Group(name="multas", description="Gestiona tus multas personales.")

    @multas_group.command(name="ver", description="Revisa tus multas pendientes de pago.")
    async def ver_multas(self, interaction: discord.Interaction, ciudadano: discord.Member):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'police'):
            await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("SELECT multa_id, cantidad, delito, fecha FROM multas_activas WHERE user_id = ? ORDER BY fecha ASC", (ciudadano.id,))
        multas = cursor.fetchall()
        if not multas: return await interaction.response.send_message(f"{ciudadano.display_name} no tiene multas pendientes.", ephemeral=True)
        embed = discord.Embed(title=f"Multas Pendientes de {ciudadano.display_name}", color=discord.Color.red())
        for multa_id, cantidad, delito, fecha_str in multas:
            fecha_dt = datetime.datetime.fromisoformat(fecha_str)
            embed.add_field(name=f"ID Multa #{multa_id} | 💵 ${cantidad:,}", value=f"**Delito:** {delito}\n**Fecha:** <t:{int(fecha_dt.timestamp())}:D>", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)


    @multas_group.command(name="pagar", description="Paga una de tus multas pendientes usando su ID.")
    async def pagar_multa(self, interaction: discord.Interaction, id_multa: int):
        cursor = self.db.cursor()
        economia_cog = self.bot.get_cog('Economia')
        if not economia_cog: return await interaction.response.send_message("Error: El sistema de economía no funciona.", ephemeral=True)
        
        cursor.execute("SELECT cantidad FROM multas_activas WHERE multa_id = ? AND user_id = ?", (id_multa, interaction.user.id))
        multa = cursor.fetchone()
        if not multa: return await interaction.response.send_message("No se encontró una multa con ese ID a tu nombre.", ephemeral=True)
        
        cantidad = multa[0]
        if await economia_cog.modificar_dinero(interaction.user.id, -cantidad, tipo='limpio'):
            # 1. Borramos la multa activa, porque ya no lo está
            cursor.execute("DELETE FROM multas_activas WHERE multa_id = ?", (id_multa,))
            # 2. ACTUALIZAMOS el antecedente vinculado a esta multa a 'Pagada'
            cursor.execute("UPDATE antecedentes SET status = 'Pagada' WHERE multa_id = ?", (id_multa,))
            self.db.commit()
            await interaction.response.send_message(f"✅ Has pagado la multa #{id_multa} por un total de ${cantidad:,}. Tu historial ha sido actualizado.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No tienes suficiente dinero limpio para pagar esta multa de ${cantidad:,}.", ephemeral=True)

    antecedentes_group = app_commands.Group(name="antecedentes", description="Gestiona los antecedentes de los ciudadanos.")

    @antecedentes_group.command(name="ver", description="[Policía] Revisa el historial delictivo de un ciudadano.")
    async def antecedentes_ver(self, interaction: discord.Interaction, ciudadano: discord.Member):
        if not await self.has_permission(interaction, 'police'):
            return await interaction.response.send_message("🚫 No tienes permisos para usar este comando.", ephemeral=True)
        
        cursor = self.db.cursor()
        cursor.execute("SELECT antecedente_id, tipo_infraccion, descripcion, fecha, status FROM antecedentes WHERE user_id = ? ORDER BY fecha DESC", (ciudadano.id,))
        records = cursor.fetchall()
        
        if not records:
            return await interaction.response.send_message(f"{ciudadano.display_name} tiene un historial limpio.", ephemeral=True)
        
        embed = discord.Embed(title=f"Historial de Antecedentes de {ciudadano.display_name}", color=discord.Color.dark_grey())
        embed.set_thumbnail(url=ciudadano.display_avatar.url)
        
        for rec_id,tipo,desc,fecha_str,status in records:
            fecha_dt = datetime.datetime.fromisoformat(fecha_str) # Volvemos a convertir el texto a fecha
            s_emoji="✅ Pagada" if status=='Pagada' else "🔴 Pendiente"
            embed.add_field(name=f"🆔 `{rec_id}` | {tipo} | <t:{int(fecha_dt.timestamp())}:D>",value=f"**Cargos:**\n{desc}\n**Estado:** {s_emoji}",inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @antecedentes_group.command(name="borrar", description="[Admin] Borra uno o todos los antecedentes de un ciudadano.")
    async def antecedentes_borrar(self, interaction: discord.Interaction, ciudadano: discord.Member, id_antecedente: Optional[int] = None):
        if not await self.has_permission(interaction, 'admin'):
            return await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)

        cursor = self.db.cursor()
        if id_antecedente:
            # Borrar un antecedente específico
            cursor.execute("DELETE FROM antecedentes WHERE user_id = ? AND antecedente_id = ?", (ciudadano.id, id_antecedente))
            if cursor.rowcount > 0:
                self.db.commit()
                await interaction.response.send_message(f"✅ Antecedente #{id_antecedente} borrado del historial de {ciudadano.mention}.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ No se encontró el antecedente #{id_antecedente} para {ciudadano.mention}.", ephemeral=True)
        else:
            # Borrar todos los antecedentes
            cursor.execute("DELETE FROM antecedentes WHERE user_id = ?", (ciudadano.id,))
            if cursor.rowcount > 0:
                self.db.commit()
                await interaction.response.send_message(f"✅ Historial completo de antecedentes de {ciudadano.mention} ha sido limpiado.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {ciudadano.mention} no tenía antecedentes para borrar.", ephemeral=True)


    # --- Lógica de Procesamiento (Actualizada) ---

    async def execute_processing(self, interaction: discord.Interaction, sospechoso: discord.Member, foto_url: str, charge_codes: list, silent_response: bool):
        cursor = self.db.cursor()
        placeholders = ','.join('?' for _ in charge_codes)
        query = f"SELECT charge_code, description, fine_amount FROM server_charges WHERE server_id = ? AND charge_code IN ({placeholders})"
        params = [interaction.guild.id] + charge_codes
        cursor.execute(query, params)
        charges_details = cursor.fetchall()
        total_multa = sum(charge[2] for charge in charges_details)
        
        razon_antecedente = "".join(f"- {c[0]}: {c[1]} (${c[2]:,})\n" for c in charges_details)
        tipo_infraccion = "Multa" if silent_response else "Arresto" # Multa si es /multar, Arresto si es /procesar

        if not silent_response:
            razon_str_embed = "".join(f"**{c[0]}** - {c[1]}: **${c[2]:,}**\n" for c in charges_details)
            embed = discord.Embed(title=f"📥 {sospechoso.display_name} ha sido procesado", description=f"**Detenido:** {sospechoso.mention}\n**Agente:** {interaction.user.mention}\n\n**Cargos:**\n{razon_str_embed}", color=0x4a4d53)
            embed.set_thumbnail(url=foto_url)
            records_channel_id = self.get_config(interaction.guild.id, 'justice_records_channel')
            if channel := self.bot.get_channel(records_channel_id if records_channel_id else 0): await channel.send(embed=embed)

        if total_multa > 0:
            now = datetime.datetime.now(datetime.timezone.utc)
            # 1. Añadimos la multa activa
            cursor.execute("INSERT INTO multas_activas (user_id, officer_id, delito, cantidad, fecha) VALUES (?, ?, ?, ?, ?)", (sospechoso.id, interaction.user.id, f"Cargos ({tipo_infraccion})", total_multa, now))
            new_multa_id = cursor.lastrowid # ¡Obtenemos el ID de la multa que acabamos de crear!

            # 2. Creamos el antecedente y lo vinculamos con el ID de la multa
            cursor.execute("INSERT INTO antecedentes (user_id, multa_id, tipo_infraccion, descripcion, fecha, status) VALUES (?, ?, ?, ?, ?, ?)", 
                           (sospechoso.id, new_multa_id, tipo_infraccion, razon_antecedente.strip(), now, 'Pendiente'))
            
            self.db.commit()
            try:
                razones_str_simple = ", ".join([f"`{c[0]}`" for c in charges_details])
                await sospechoso.send(f"Has sido sancionado en **{interaction.guild.name}** con una multa de **${total_multa:,}** por los siguientes cargos: {razones_str_simple}. Revisa tus multas pendientes.")
            except discord.Forbidden: pass

        await interaction.followup.send(f"✅ **{sospechoso.display_name}** ha sido procesado ({tipo_infraccion}) y multado con **${total_multa:,}**. Su historial ha sido actualizado.", ephemeral=False)

# --- Setup del Cog ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Justicia(bot))
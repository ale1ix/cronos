# Guardar en: /cogs/economia_cog.py (VERSIÓN CORREGIDA Y FUNCIONAL)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import datetime
from typing import Optional

# --- Función de Autocompletado para Propiedades (Puede estar fuera de la clase) ---
async def property_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    db = sqlite3.connect('cronos_rp.db')
    cursor = db.cursor()
    query = "SELECT propiedad_id, nombre_calle FROM propiedades WHERE server_id = ? AND (CAST(propiedad_id AS TEXT) LIKE ? OR nombre_calle LIKE ?)"
    cursor.execute(query, (interaction.guild.id, f'%{current}%', f'%{current}%'))
    properties = cursor.fetchall()
    db.close()
    return [
        app_commands.Choice(name=f"#{prop[0]} - {prop[1]}", value=str(prop[0]))
        for prop in properties
    ][:25]


class Economia(commands.Cog):
    """Cog para gestionar la economía: balances, pagos y reclamo de sueldos."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        self.db.row_factory = sqlite3.Row

    # --- GRUPOS DE COMANDOS (DEFINIDOS DENTRO DE LA CLASE) ---
    sueldos = app_commands.Group(name="sueldos", description="Configura los ingresos reclamables del servidor.")
    rol_subgroup = app_commands.Group(name="rol", parent=sueldos, description="Gestiona los sueldos por rol.")
    propiedad_subgroup = app_commands.Group(name="propiedad", parent=sueldos, description="Gestiona los ingresos por propiedad.")


    # --- MÉTODOS INTERNOS Y DE AYUDA ---

    async def has_admin_permission(self, interaction: discord.Interaction) -> bool:
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog: 
            print("ERROR CRÍTICO: No se pudo acceder a ConfigCog desde EconomiaCog.")
            return False
        return await config_cog.has_permission(interaction, 'admin')

    async def ensure_user_exists(self, user_id: int):
        cursor = self.db.cursor()
        cursor.execute("SELECT user_id FROM economia WHERE user_id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO economia (user_id, dinero_limpio, dinero_sucio) VALUES (?, 1000, 0)", (user_id,))
            self.db.commit()

    async def get_balance(self, user_id: int):
        await self.ensure_user_exists(user_id)
        cursor = self.db.cursor()
        cursor.execute("SELECT dinero_limpio, dinero_sucio FROM economia WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

    async def modificar_dinero(self, user_id: int, cantidad: int, tipo: str = 'limpio') -> bool:
        await self.ensure_user_exists(user_id)
        balance = await self.get_balance(user_id)
        columna_db = 'dinero_limpio' if tipo == 'limpio' else 'dinero_sucio'
        dinero_actual = balance[columna_db]
        if dinero_actual + cantidad < 0:
            return False
        cursor = self.db.cursor()
        cursor.execute(f"UPDATE economia SET {columna_db} = {columna_db} + ? WHERE user_id = ?", (cantidad, user_id))
        self.db.commit()
        return True

    def check_cooldown(self, config_row, current_time: datetime.datetime):
        """Verifica el cooldown de un ingreso y devuelve el estado y tiempo restante."""
        last_paid = config_row['last_paid_timestamp']
        interval_hours = config_row['payout_interval_hours']
        
        # --- CORRECCIÓN CLAVE ---
        # Si la fecha de la DB es "naive" (sin zona horaria), la hacemos "aware" (UTC) para poder compararla.
        if last_paid and last_paid.tzinfo is None:
            last_paid = last_paid.replace(tzinfo=datetime.timezone.utc)
        # --- FIN DE LA CORRECCIÓN ---
        
        if not last_paid or (current_time - last_paid).total_seconds() >= interval_hours * 3600:
            return True, "0h 0m"
        else:
            remaining_seconds = (interval_hours * 3600) - (current_time - last_paid).total_seconds()
            hours, rem = divmod(remaining_seconds, 3600)
            minutes, _ = divmod(rem, 60)
            return False, f"{int(hours)}h {int(minutes)}m"

    # --- COMANDOS DE USUARIO ---

    @app_commands.command(name="dinero", description="Consulta tu cartera o la de otro usuario.")
    async def dinero(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target_user = usuario or interaction.user
        balance = await self.get_balance(target_user.id)
        embed = discord.Embed(title=f"Cartera de {target_user.display_name}", color=discord.Color.from_rgb(255, 200, 0))
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="💵 Dinero Limpio", value=f"${balance['dinero_limpio']:,}", inline=True)
        embed.add_field(name="💰 Dinero Sucio", value=f"${balance['dinero_sucio']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pagar", description="Paga a otro ciudadano con tu dinero limpio.")
    async def pagar(self, interaction: discord.Interaction, destinatario: discord.Member, cantidad: int):
        if cantidad <= 0: return await interaction.response.send_message("❌ La cantidad debe ser positiva.", ephemeral=True)
        if destinatario.id == interaction.user.id: return await interaction.response.send_message("❌ No te puedes pagar a ti mismo.", ephemeral=True)
        if destinatario.bot: return await interaction.response.send_message("❌ No puedes pagarle a un bot.", ephemeral=True)
        
        if not await self.modificar_dinero(interaction.user.id, -cantidad): 
            return await interaction.response.send_message(f"❌ No tienes suficiente dinero. Necesitas ${cantidad:,}.", ephemeral=True)
        
        await self.modificar_dinero(destinatario.id, cantidad)
        await interaction.response.send_message(f"✅ Has pagado ${cantidad:,} a {destinatario.mention}.")

    @app_commands.command(name="sueldo", description="Reclama todos tus ingresos disponibles de roles y propiedades.")
    async def sueldo_reclamar(self, interaction: discord.Interaction):
        current_time = datetime.datetime.now(datetime.timezone.utc)
        cursor = self.db.cursor()
        total_payout = 0
        claimed_incomes, cooldown_incomes = [], []

        # 1. Procesar Sueldos por Rol
        user_role_ids = {role.id for role in interaction.user.roles}
        if user_role_ids:
            query = f"SELECT * FROM role_salaries WHERE server_id = ? AND role_id IN ({','.join('?' for _ in user_role_ids)})"
            params = (interaction.guild.id,) + tuple(user_role_ids)
            cursor.execute(query, params)

            for salary_config in cursor.fetchall():
                role = interaction.guild.get_role(salary_config['role_id'])
                if not role: continue
                
                is_ready, rem_time = self.check_cooldown(salary_config, current_time)
                
                if is_ready:
                    total_payout += salary_config['salary_amount']
                    claimed_incomes.append(f"✅ **${salary_config['salary_amount']:,}** (del rol {role.mention})")
                    cursor.execute("UPDATE role_salaries SET last_paid_timestamp = ? WHERE server_id = ? AND role_id = ?", (current_time, interaction.guild.id, role.id))
                else:
                    cooldown_incomes.append(f"⏳ **${salary_config['salary_amount']:,}** (del rol {role.mention}) - Faltan **{rem_time}**")

        # 2. Procesar Ingresos por Propiedades
        cursor.execute("SELECT * FROM propiedades WHERE propietario_id = ? AND ingreso_pasivo > 0", (interaction.user.id,))
        for prop in cursor.fetchall():
            is_ready, rem_time = self.check_cooldown(prop, current_time)
            if is_ready:
                total_payout += prop['ingreso_pasivo']
                claimed_incomes.append(f"✅ **${prop['ingreso_pasivo']:,}** (de '{prop['nombre_calle']}')")
                cursor.execute("UPDATE propiedades SET last_paid_timestamp = ? WHERE propiedad_id = ?", (current_time, prop['propiedad_id']))
            else:
                cooldown_incomes.append(f"⏳ **${prop['ingreso_pasivo']:,}** (de '{prop['nombre_calle']}') - Faltan **{rem_time}**")

        # 3. Realizar Pago y Enviar Respuesta
        embed = discord.Embed(title=f"💸 Reclamo de Sueldo de {interaction.user.display_name}", color=discord.Color.green())
        if total_payout > 0:
            await self.modificar_dinero(interaction.user.id, total_payout)
            embed.description = f"**¡Has reclamado un total de `${total_payout:,}`!**"
            if claimed_incomes:
                embed.add_field(name="Ingresos Reclamados Ahora", value="\n".join(claimed_incomes), inline=False)
        else:
            embed.description = "No tenías ningún ingreso listo para reclamar."
            embed.color = discord.Color.orange()
        if cooldown_incomes:
            embed.add_field(name="Próximos Ingresos (En Espera)", value="\n".join(cooldown_incomes), inline=False)
        
        self.db.commit()
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # --- COMANDOS DE ADMINISTRACIÓN DE SUELDOS ---

    @rol_subgroup.command(name="establecer", description="[Admin] Establece el sueldo y el intervalo de pago para un rol.")
    async def sueldo_rol_set(self, interaction: discord.Interaction, rol: discord.Role, cantidad: int, intervalo_horas: int):
        if not await self.has_admin_permission(interaction): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        if cantidad < 0 or intervalo_horas <= 0: return await interaction.response.send_message("❌ La cantidad y el intervalo deben ser positivos.", ephemeral=True)
        
        cursor = self.db.cursor()
        cursor.execute("REPLACE INTO role_salaries (server_id, role_id, salary_amount, payout_interval_hours, last_paid_timestamp) VALUES (?, ?, ?, ?, ?)",
                       (interaction.guild.id, rol.id, cantidad, intervalo_horas, None))
        self.db.commit()
        await interaction.response.send_message(f"✅ Sueldo establecido para {rol.mention}:\n- **Cantidad:** ${cantidad:,}\n- **Frecuencia:** Cada {intervalo_horas} horas.", ephemeral=True)

    @rol_subgroup.command(name="quitar", description="[Admin] Quita el sueldo de un rol.")
    async def sueldo_rol_remove(self, interaction: discord.Interaction, rol: discord.Role):
        if not await self.has_admin_permission(interaction): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM role_salaries WHERE server_id = ? AND role_id = ?", (interaction.guild.id, rol.id))
        self.db.commit()
        await interaction.response.send_message(f"✅ Sueldo para {rol.mention} eliminado." if cursor.rowcount > 0 else "❌ Ese rol no tenía sueldo.", ephemeral=True)

    @rol_subgroup.command(name="ver", description="[Admin] Muestra todos los sueldos por rol configurados.")
    async def sueldo_rol_view(self, interaction: discord.Interaction):
        if not await self.has_admin_permission(interaction): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM role_salaries WHERE server_id = ?", (interaction.guild.id,))
        salaries = cursor.fetchall()
        if not salaries: return await interaction.response.send_message("No hay sueldos por rol configurados.", ephemeral=True)
        
        embed = discord.Embed(title="Sueldos por Rol Configurados", color=discord.Color.gold())
        desc = []
        for s in salaries:
            role = interaction.guild.get_role(s['role_id'])
            if role:
                last_paid_str = f"<t:{int(s['last_paid_timestamp'].timestamp())}:R>" if s['last_paid_timestamp'] else 'Nunca'
                desc.append(f"**{role.mention}**: ${s['salary_amount']:,} cada {s['payout_interval_hours']}h (Último pago: {last_paid_str})")
        
        embed.description = "\n".join(desc) if desc else "No hay roles configurados válidos."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @propiedad_subgroup.command(name="establecer", description="[Admin] Establece el ingreso y el intervalo para una propiedad.")
    @app_commands.autocomplete(propiedad_id=property_autocomplete)
    async def sueldo_prop_set(self, interaction: discord.Interaction, propiedad_id: str, ingreso: int, intervalo_horas: int):
        if not await self.has_admin_permission(interaction): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        if ingreso < 0 or intervalo_horas <= 0: return await interaction.response.send_message("❌ El ingreso y el intervalo deben ser positivos.", ephemeral=True)
        
        cursor = self.db.cursor()
        prop = cursor.execute("SELECT tipo, nombre_calle FROM propiedades WHERE propiedad_id = ?", (int(propiedad_id),)).fetchone()
        if not prop: return await interaction.response.send_message("❌ No se encontró una propiedad con ese ID.", ephemeral=True)
        
        cursor.execute("UPDATE propiedades SET ingreso_pasivo = ?, payout_interval_hours = ? WHERE propiedad_id = ?", (ingreso, intervalo_horas, int(propiedad_id)))
        self.db.commit()
        await interaction.response.send_message(f"✅ Ingreso para la propiedad **#{propiedad_id}** ('{prop['nombre_calle']}') establecido en **${ingreso:,}** cada **{intervalo_horas} horas**.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economia(bot))
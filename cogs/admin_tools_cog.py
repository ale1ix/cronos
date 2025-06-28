# Guardar en: /cogs/admin_tools_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3

class AdminTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        self.economia_cog = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.economia_cog = self.bot.get_cog('Economia')
        if self.economia_cog:
            print(" -> Módulo de AdminTools conectado con Economía.")
        else:
            print("ERROR CRÍTICO: AdminTools no pudo conectarse con el módulo de Economía.")

    async def check_economia(self, interaction: discord.Interaction) -> bool:
        if not self.economia_cog:
            self.economia_cog = self.bot.get_cog('Economia')
            if not self.economia_cog:
                await interaction.response.send_message("❌ **Error Crítico:** El sistema de economía no responde.", ephemeral=True)
                return False
        return True

    @app_commands.command(name="dar_dinero", description="[Admin] Añade dinero (limpio o sucio) a un usuario.")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="💵 Limpio", value="limpio"),
        app_commands.Choice(name="💰 Sucio", value="sucio"),
    ])
    async def dar_dinero(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int, tipo: str):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        if not await self.check_economia(interaction): return
        if cantidad <= 0:
            return await interaction.response.send_message("La cantidad debe ser positiva.", ephemeral=True)
        
        await self.economia_cog.modificar_dinero(usuario.id, cantidad, tipo=tipo)
        await interaction.response.send_message(f"✅ Se han añadido **${cantidad:,}** de dinero **{tipo}** a {usuario.mention}.", ephemeral=True)

    @app_commands.command(name="quitar_dinero", description="[Admin] Quita dinero (limpio o sucio) a un usuario.")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="💵 Limpio", value="limpio"),
        app_commands.Choice(name="💰 Sucio", value="sucio"),
    ])
    async def quitar_dinero(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int, tipo: str):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        if not await self.check_economia(interaction): return
        if cantidad <= 0:
            return await interaction.response.send_message("La cantidad debe ser positiva.", ephemeral=True)

        if not await self.economia_cog.modificar_dinero(usuario.id, -cantidad, tipo=tipo):
            await interaction.response.send_message(f"❌ La operación falló. {usuario.mention} no tiene suficiente dinero {tipo}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Se han quitado **${cantidad:,}** de dinero **{tipo}** a {usuario.mention}.", ephemeral=True)

    @app_commands.command(name="quitar_multa", description="[Admin] Elimina una multa activa usando su ID.")
    async def quitar_multa(self, interaction: discord.Interaction, id_multa: int):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM multas_activas WHERE multa_id = ?", (id_multa,))
        self.db.commit()

        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Multa #{id_multa} eliminada.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró multa activa con ID #{id_multa}.", ephemeral=True)

    @app_commands.command(name="transferir_propiedad", description="[Admin] Da una propiedad a un usuario.")
    async def transferir_propiedad(self, interaction: discord.Interaction, id_propiedad: int, nuevo_propietario: discord.Member):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("UPDATE propiedades SET propietario_id = ?, en_venta = FALSE WHERE propiedad_id = ?", (nuevo_propietario.id, id_propiedad))
        self.db.commit()

        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Propiedad #{id_propiedad} ahora pertenece a {nuevo_propietario.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró una propiedad con el ID #{id_propiedad}.", ephemeral=True)

    @app_commands.command(name="despojar_propiedad", description="[Admin] Quita una propiedad a su dueño y la pone en venta.")
    async def despojar_propiedad(self, interaction: discord.Interaction, id_propiedad: int):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        cursor = self.db.cursor()
        cursor.execute("UPDATE propiedades SET propietario_id = NULL, en_venta = TRUE WHERE propiedad_id = ?", (id_propiedad,))
        self.db.commit()

        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Propiedad #{id_propiedad} despojada y en el mercado.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No se encontró una propiedad con el ID #{id_propiedad}.", ephemeral=True)

    @app_commands.command(name="blanquear_dinero", description="[Admin] Blanquea dinero sucio para un usuario con comisión.")
    async def blanquear_dinero(self, interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog or not await config_cog.has_permission(interaction, 'admin'):
            await interaction.response.send_message("🚫 No tienes permisos de administrador para usar este comando.", ephemeral=True)
            return
        if not await self.check_economia(interaction): return
        
        balance = await self.economia_cog.get_balance(usuario.id)
        dinero_sucio_usuario = balance[1]

        if cantidad <= 0:
            return await interaction.response.send_message("La cantidad debe ser positiva.", ephemeral=True)
        if cantidad > dinero_sucio_usuario:
            return await interaction.response.send_message(f"❌ {usuario.mention} solo tiene ${dinero_sucio_usuario:,} de dinero sucio.", ephemeral=True)
        
        if not await self.economia_cog.modificar_dinero(usuario.id, -cantidad, tipo='sucio'):
            return await interaction.response.send_message(f"❌ Error al quitar el dinero sucio de {usuario.mention}.", ephemeral=True)
        
        comision = int(cantidad * 0.25)
        dinero_lavado = cantidad - comision

        await self.economia_cog.modificar_dinero(usuario.id, dinero_lavado, tipo='limpio')
        await self.economia_cog.modificar_dinero(interaction.user.id, comision, tipo='limpio')
        
        embed = discord.Embed(title="Blanqueo de Capitales Completado", color=discord.Color.dark_green())
        embed.add_field(name="Resultado para el Usuario", value=f"Recibe: **${dinero_lavado:,}** (limpio)", inline=True)
        embed.add_field(name="Resultado para Ti", value=f"Recibes: **${comision:,}** (comisión)", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminTools(bot))
# Guardar en: /cogs/shop_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from typing import Optional

# --- Función de Autocompletado para Items ---
async def item_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    db = sqlite3.connect('cronos_rp.db')
    cursor = db.cursor()
    cursor.execute("SELECT name FROM shop_items WHERE server_id = ? AND name LIKE ?", (interaction.guild.id, f'%{current}%'))
    items = cursor.fetchall()
    db.close()
    return [app_commands.Choice(name=item[0], value=item[0]) for item in items][:25]

class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        self.economia_cog = self.bot.get_cog('Economia')
        if not self.economia_cog:
            print("ADVERTENCIA: ShopCog no pudo conectar con Economia en el arranque.")

    @commands.Cog.listener()
    async def on_ready(self):
        # Aseguramos la conexión con Economía una vez que todos los cogs están cargados
        if not self.economia_cog:
            self.economia_cog = self.bot.get_cog('Economia')
            if self.economia_cog:
                print(" -> Módulo de Tienda conectado con Economía.")

    async def has_admin_permission(self, interaction: discord.Interaction) -> bool:
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog: return False
        return await config_cog.has_permission(interaction, 'admin')

    # --- Grupo de Comandos para el Usuario ---
    tienda = app_commands.Group(name="tienda", description="Interactúa con la tienda del servidor.")

    @tienda.command(name="ver", description="Muestra los objetos disponibles en la tienda.")
    async def tienda_ver(self, interaction: discord.Interaction):
        cursor = self.db.cursor()
        cursor.execute("SELECT name, description, price, stock FROM shop_items WHERE server_id = ?", (interaction.guild.id,))
        items = cursor.fetchall()

        if not items:
            return await interaction.response.send_message("La tienda está vacía en este momento.", ephemeral=True)

        embed = discord.Embed(title=f"🏪 Tienda de {interaction.guild.name}", color=discord.Color.blurple())
        for name, description, price, stock in items:
            stock_text = f"Stock: {stock}" if stock != -1 else "Stock: ∞ (infinito)"
            embed.add_field(
                name=f"{name} - `${price:,}`",
                value=f"_{description or 'Sin descripción.'}_\n**{stock_text}**",
                inline=False
            )
        embed.set_footer(text="Usa /tienda comprar para adquirir un objeto.")
        await interaction.response.send_message(embed=embed)

    @tienda.command(name="comprar", description="Compra un objeto de la tienda.")
    @app_commands.autocomplete(nombre=item_autocomplete)
    async def tienda_comprar(self, interaction: discord.Interaction, nombre: str, cantidad: int = 1):
        if cantidad <= 0:
            return await interaction.response.send_message("La cantidad debe ser mayor que cero.", ephemeral=True)

        cursor = self.db.cursor()
        cursor.execute("SELECT item_id, price, stock FROM shop_items WHERE server_id = ? AND name = ?", (interaction.guild.id, nombre))
        item = cursor.fetchone()

        if not item:
            return await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
        
        item_id, price, stock = item
        total_cost = price * cantidad

        if stock != -1 and stock < cantidad:
            return await interaction.response.send_message(f"No hay suficiente stock para comprar {cantidad} de '{nombre}'. Solo quedan {stock}.", ephemeral=True)

        # Transacción económica
        if not await self.economia_cog.modificar_dinero(interaction.user.id, -total_cost):
            return await interaction.response.send_message(f"No tienes suficiente dinero. Necesitas `${total_cost:,}`.", ephemeral=True)

        # Actualizar stock si no es infinito
        if stock != -1:
            cursor.execute("UPDATE shop_items SET stock = stock - ? WHERE item_id = ?", (cantidad, item_id))
        
        # Añadir objeto al inventario
        cursor.execute("SELECT quantity FROM user_inventories WHERE user_id = ? AND item_id = ?", (interaction.user.id, item_id))
        user_item = cursor.fetchone()
        if user_item:
            cursor.execute("UPDATE user_inventories SET quantity = quantity + ? WHERE user_id = ? AND item_id = ?", (cantidad, interaction.user.id, item_id))
        else:
            cursor.execute("INSERT INTO user_inventories (server_id, user_id, item_id, quantity) VALUES (?, ?, ?, ?)", (interaction.guild.id, interaction.user.id, item_id, cantidad))
        
        self.db.commit()
        await interaction.response.send_message(f"¡Has comprado **{cantidad}x {nombre}** por un total de **${total_cost:,}**!")

    @app_commands.command(name="inventario", description="Muestra tu inventario o el de otro usuario.")
    async def inventario(self, interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target_user = usuario or interaction.user
        
        embed = discord.Embed(title=f"🎒 Inventario de {target_user.display_name}", color=discord.Color.green())
        embed.set_thumbnail(url=target_user.display_avatar.url)

        # 1. Obtener objetos del inventario
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT si.name, ui.quantity 
            FROM user_inventories ui
            JOIN shop_items si ON ui.item_id = si.item_id
            WHERE ui.user_id = ? AND ui.server_id = ?
        """, (target_user.id, interaction.guild.id))
        items = cursor.fetchall()
        
        item_list = "\n".join([f"- **{quantity}x** {name}" for name, quantity in items]) if items else "No tiene objetos."
        embed.add_field(name="Objetos", value=item_list, inline=False)

        # 2. Obtener propiedades
        cursor.execute("SELECT propiedad_id, tipo, nombre_calle FROM propiedades WHERE propietario_id = ?", (target_user.id,))
        properties = cursor.fetchall()

        prop_list = "\n".join([f"- **{tipo} #{prop_id}**: {nombre_calle}" for prop_id, tipo, nombre_calle in properties]) if properties else "No tiene propiedades."
        embed.add_field(name="Propiedades", value=prop_list, inline=False)
        
        await interaction.response.send_message(embed=embed)

    # --- Grupo de Comandos para Administradores ---
    tienda_admin = app_commands.Group(name="tienda-admin", description="Comandos de administración de la tienda.")
    inventario_admin = app_commands.Group(name="inventario-admin", description="Comandos de administración de inventarios.")

    @tienda_admin.command(name="añadir", description="Añade un nuevo objeto a la tienda.")
    async def tienda_admin_añadir(self, interaction: discord.Interaction, nombre: str, precio: int, descripcion: str, stock: int = -1):
        if not await self.has_admin_permission(interaction):
            return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        if precio <= 0:
            return await interaction.response.send_message("El precio debe ser mayor que cero.", ephemeral=True)
        
        cursor = self.db.cursor()
        try:
            cursor.execute("INSERT INTO shop_items (server_id, name, description, price, stock) VALUES (?, ?, ?, ?, ?)",
                           (interaction.guild.id, nombre, descripcion, precio, stock))
            self.db.commit()
            await interaction.response.send_message(f"✅ Objeto '{nombre}' añadido a la tienda.", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message("❌ Ya existe un objeto con ese nombre.", ephemeral=True)

    @tienda_admin.command(name="quitar", description="Quita un objeto de la tienda permanentemente.")
    @app_commands.autocomplete(nombre=item_autocomplete)
    async def tienda_admin_quitar(self, interaction: discord.Interaction, nombre: str):
        if not await self.has_admin_permission(interaction):
            return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM shop_items WHERE server_id = ? AND name = ?", (interaction.guild.id, nombre))
        self.db.commit()
        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Objeto '{nombre}' eliminado de la tienda.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No se encontró un objeto con ese nombre.", ephemeral=True)

    @tienda_admin.command(name="modificar", description="Modifica un objeto existente en la tienda.")
    @app_commands.autocomplete(nombre=item_autocomplete)
    async def tienda_admin_modificar(self, interaction: discord.Interaction, nombre: str, nuevo_precio: Optional[int] = None, nuevo_stock: Optional[int] = None, nueva_descripcion: Optional[str] = None):
        if not await self.has_admin_permission(interaction):
            return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        if all(arg is None for arg in [nuevo_precio, nuevo_stock, nueva_descripcion]):
            return await interaction.response.send_message("Debes proporcionar al menos un campo para modificar.", ephemeral=True)

        updates = []
        params = []
        if nuevo_precio is not None:
            updates.append("price = ?")
            params.append(nuevo_precio)
        if nuevo_stock is not None:
            updates.append("stock = ?")
            params.append(nuevo_stock)
        if nueva_descripcion is not None:
            updates.append("description = ?")
            params.append(nueva_descripcion)
        
        params.extend([interaction.guild.id, nombre])
        cursor = self.db.cursor()
        cursor.execute(f"UPDATE shop_items SET {', '.join(updates)} WHERE server_id = ? AND name = ?", tuple(params))
        self.db.commit()

        if cursor.rowcount > 0:
            await interaction.response.send_message(f"✅ Objeto '{nombre}' actualizado.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No se encontró el objeto.", ephemeral=True)

    @inventario_admin.command(name="dar", description="Añade un objeto al inventario de un usuario.")
    @app_commands.autocomplete(nombre_objeto=item_autocomplete)
    async def inv_admin_dar(self, interaction: discord.Interaction, usuario: discord.Member, nombre_objeto: str, cantidad: int = 1):
        if not await self.has_admin_permission(interaction):
            return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        
        cursor = self.db.cursor()
        cursor.execute("SELECT item_id FROM shop_items WHERE server_id = ? AND name = ?", (interaction.guild.id, nombre_objeto))
        item = cursor.fetchone()
        if not item:
            return await interaction.response.send_message("❌ Ese objeto no existe en la tienda.", ephemeral=True)
        
        item_id = item[0]
        cursor.execute("SELECT quantity FROM user_inventories WHERE user_id = ? AND item_id = ?", (usuario.id, item_id))
        user_item = cursor.fetchone()
        if user_item:
            cursor.execute("UPDATE user_inventories SET quantity = quantity + ? WHERE user_id = ? AND item_id = ?", (cantidad, usuario.id, item_id))
        else:
            cursor.execute("INSERT INTO user_inventories (server_id, user_id, item_id, quantity) VALUES (?, ?, ?, ?)", (interaction.guild.id, usuario.id, item_id, cantidad))
        
        self.db.commit()
        await interaction.response.send_message(f"✅ Se han añadido **{cantidad}x {nombre_objeto}** al inventario de {usuario.mention}.", ephemeral=True)

    @inventario_admin.command(name="quitar", description="Quita objetos del inventario de un usuario.")
    @app_commands.autocomplete(nombre_objeto=item_autocomplete)
    async def inv_admin_quitar(self, interaction: discord.Interaction, usuario: discord.Member, nombre_objeto: str, cantidad: int = 1):
        if not await self.has_admin_permission(interaction):
            return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)

        cursor = self.db.cursor()
        cursor.execute("SELECT i.item_id, ui.quantity FROM user_inventories ui JOIN shop_items i ON ui.item_id = i.item_id WHERE ui.user_id = ? AND i.name = ?", (usuario.id, nombre_objeto))
        user_item = cursor.fetchone()

        if not user_item:
            return await interaction.response.send_message(f"{usuario.mention} no tiene '{nombre_objeto}' en su inventario.", ephemeral=True)

        item_id, current_quantity = user_item
        if current_quantity < cantidad:
            return await interaction.response.send_message(f"No puedes quitar {cantidad} de '{nombre_objeto}', {usuario.mention} solo tiene {current_quantity}.", ephemeral=True)

        if current_quantity == cantidad:
            cursor.execute("DELETE FROM user_inventories WHERE user_id = ? AND item_id = ?", (usuario.id, item_id))
        else:
            cursor.execute("UPDATE user_inventories SET quantity = quantity - ? WHERE user_id = ? AND item_id = ?", (cantidad, usuario.id, item_id))

        self.db.commit()
        await interaction.response.send_message(f"✅ Se han quitado **{cantidad}x {nombre_objeto}** del inventario de {usuario.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
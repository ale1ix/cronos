# Guardar en: /cogs/propiedades_cog.py (VERSIÓN CORREGIDA Y FUNCIONAL)

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import math

# --- VISTA PARA EL MERCADO INMOBILIARIO (CON PAGINACIÓN MÚLTIPLE) ---
class PropertyMarketView(discord.ui.View):
    """
    Una vista interactiva para navegar por el mercado de propiedades
    con botones de anterior/siguiente y mostrando varias propiedades por página.
    """
    def __init__(self, properties: list, bot, items_per_page: int = 10):
        super().__init__(timeout=300)
        self.properties = properties
        self.bot = bot
        self.items_per_page = items_per_page
        self.current_page = 0
        self.total_pages = math.ceil(len(self.properties) / self.items_per_page)

    async def create_embed_for_page(self, page_index: int) -> discord.Embed:
        """Crea un embed con una lista de hasta 10 (o los definidos) propiedades."""
        
        embed = discord.Embed(
            title="🏡 Mercado Inmobiliario 🏙️",
            description="Usa los botones para navegar por las propiedades disponibles.",
            color=discord.Color.from_rgb(0, 151, 230)
        )
        
        start_index = page_index * self.items_per_page
        end_index = start_index + self.items_per_page
        properties_on_page = self.properties[start_index:end_index]
        
        property_list_text = []
        for prop in properties_on_page:
            if prop['en_venta']:
                price = prop['precio']
                seller_text = "(Estado)"
            else: # en_venta_por_jugador
                price = prop['precio_venta_jugador']
                seller_text = "(Jugador)"

            property_list_text.append(
                f"**ID #{prop['propiedad_id']}**: {prop['tipo']} en *{prop['nombre_calle']}*\n"
                f"└ **Precio: ${price:,}** {seller_text}"
            )
            
        if property_list_text:
            embed.add_field(name="Propiedades en Venta", value="\n\n".join(property_list_text), inline=False)
        else:
            embed.description = "No hay más propiedades que mostrar."

        embed.set_footer(text=f"Página {page_index + 1} de {self.total_pages}")
        return embed

    async def update_view(self, interaction: discord.Interaction):
        """Actualiza el mensaje con el embed y los botones correctos."""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

        embed = await self.create_embed_for_page(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.secondary, custom_id="prop_market_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view(interaction)

    @discord.ui.button(label="Siguiente ▶️", style=discord.ButtonStyle.secondary, custom_id="prop_market_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_view(interaction)


class Propiedades(commands.Cog):
    """Cog para gestionar la creación, compra y venta de propiedades."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db')
        self.db.row_factory = sqlite3.Row
        self.economia_cog = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Asegura la conexión inicial con el cog de Economía."""
        self.economia_cog = self.bot.get_cog('Economia')

    async def get_economia_cog(self) -> commands.Cog:
        """Función robusta para obtener el cog de economía, reintentando si es necesario."""
        if self.economia_cog is None:
            self.economia_cog = self.bot.get_cog('Economia')
        return self.economia_cog

    async def has_admin_permission(self, interaction: discord.Interaction) -> bool:
        """Verifica si el usuario tiene permisos de administrador."""
        config_cog = self.bot.get_cog('ConfigCog')
        if not config_cog: return False
        return await config_cog.has_permission(interaction, 'admin')

    # --- GRUPO DE COMANDOS /propiedad ---
    propiedad = app_commands.Group(name="propiedad", description="Gestiona, compra y vende propiedades.")

    @propiedad.command(name="crear", description="[Admin] Añade una nueva propiedad al mercado del estado.")
    @app_commands.default_permissions(administrator=True)
    async def crear_propiedad(self, interaction: discord.Interaction, id_propiedad: int, tipo: str, calle: str, precio: int, foto: discord.Attachment = None):
        if not await self.has_admin_permission(interaction): return await interaction.response.send_message("🚫 No tienes permisos.", ephemeral=True)
        if precio <= 0 or id_propiedad <= 0: return await interaction.response.send_message("❌ El ID y el precio deben ser positivos.", ephemeral=True)
        if foto and not foto.content_type.startswith('image/'): return await interaction.response.send_message("❌ El archivo adjunto debe ser una imagen.", ephemeral=True)
        photo_url = foto.url if foto else None
        
        try:
            cursor = self.db.cursor()
            cursor.execute("""
                INSERT INTO propiedades (propiedad_id, server_id, tipo, nombre_calle, precio, photo_url, en_venta) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (id_propiedad, interaction.guild.id, tipo.capitalize(), calle, precio, photo_url, True))
            self.db.commit()
            await interaction.response.send_message(f"✅ Propiedad #{id_propiedad} ('{calle}') creada y puesta en el mercado.", ephemeral=True)
        except sqlite3.IntegrityError:
            await interaction.response.send_message(f"❌ Ya existe una propiedad con el ID #{id_propiedad}.", ephemeral=True)

    @propiedad.command(name="mercado", description="Navega por las propiedades en venta.")
    async def propiedades_mercado(self, interaction: discord.Interaction):
        cursor = self.db.cursor()
        properties_for_sale = cursor.execute("SELECT * FROM propiedades WHERE en_venta = 1 OR en_venta_por_jugador = 1 ORDER BY precio, precio_venta_jugador").fetchall()

        if not properties_for_sale:
            return await interaction.response.send_message("Actualmente no hay propiedades en el mercado.", ephemeral=True)
        
        view = PropertyMarketView(properties_for_sale, self.bot, items_per_page=10)
        
        view.prev_button.disabled = True
        view.next_button.disabled = view.total_pages <= 1
        
        embed = await view.create_embed_for_page(0)
        await interaction.response.send_message(embed=embed, view=view)

    @propiedad.command(name="vender", description="Pon una de tus propiedades a la venta en el mercado.")
    async def vender_propiedad(self, interaction: discord.Interaction, propiedad_id: int, precio: int):
        if precio <= 0: return await interaction.response.send_message("❌ El precio debe ser mayor que cero.", ephemeral=True)
        cursor = self.db.cursor()
        prop = cursor.execute("SELECT propietario_id FROM propiedades WHERE propiedad_id = ? AND propietario_id = ?", (propiedad_id, interaction.user.id)).fetchone()
        if not prop: return await interaction.response.send_message("❌ Esa propiedad no existe o no te pertenece.", ephemeral=True)
        
        cursor.execute("UPDATE propiedades SET en_venta_por_jugador = 1, en_venta = 0, precio_venta_jugador = ? WHERE propiedad_id = ?", (precio, propiedad_id))
        self.db.commit()
        await interaction.response.send_message(f"✅ Has puesto tu propiedad #{propiedad_id} a la venta por **${precio:,}**.")

    @propiedad.command(name="comprar", description="Compra una propiedad del mercado.")
    async def comprar_propiedad(self, interaction: discord.Interaction, propiedad_id: int):
        economia_cog = await self.get_economia_cog()
        if not economia_cog:
            return await interaction.response.send_message("❌ Error crítico: El sistema de economía no está disponible.", ephemeral=True)
        
        cursor = self.db.cursor()
        prop = cursor.execute("SELECT * FROM propiedades WHERE propiedad_id = ?", (propiedad_id,)).fetchone()
        
        if not prop or (not prop['en_venta'] and not prop['en_venta_por_jugador']):
            return await interaction.response.send_message("❌ Esa propiedad no está en venta.", ephemeral=True)
        if prop['propietario_id'] == interaction.user.id:
            return await interaction.response.send_message("❌ No puedes comprar tu propia propiedad.", ephemeral=True)

        precio_final, vendedor_id = (prop['precio'], None) if prop['en_venta'] else (prop['precio_venta_jugador'], prop['propietario_id'])
        
        if not await economia_cog.modificar_dinero(interaction.user.id, -precio_final):
            return await interaction.response.send_message(f"❌ No tienes suficiente dinero. Necesitas ${precio_final:,}.", ephemeral=True)
        
        if vendedor_id:
            await economia_cog.modificar_dinero(vendedor_id, precio_final)

        cursor.execute("UPDATE propiedades SET propietario_id = ?, en_venta = 0, en_venta_por_jugador = 0, precio_venta_jugador = 0 WHERE propiedad_id = ?",
                       (interaction.user.id, prop['propiedad_id']))
        self.db.commit()
        await interaction.response.send_message(f"¡Felicidades! Has comprado la propiedad #{propiedad_id} por **${precio_final:,}**.")

    @propiedad.command(name="ver", description="Muestra información detallada de una propiedad por su ID.")
    async def propiedad_ver(self, interaction: discord.Interaction, id_propiedad: int):
        cursor = self.db.cursor()
        # --- CORRECCIÓN AQUÍ: Se cambió "image_url" por "photo_url" para coincidir con la base de datos ---
        cursor.execute("SELECT tipo, nombre_calle, precio, propietario_id, en_venta, en_venta_por_jugador, precio_venta_jugador, ingreso_pasivo, photo_url FROM propiedades WHERE propiedad_id = ?", (id_propiedad,))
        propiedad = cursor.fetchone()

        if not propiedad:
            await interaction.response.send_message(f"❌ No se encontró ninguna propiedad con el ID #{id_propiedad}.", ephemeral=True)
            return

        # --- CORRECCIÓN AQUÍ: Se usa la variable correcta "photo_url" ---
        tipo, calle, precio_estado, propietario_id, en_venta, en_venta_jugador, precio_jugador, ingreso, photo_url = propiedad

        embed = discord.Embed(title=f"{tipo} en {calle}", color=discord.Color.dark_blue())
        if photo_url:
            embed.set_image(url=photo_url)

        # Estado y Propietario
        if en_venta:
            embed.add_field(name="Estado", value="🟢 **En Venta (Estado)**", inline=True)
            embed.add_field(name="Precio", value=f"**${precio_estado:,}**", inline=True)
        elif en_venta_jugador:
            embed.add_field(name="Estado", value="🟡 **En Venta (Jugador)**", inline=True)
            embed.add_field(name="Precio", value=f"**${precio_jugador:,}**", inline=True)
        else:
            embed.add_field(name="Estado", value="🔴 **Vendida**", inline=True)
        
        if propietario_id:
            try:
                propietario = await interaction.guild.fetch_member(propietario_id)
                embed.add_field(name="Propietario/a", value=propietario.mention, inline=True)
            except discord.NotFound:
                embed.add_field(name="Propietario/a", value="*Usuario no encontrado*", inline=True)
        
        # Ingreso pasivo (si lo tiene)
        if ingreso > 0:
            embed.add_field(name="Genera", value=f"💰 ${ingreso:,} / ciclo", inline=True)

        embed.set_footer(text=f"ID de Propiedad: {id_propiedad}")
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Propiedades(bot))
# Guardar en: /cogs/casino_cog.py

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

# --- Lógica de Blackjack (completa y autocontenida) ---
DECK = [2, 3, 4, 5, 6, 7, 8, 9, 10, 'J', 'Q', 'K', 'A'] * 4
CARD_VALUES = {'J': 10, 'Q': 10, 'K': 10, 'A': 11}

def calculate_hand(hand):
    """Calcula el valor total de una mano de Blackjack."""
    value = sum(CARD_VALUES.get(card, card) for card in hand)
    num_aces = hand.count('A')
    while value > 21 and num_aces:
        value -= 10
        num_aces -= 1
    return value

class BlackjackView(discord.ui.View):
    """Vista interactiva para una partida de Blackjack (CORREGIDA)."""
    def __init__(self, author: discord.Member, apuesta: int, economia_cog):
        super().__init__(timeout=180.0)
        self.author = author
        self.apuesta = apuesta
        self.economia_cog = economia_cog
        self.deck = random.sample(DECK, k=52)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.message = None # Guardaremos el mensaje aquí

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Asegura que solo el jugador original pueda interactuar."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("No es tu partida.", ephemeral=True)
            return False
        return True

    def create_embed(self, game_over=False, result_text=""):
        """Crea el Embed que representa el estado actual del juego."""
        player_score = calculate_hand(self.player_hand)
        dealer_score = calculate_hand(self.dealer_hand)
        dealer_hand_text = f"[{dealer_score}]  `{' '.join(map(str, self.dealer_hand))}`" if game_over else f"[?]  `{self.dealer_hand[0]} ?`"

        embed = discord.Embed(title=f"Blackjack 🃏 | Apuesta: ${self.apuesta:,}", color=discord.Color.from_rgb(5, 99, 53))
        embed.set_author(name=self.author.display_name, icon_url=self.author.display_avatar.url)
        embed.add_field(name="Tu Mano", value=f"[{player_score}]  `{' '.join(map(str, self.player_hand))}`", inline=False)
        embed.add_field(name="Mano del Crupier", value=dealer_hand_text, inline=False)
        if game_over:
            embed.description = result_text
        return embed

    async def end_game(self, interaction: discord.Interaction, result_text: str, payout_multiplier: float):
        """Finaliza la partida, paga las ganancias y deshabilita los botones."""
        for item in self.children:
            item.disabled = True
        
        ganancia = int(self.apuesta * (payout_multiplier - 1)) # Restamos 1 para no devolver la apuesta que ya se quitó
        if ganancia != -self.apuesta: # Si no es una pérdida total
            await self.economia_cog.modificar_dinero(self.author.id, self.apuesta + ganancia)

        final_embed = self.create_embed(game_over=True, result_text=result_text)
        await interaction.response.edit_message(embed=final_embed, view=self)
        self.stop()

    # ---- MÉTODO CRÍTICO CORREGIDO ----
    async def on_timeout(self):
        """Se ejecuta cuando la vista expira (180s)."""
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        # Devolver la apuesta original al jugador
        await self.economia_cog.modificar_dinero(self.author.id, self.apuesta)

        # Notificar al usuario y actualizar el mensaje
        result_text = f"**Partida terminada por inactividad.** Se te ha devuelto tu apuesta de ${self.apuesta:,}."
        final_embed = self.create_embed(game_over=True, result_text=result_text)
        
        if self.message:
            await self.message.edit(embed=final_embed, view=self)
        
        # self.stop() se llama automáticamente al final de on_timeout

    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.deck.pop())
        player_score = calculate_hand(self.player_hand)
        
        if player_score > 21:
            # Aquí no hay multiplicador porque el dinero ya fue retirado al inicio
            await self.end_game(interaction, f"**¡Te has pasado! ({player_score})** Pierdes tu apuesta de ${self.apuesta:,}.", 0)
        elif player_score == 21:
            # Forzamos al jugador a plantarse si llega a 21
            self.stand.disabled = True # Opcional: deshabilitar 'plantarse'
            await self.stand.callback(interaction) # Llamamos directamente a la lógica de plantarse
        else:
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Plantarse", style=discord.ButtonStyle.success, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        dealer_score = calculate_hand(self.dealer_hand)
        while dealer_score < 17:
            self.dealer_hand.append(self.deck.pop())
            dealer_score = calculate_hand(self.dealer_hand)
        
        player_score = calculate_hand(self.player_hand)
        
        if dealer_score > 21 or player_score > dealer_score:
            await self.end_game(interaction, f"**¡Ganaste!** Recibes ${self.apuesta * 2:,} en total.", 2)
        elif player_score < dealer_score:
            await self.end_game(interaction, f"**El crupier gana.** Pierdes tu apuesta de ${self.apuesta:,}.", 0)
        else:
            await self.end_game(interaction, "**¡Empate!** Recuperas tu apuesta de ${self.apuesta:,}.", 1)

# --- Cog Principal del Casino ---
class Casino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = set()
        self.economia_cog = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Se asegura de que el cog de economía esté listo cuando el bot arranque."""
        self.economia_cog = self.bot.get_cog('Economia')
        if self.economia_cog:
            print(" -> Módulo de Casino conectado con Economía.")
        else:
            print("ERROR CRÍTICO: Casino no pudo conectarse con el módulo de Economía.")

    async def check_preconditions(self, interaction: discord.Interaction, apuesta: int):
        """Comprobaciones centralizadas antes de iniciar cualquier juego."""
        if not self.economia_cog:
            # Reintenta la conexión por si acaso
            self.economia_cog = self.bot.get_cog('Economia')
            if not self.economia_cog:
                await interaction.response.send_message("❌ Error: El sistema de economía no está disponible. Contacta a un admin.", ephemeral=True)
                return False
        
        if interaction.user.id in self.active_games:
            await interaction.response.send_message("❌ Ya tienes una partida en curso. ¡Termínala primero!", ephemeral=True)
            return False
        
        if apuesta <= 0:
            await interaction.response.send_message("❌ La apuesta debe ser mayor que cero.", ephemeral=True)
            return False
        
        # Le quitamos el dinero ANTES de jugar para evitar abusos
        if not await self.economia_cog.modificar_dinero(interaction.user.id, -apuesta):
            await interaction.response.send_message(f"❌ No tienes suficiente dinero para apostar ${apuesta:,}.", ephemeral=True)
            return False
        
        return True

    casino = app_commands.Group(name="casino", description="Juega a los juegos del casino.")

    @casino.command(name="blackjack", description="Juega una partida de Blackjack contra el crupier.")
    async def blackjack(self, interaction: discord.Interaction, apuesta: int):
        if not await self.check_preconditions(interaction, apuesta):
            # Devolvemos el dinero si la precondición falla después de haberlo quitado.
            # La función check_preconditions ya envía el mensaje de error.
            if interaction.user.id not in self.active_games: # Solo si el error no fue por partida activa
                 await self.economia_cog.modificar_dinero(interaction.user.id, apuesta)
            return

        self.active_games.add(interaction.user.id)
        view = BlackjackView(interaction.user, apuesta, self.economia_cog)
        
        try:
            await interaction.response.send_message(embed=view.create_embed(), view=view)
            # ---- LÍNEAS AÑADIDAS/MODIFICADAS ----
            message = await interaction.original_response() # Obtenemos el mensaje que acabamos de enviar
            view.message = message # Guardamos el mensaje en la vista para usarlo en on_timeout
            # ------------------------------------
            await view.wait()
        finally:
            if interaction.user.id in self.active_games:
                self.active_games.remove(interaction.user.id)

    @casino.command(name="ruleta", description="Apuesta en la ruleta.")
    async def ruleta(self, interaction: discord.Interaction, tipo_apuesta: str, apuesta: int):
        tipo_apuesta = tipo_apuesta.lower()
        APUESTAS_VALIDAS = ['rojo', 'negro', 'par', 'impar'] + [str(i) for i in range(37)]
        if tipo_apuesta not in APUESTAS_VALIDAS:
            await interaction.response.send_message("❌ Apuesta no válida. Opciones: 'rojo', 'negro', 'par', 'impar', o un número de 0 a 36.", ephemeral=True)
            return
        
        if not await self.check_preconditions(interaction, apuesta):
            return

        self.active_games.add(interaction.user.id)
        
        embed = discord.Embed(title="Roulette 🎡", description="¡No va más! La bola está girando...", color=discord.Color.dark_magenta())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
        
        anim_emojis = ['➡️', '↘️', '⬇️', '↙️', '⬅️', '↖️', '⬆️', '↗️']
        for i in range(random.randint(4, 7)):
            embed.description = f"La bola gira y gira... {random.choice(anim_emojis)}"
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.7)
        
        resultado = random.randint(0, 36)
        es_rojo = resultado in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        es_par = resultado != 0 and resultado % 2 == 0

        payout_multiplier = 0
        if tipo_apuesta.isdigit() and int(tipo_apuesta) == resultado: payout_multiplier = 36
        elif tipo_apuesta == 'rojo' and es_rojo: payout_multiplier = 2
        elif tipo_apuesta == 'negro' and not es_rojo and resultado != 0: payout_multiplier = 2
        elif tipo_apuesta == 'par' and es_par: payout_multiplier = 2
        elif tipo_apuesta == 'impar' and not es_par and resultado != 0: payout_multiplier = 2

        ganancia_total = apuesta * payout_multiplier
        color_emoji = "🔴" if es_rojo else "⚫️" if resultado != 0 else "🟢"
        
        embed.description = f"La bola ha caído en... **{color_emoji} {resultado} {color_emoji}**"
        
        if ganancia_total > 0:
            await self.economia_cog.modificar_dinero(interaction.user.id, ganancia_total)
            embed.add_field(name="¡Felicidades!", value=f"Tu apuesta a `{tipo_apuesta}` ha ganado. Recibes **${ganancia_total:,}** en total.")
            embed.color = discord.Color.green()
        else:
            embed.add_field(name="Mala Suerte", value=f"Tu apuesta a `{tipo_apuesta}` no ha salido premiada.")
            embed.color = discord.Color.red()
            
        await interaction.edit_original_response(embed=embed)
        self.active_games.remove(interaction.user.id)

    @casino.command(name="slots", description="Juega a la máquina tragaperras y prueba tu suerte.")
    async def slots(self, interaction: discord.Interaction, apuesta: int):
        if not await self.check_preconditions(interaction, apuesta):
            return

        self.active_games.add(interaction.user.id)

        simbolos = { "🍒": 3, "🔔": 5, "🍊": 8, "💰": 15, "💎": 30, "👑": 60 }
        pesos = [30, 25, 20, 15, 8, 2]
        
        embed = discord.Embed(title="Tragaperras 🎰", color=discord.Color.blue())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        rodillos_girando = ["❓", "❓", "❓"]
        embed.description = f"**[ {' | '.join(rodillos_girando)} ]**\n*¡Girando!*"
        await interaction.response.send_message(embed=embed)
        
        rodillo_final = random.choices(list(simbolos.keys()), weights=pesos, k=3)
        
        await asyncio.sleep(0.8)
        rodillos_girando[0] = rodillo_final[0]
        embed.description = f"**[ {' | '.join(rodillos_girando)} ]**"
        await interaction.edit_original_response(embed=embed)
        
        await asyncio.sleep(0.8)
        rodillos_girando[1] = rodillo_final[1]
        embed.description = f"**[ {' | '.join(rodillos_girando)} ]**"
        await interaction.edit_original_response(embed=embed)

        await asyncio.sleep(0.8)
        rodillos_girando[2] = rodillo_final[2]
        embed.description = f"**[ {' | '.join(rodillos_girando)} ]**"
        
        ganancia_total = 0
        if rodillo_final[0] == rodillo_final[1] == rodillo_final[2]:
            multiplicador = simbolos[rodillo_final[0]]
            ganancia_total = apuesta * multiplicador
            embed.add_field(name="¡¡¡JACKPOT!!!", value=f"¡Tres `{rodillo_final[0]}` en línea! Has ganado **${ganancia_total:,}**.")
            embed.color = discord.Color.gold()
        elif rodillo_final[0] == rodillo_final[1] or rodillo_final[1] == rodillo_final[2]:
            multiplicador = 2
            ganancia_total = apuesta * multiplicador
            embed.add_field(name="¡Premio!", value=f"¡Dos en línea! Has ganado **${ganancia_total:,}**.")
            embed.color = discord.Color.green()
        else:
            embed.add_field(name="Sin Suerte", value=f"No hubo combinación.")
        
        if ganancia_total > 0:
            await self.economia_cog.modificar_dinero(interaction.user.id, ganancia_total)

        await interaction.edit_original_response(embed=embed)
        self.active_games.remove(interaction.user.id)

async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))
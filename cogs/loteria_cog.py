# Guardar en: /cogs/loteria_cog.py (VERSIÓN CON LA FINALIZACIÓN CORREGIDA)

import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import datetime
import random

# La vista no cambia
class LotteryView(discord.ui.View):
    def __init__(self, lottery_id: int):
        super().__init__(timeout=None); self.lottery_id=lottery_id; self.participate_button.custom_id=f"lottery_participate_{lottery_id}"
    @discord.ui.button(label="Comprar Ticket", style=discord.ButtonStyle.success, emoji="🎟️")
    async def participate_button(self, i, b):
        cog=i.client.get_cog('Loteria')
        if cog: await cog.handle_participation(i,self.lottery_id)

class Loteria(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = sqlite3.connect('cronos_rp.db') # CONEXIÓN SIMPLE Y CORRECTA
        self.db.row_factory = sqlite3.Row
        self.bot.add_view(LotteryView(lottery_id=-1))
        self.check_lottery_end.start()

    # El resto de funciones no cambian...
    def get_config(self, s, k):
        cur=self.db.cursor(); cur.execute("SELECT value FROM server_config WHERE server_id = ? AND key = ?",(s,k)); res=cur.fetchone(); return int(res[0]) if res else None
    async def get_active_lottery(self, s):
        cur=self.db.cursor(); cur.execute("SELECT * FROM lotteries WHERE server_id=? AND is_active=TRUE",(s,)); return cur.fetchone()
    async def handle_participation(self, i, l_id):
        await i.response.defer(ephemeral=True); cost=self.get_config(i.guild.id,'lottery_ticket_cost')
        if not cost: return await i.followup.send("❌ Error: Precio no configurado.",ephemeral=True)
        lottery=await self.get_active_lottery(i.guild.id)
        if not lottery or lottery['lottery_id']!=l_id: return await i.followup.send("❌ Lotería finalizada.",ephemeral=True)
        cur=self.db.cursor(); cur.execute("SELECT 1 FROM lottery_participants WHERE lottery_id=? AND user_id=?",(l_id,i.user.id))
        if cur.fetchone(): return await i.followup.send("🎟️ Ya participas.",ephemeral=True)
        eco=self.bot.get_cog('Economia')
        if not eco or not await eco.modificar_dinero(i.user.id,-cost): return await i.followup.send(f"❌ No tienes ${cost:,}.",ephemeral=True)
        cur.execute("INSERT INTO lottery_participants (lottery_id, user_id) VALUES (?,?)",(l_id,i.user.id)); cur.execute("UPDATE lotteries SET current_pot=current_pot+? WHERE lottery_id=?",(cost,l_id)); self.db.commit()
        await i.followup.send(f"✅ Ticket comprado por ${cost:,} ¡Suerte!",ephemeral=True); await self.update_lottery_embed(lottery['lottery_id'])

    @app_commands.command(name="loteria",description="[Admin] Inicia una nueva lotería.")
    async def loteria(self, i, bote:int, fecha:str):
        cfg=self.bot.get_cog('ConfigCog')
        if not cfg or not await cfg.has_permission(i,'admin'): return await i.response.send_message("🚫 No tienes permisos.",ephemeral=True)
        if await self.get_active_lottery(i.guild.id): return await i.response.send_message("❌ Ya hay una lotería activa.",ephemeral=True)
        try: end_dt=datetime.datetime.strptime(fecha,"%d/%m/%Y %H:%M")
        except ValueError: return await i.response.send_message("❌ Formato fecha: `DD/MM/YYYY HH:MM`.",ephemeral=True)
        cur=self.db.cursor(); cur.execute("INSERT INTO lotteries (server_id,end_timestamp,initial_pot,current_pot) VALUES (?,?,?,?)",(i.guild.id,end_dt,bote,bote)); l_id=cur.lastrowid; self.db.commit()
        embed=await self.create_lottery_embed(l_id); msg=await i.channel.send(embed=embed,view=LotteryView(l_id)); cur.execute("UPDATE lotteries SET message_id=?,channel_id=? WHERE lottery_id=?",(msg.id,msg.channel.id,l_id)); self.db.commit()
        await i.response.send_message(f"✅ Lotería #{l_id} creada.",ephemeral=True)

    # --- ¡¡¡AQUÍ ESTÁ LA CORRECCIÓN!!! ---
    @tasks.loop(minutes=1)
    async def check_lottery_end(self):
        """
        Esta tarea se ejecuta cada minuto para comprobar si alguna lotería ha finalizado.
        Ahora compara objetos de fecha reales en lugar de texto.
        """
        cursor = self.db.cursor()
        # 1. Obtenemos TODAS las loterías que siguen marcadas como activas
        cursor.execute("SELECT lottery_id, end_timestamp FROM lotteries WHERE is_active = TRUE")
        active_lotteries = cursor.fetchall()
        
        if not active_lotteries:
            return # Si no hay ninguna activa, no hacemos nada

        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for lottery_data in active_lotteries:
            lottery_id = lottery_data['lottery_id']
            end_timestamp_str = lottery_data['end_timestamp']
            
            # 2. Convertimos el TEXTO de la base de datos a un objeto de FECHA real
            #    Le añadimos la zona horaria UTC para una comparación segura
            end_timestamp_dt = datetime.datetime.fromisoformat(end_timestamp_str).replace(tzinfo=datetime.timezone.utc)
            
            # 3. Comparamos las fechas. Si la hora actual es posterior, la lotería ha terminado.
            if now_utc > end_timestamp_dt:
                print(f"Lotería #{lottery_id} ha finalizado. Sorteando ganador...")
                await self.draw_winner(lottery_id)

    @check_lottery_end.before_loop
    async def before_check(self): await self.bot.wait_until_ready()
    # ----------------------------------------------------

    async def draw_winner(self, l_id):
        cur=self.db.cursor(); cur.execute("SELECT user_id FROM lottery_participants WHERE lottery_id=?",(l_id,)); p=cur.fetchall(); info=self.db.execute("SELECT * FROM lotteries WHERE lottery_id=?",(l_id,)).fetchone(); w_id=None
        if p: w_id=random.choice(p)['user_id']; eco=self.bot.get_cog('Economia'); await eco.modificar_dinero(w_id,info['current_pot'])
        cur.execute("UPDATE lotteries SET is_active=FALSE,winner_id=? WHERE lottery_id=?",(w_id,l_id)); self.db.commit(); await self.update_lottery_embed(l_id,True)

    async def create_lottery_embed(self, l_id):
        info=self.db.execute("SELECT * FROM lotteries WHERE lottery_id=?",(l_id,)).fetchone()
        end_dt = datetime.datetime.fromisoformat(info['end_timestamp'])
        end_ts = int(end_dt.timestamp())
        e=discord.Embed(title="🎉 ¡Lotería del Servidor! 🎉",color=0xFFD700); e.add_field(name="💰 Bote Actual",value=f"**${info['current_pot']:,}**",inline=True)
        cur=self.db.cursor(); cur.execute("SELECT COUNT(*) FROM lottery_participants WHERE lottery_id=?",(l_id,)); p_count=cur.fetchone()[0]; e.add_field(name="👥 Participantes",value=str(p_count),inline=True)
        e.add_field(name="🗓️ Finaliza",value=f"<t:{end_ts}:R> (<t:{end_ts}:F>)",inline=False); e.set_footer(text=f"Lotería ID: {l_id} | ¡Participa!"); return e

    async def update_lottery_embed(self, l_id, is_ended=False):
        info=self.db.execute("SELECT * FROM lotteries WHERE lottery_id=?",(l_id,)).fetchone()
        if not info or not info['channel_id']: return
        try: chan=await self.bot.fetch_channel(info['channel_id']); msg=await chan.fetch_message(info['message_id'])
        except (discord.NotFound,discord.Forbidden): return
        e=await self.create_lottery_embed(l_id); view=None
        if is_ended:
            e.color=0xFF0000; e.title="🚫 ¡Lotería Finalizada! 🚫"; w_id=info['winner_id']
            if w_id: w_user=await self.bot.fetch_user(w_id); e.description=f"¡Felicidades a {w_user.mention} por ganar **${info['current_pot']:,}**!"
            else: e.description="Lotería finalizada sin participantes."
            e.remove_footer()
        else: view=LotteryView(l_id)
        await msg.edit(embed=e,view=view)

async def setup(bot): await bot.add_cog(Loteria(bot))
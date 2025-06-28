# Guardar como main.py

import discord
from discord.ext import commands
from discord import app_commands
import os

# --- Configuración Inicial ---
intents = discord.Intents.default()
intents.members = True # Necesario para que el bot vea a los miembros del servidor
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Evento de Inicio ---
@bot.event
async def on_ready():
    print(f'¡Conectado como {bot.user}!')
    print('Cargando módulos (Cogs)...')
    
    for filename in os.listdir('./cogs'):
        # Condición añadida: ignora el archivo checks.py y cualquier archivo que empiece por dos guiones bajos.
        if filename.endswith('.py') and not filename.startswith('__') and filename != 'checks.py':
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f' -> Módulo {filename} cargado.')
            except Exception as e:
                print(f'ERROR: No se pudo cargar el módulo {filename}.')
                print(f'  {e}')

    try:
        synced = await bot.tree.sync()
        print(f"¡Sincronizados {len(synced)} comandos de barra (/)!")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

# --- GESTOR DE ERRORES GLOBAL ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingRole):
        # Este error es para @app_commands.checks.has_role, que ya no usaremos tanto.
        embed = discord.Embed(title="🚫 Acceso Denegado 🚫", description=f"No tienes los permisos necesarios (rol `{error.missing_role}`) para usar este comando.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif isinstance(error, app_commands.errors.CheckFailure):
        # Este error se activará con nuestros nuevos chequeos dinámicos.
        embed = discord.Embed(title="🚫 Acceso Denegado 🚫", description=f"No tienes el rol configurado en este servidor para usar este comando, o falta alguna configuración.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        print(f"Ha ocurrido un error no manejado en el comando '{interaction.command.name}': {error}")
        embed = discord.Embed(title="💥 ¡Oops! Algo ha salido mal 💥", description="Ha ocurrido un error inesperado. El incidente ha sido reportado.", color=discord.Color.dark_red())
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

# --- Ejecución del Bot ---
TOKEN = "MTEyOTAwODQzMjQ4NjI5MzUzNA.GutDci.EpHVoAZuvOPgbZ2327wHHGw1mM6P2jPkB4ShPE" 
bot.run(TOKEN)
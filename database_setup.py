# Guardar como database_setup.py (VERSIÓN COMPLETA Y CORRECTA)

import sqlite3

print("Iniciando configuración completa de la base de datos 'cronos_rp.db'...")
db = sqlite3.connect('cronos_rp.db')
cursor = db.cursor()

# --- TABLAS PRINCIPALES ---

cursor.execute('''
    CREATE TABLE IF NOT EXISTS economia (
        user_id INTEGER PRIMARY KEY,
        dinero_limpio INTEGER DEFAULT 1000,
        dinero_sucio INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS multas_activas (
        multa_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        officer_id INTEGER,
        delito TEXT,
        cantidad INTEGER,
        fecha TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS antecedentes (
        antecedente_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tipo_infraccion TEXT,
        descripcion TEXT,
        fecha TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS dnis (
        server_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        dni_number TEXT NOT NULL UNIQUE,
        full_name TEXT,
        date_of_birth TEXT,
        sex TEXT,
        nationality TEXT,
        photo_url TEXT,
        PRIMARY KEY (server_id, user_id)
    )
''')

# --- TABLAS DE CONFIGURACIÓN Y SISTEMAS ---

cursor.execute('''
    CREATE TABLE IF NOT EXISTS server_config (
        server_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        value INTEGER NOT NULL,
        PRIMARY KEY (server_id, key)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS role_config (
        server_id INTEGER NOT NULL,
        role_type TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        PRIMARY KEY (server_id, role_type, role_id)
    )
''')

# Tabla de cargos CON la columna 'category'
cursor.execute('''
    CREATE TABLE IF NOT EXISTS server_charges (
        charge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        charge_code TEXT NOT NULL,
        description TEXT NOT NULL,
        fine_amount INTEGER DEFAULT 0,
        extra_notes TEXT
    )
''')

# Tabla para CKs
cursor.execute('''
    CREATE TABLE IF NOT EXISTS ck_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        requester_id INTEGER NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        evidence_url TEXT,
        status TEXT DEFAULT 'PENDING',
        moderator_id INTEGER,
        moderator_notes TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

print("Añadiendo tablas para el sistema de Tienda e Inventario...")

# --- TABLA PARA LOS OBJETOS DE LA TIENDA ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS shop_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER NOT NULL,
        stock INTEGER DEFAULT -1, 
        role_required_id INTEGER DEFAULT NULL,
        UNIQUE (server_id, name)
    )
''')
# Nota: stock = -1 significa infinito.

# --- TABLA PARA LOS INVENTARIOS DE LOS USUARIOS ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_inventories (
        inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (item_id) REFERENCES shop_items (item_id) ON DELETE CASCADE
    )
''')

print("Añadiendo tabla para el sistema de Sueldos por Rol...")

# --- TABLA DE SUELDOS (Correcta para este sistema) ---
cursor.execute("DROP TABLE IF EXISTS role_salaries")
cursor.execute('''
    CREATE TABLE IF NOT EXISTS role_salaries (
        server_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        salary_amount INTEGER NOT NULL,
        payout_interval_hours INTEGER NOT NULL,
        last_paid_timestamp TIMESTAMP,
        PRIMARY KEY (server_id, role_id)
    )
''')

# --- TABLA DE PROPIEDADES (Correcta para este sistema) ---
cursor.execute("DROP TABLE IF EXISTS propiedades")
cursor.execute('''
    CREATE TABLE IF NOT EXISTS propiedades (
        propiedad_id INTEGER PRIMARY KEY,
        server_id INTEGER NOT NULL,
        tipo TEXT,
        nombre_calle TEXT,
        precio INTEGER,
        propietario_id INTEGER DEFAULT NULL,
        en_venta BOOLEAN DEFAULT TRUE,
        ingreso_pasivo INTEGER DEFAULT 0,
        payout_interval_hours INTEGER DEFAULT 24,
        last_paid_timestamp TIMESTAMP,
        photo_url TEXT,
        en_venta_por_jugador BOOLEAN DEFAULT FALSE,
        precio_venta_jugador INTEGER DEFAULT 0
    )
''')

# Tabla para registrar todas las sanciones
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sanciones (
        sancion_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        moderator_id INTEGER NOT NULL,
        tipo TEXT NOT NULL, -- 'warn', 'timeout', 'kick', 'ban'
        razon TEXT,
        duracion_segundos INTEGER DEFAULT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        activa BOOLEAN DEFAULT TRUE
    )
''')

# Tabla para llevar la cuenta de las demandas activas
# (Opcional, pero útil para evitar que un usuario abra múltiples demandas a la vez)
cursor.execute('''
    CREATE TABLE IF NOT EXISTS demandas_activas (
        demanda_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        demandante_id INTEGER NOT NULL,
        demandado_id INTEGER NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS lotteries (
        lottery_id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL,
        message_id INTEGER,
        channel_id INTEGER,
        end_timestamp TIMESTAMP NOT NULL,
        initial_pot INTEGER NOT NULL,
        current_pot INTEGER NOT NULL,
        winner_id INTEGER,
        is_active BOOLEAN DEFAULT TRUE
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS lottery_participants (
        participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lottery_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (lottery_id) REFERENCES lotteries (lottery_id) ON DELETE CASCADE,
        UNIQUE(lottery_id, user_id)
    )
''')

# --- TABLA DE ANTECEDENTES MEJORADA ---
cursor.execute('''
    CREATE TABLE IF NOT EXISTS antecedentes (
        antecedente_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        multa_id INTEGER, -- Para vincularlo a una multa específica
        tipo_infraccion TEXT NOT NULL, -- 'Arresto' o 'Multa'
        descripcion TEXT,
        fecha TIMESTAMP,
        status TEXT DEFAULT 'Pendiente' -- 'Pendiente' o 'Pagada'
    )
''')

db.commit()
db.close()

print("\n¡Base de datos y todas las tablas listas con la estructura más reciente!")
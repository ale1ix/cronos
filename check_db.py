import sqlite3

# Pon aquí el MISMO ID de servidor que usaste en el otro script
SERVER_ID_TO_CHECK = 1115623983392505886 # <--- ¡¡¡CAMBIA ESTE NÚMERO!!!

conn = sqlite3.connect('cronos_rp.db')
cursor = conn.cursor()

print(f"Buscando cargos en la base de datos para el servidor ID: {SERVER_ID_TO_CHECK}\n")

cursor.execute("SELECT category, charge_code, description, fine_amount FROM server_charges WHERE server_id = ?", (SERVER_ID_TO_CHECK,))

rows = cursor.fetchall()

if not rows:
    print("RESULTADO: La base de datos está VACÍA para este ID de servidor.")
    print("POSIBLES CAUSAS:")
    print("1. El SERVER_ID es incorrecto en este script o en add_charges.py.")
    print("2. El script add_charges.py no consiguió guardar los datos.")
else:
    print(f"¡ÉXITO! Se han encontrado {len(rows)} cargos en la base de datos:\n")
    for row in rows:
        print(f"  - Categoría: {row[0]}, Código: {row[1]}, Desc: {row[2]}, Multa: ${row[3]}")
        
conn.close()
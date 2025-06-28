# Guardar como: add_charges.py (Versión con Códigos "Art X.Y")
import sqlite3
import os

# --- CONFIGURACIÓN ---
# 1. Pon aquí el ID de tu servidor de Discord.
SERVER_ID = 1115623983392505886  # <--- ¡¡¡CAMBIA ESTE NÚMERO!!!

# 2. Nombre del fichero de la base de datos.
DATABASE_FILE = 'cronos_rp.db'

# 3. Nombre del fichero con la lista de cargos.
INPUT_FILE = 'cargos.txt'

# 4. Multa por defecto si NO se especifica una para un cargo.
DEFAULT_FINE = 1000
# --------------------

def create_sample_file():
    """Crea un fichero de ejemplo si no existe."""
    sample_content = """# INSTRUCCIONES:
# 1. El script generará los códigos de cargo automáticamente como "Art X.Y".
#    Por ejemplo, "1.1 Saltarse un semáforo" tendrá el código "Art 1.1".
# 2. Multa: Añade " - " y el número al final de la línea del cargo. Si no la pones, se usará la multa por defecto.

1. Infracciones de Tráfico
 1.1 Saltarse un semáforo - 1500
 1.2 Giro indebido - 750

2. Hurtos y Robos
 2.1 Hurto menor (sin violencia) - 5000
 2.2 Robo con intimidación - 15000
 2.3 Robo a mano armada - 50000
"""
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(sample_content)
    print(f"Se ha creado un fichero de ejemplo llamado '{INPUT_FILE}'. Edítalo con tus categorías y cargos, y vuelve a ejecutar el script.")

def main():
    """Función principal para procesar categorías y cargos."""
    if SERVER_ID == 111111111111111111:
        print("Error: Por favor, edita el script 'add_charges.py' y cambia el valor de SERVER_ID.")
        return

    if not os.path.exists(INPUT_FILE):
        create_sample_file()
        return

    if not os.path.exists(DATABASE_FILE):
        print(f"Error: No se encontró la base de datos '{DATABASE_FILE}' en este directorio.")
        return

    print("--- Asistente de Carga de Código Penal ---")
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    print(f"\nSe van a procesar los cargos del fichero '{INPUT_FILE}'.")
    print(f"Se aplicarán al servidor con ID: {SERVER_ID}")
    print("\nADVERTENCIA: Esto borrará TODOS los cargos existentes para este servidor y los reemplazará con los nuevos.")
    
    try:
        confirm = input("¿Estás seguro de que quieres continuar? (s/n): ")
        if confirm.lower() != 's':
            print("Operación cancelada.")
            return
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return

    try:
        cursor.execute("BEGIN TRANSACTION")

        cursor.execute("DELETE FROM server_charges WHERE server_id = ?", (SERVER_ID,))
        print(f"\nCargos antiguos para el servidor {SERVER_ID} eliminados.")

        cargos_a_insertar = []
        current_category = ""

        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split(' ', 1)
                if len(parts) < 2:
                    continue

                numbering, description = parts
                numbering = numbering.strip()

                # Detectar si es categoría (ej: "1.")
                if numbering.endswith('.') and numbering[:-1].isdigit() and '.' not in numbering[:-1]:
                    current_category = description.strip().capitalize()
                    print(f"\nDetectada categoría: '{current_category}'")
                
                # Detectar si es cargo (ej: "1.1")
                elif '.' in numbering:
                    if not current_category:
                        print(f"  -> ERROR (Línea {line_num}): Se encontró el cargo '{line}' sin una categoría previa. Saltando.")
                        continue
                    
                    # --- NUEVA LÓGICA DE GENERACIÓN DE CÓDIGO ---
                    charge_code = f"Art {numbering}"
                    # --- FIN DE LA NUEVA LÓGICA ---
                    
                    fine = DEFAULT_FINE
                    if ' - ' in description:
                        try:
                            desc_part, fine_part = description.rsplit(' - ', 1)
                            fine = int(fine_part.strip())
                            description = desc_part
                        except ValueError:
                            print(f"  -> ADVERTENCIA (Línea {line_num}): No se pudo leer la multa para '{description}'. Usando multa por defecto (${DEFAULT_FINE:,}).")
                    
                    description = description.strip().capitalize()

                    charge_data = (SERVER_ID, current_category, charge_code, description, fine)
                    cargos_a_insertar.append(charge_data)
                    # El print ahora muestra el nuevo código
                    print(f"  -> Preparando '{charge_code}': {description} (${fine:,})")

        if cargos_a_insertar:
            cursor.executemany(
                "INSERT INTO server_charges (server_id, category, charge_code, description, fine_amount) VALUES (?, ?, ?, ?, ?)",
                cargos_a_insertar
            )
            print(f"\n¡ÉXITO! Se han preparado {len(cargos_a_insertar)} nuevos cargos para insertar en la base de datos.")
        else:
            print("\nNo se encontraron cargos válidos en el fichero para insertar.")

        cursor.execute("COMMIT")
        print("\nOperación completada y guardada en la base de datos.")

    except Exception as e:
        print(f"\nHa ocurrido un error durante el proceso: {e}")
        cursor.execute("ROLLBACK")
        print("Todos los cambios han sido revertidos. La base de datos está como antes.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
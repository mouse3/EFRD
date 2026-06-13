import sqlite3
import random
import string

# Configuración
DATABASE_NAME = "outputs/Base_Datos_MACRO.db"
TOTAL_REGISTROS = 100000  # Número de filas aleatorias a generar

def generar_dni_nie():
    """Genera un DNI o NIE español con formato y letra de control válidos."""
    letras_control = "TRWAGMYFPDXBNJZSQVHLCKE"
    es_nie = random.random() < 0.3  # 30% de probabilidad de ser NIE
    
    if es_nie:
        letra_inicial = random.choice(['X', 'Y', 'Z'])
        reemplazo = {'X': '0', 'Y': '1', 'Z': '2'}[letra_inicial]
        numeros = "".join(random.choices(string.digits, k=7))
        num_control = int(reemplazo + numeros)
        letra_final = letras_control[num_control % 23]
        return f"{letra_inicial}{numeros}{letra_final}"
    else:
        numeros = "".join(random.choices(string.digits, k=8))
        num_control = int(numeros)
        letra_final = letras_control[num_control % 23]
        return f"{numeros}{letra_final}"

def crear_base_de_datos():
    # Conecta a la base de datos (se creará el archivo si no existe)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Elimina la tabla si ya existía para evitar duplicados en pruebas
    cursor.execute("DROP TABLE IF EXISTS Base_Datos_MACRO")
    
    # Crea la tabla con la estructura solicitada
    cursor.execute('''
        CREATE TABLE Base_Datos_MACRO (
            ref_catastral TEXT,
            tipo_unit TEXT,
            es_habitual INTEGER,
            dni_nie_nif TEXT,
            renta_mensual REAL,
            phi REAL,
            gamma REAL
        )
    ''')
    
    # Pisos físicos de muestra para simular que se comparten
    ciudades = ['MAD', 'BAR', 'VAL', 'SEV', 'BIL']
    referencias_fisicas = [f"REF_{random.choice(ciudades)}_{i:03d}" for i in range(1, 10)]
    
    registros = []
    
    for _ in range(TOTAL_REGISTROS):
        tipo_unit = random.choice(['fisica', 'virtual'])
        dni = generar_dni_nie()
        es_habitual = random.choice([0, 1])
        
        if tipo_unit == 'fisica':
            # Elegimos una referencia física aleatoria (puede repetirse)
            ref_catastral = random.choice(referencias_fisicas)
            # Algunas personas en casas compartidas pueden tener renta 0.0 o un valor real
            renta_mensual = round(random.choice([0.0, random.uniform(400, 3000)]), 1)
            gamma = round(random.uniform(1.0, 1.5), 2)
        else:
            # Las unidades virtuales vinculan la referencia al DNI
            ref_catastral = f"VIRTUAL_{dni}"
            renta_mensual = round(random.choice([0.0, random.uniform(200, 1500)]), 1)
            gamma = round(random.uniform(1.0, 1.4), 2)
            
        phi = round(random.uniform(0.1, 1.0), 2)
        
        registros.append((ref_catastral, tipo_unit, es_habitual, dni, renta_mensual, phi, gamma))
    
    # Inserta los datos en la tabla
    cursor.executemany('''
        INSERT INTO Base_Datos_MACRO (ref_catastral, tipo_unit, es_habitual, dni_nie_nif, renta_mensual, phi, gamma)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', registros)
    
    # Guarda cambios y cierra conexión
    conn.commit()
    print(f"¡Base de datos '{DATABASE_NAME}' creada con éxito con {TOTAL_REGISTROS} registros!")
    
    # Muestra una vista previa en la terminal
    print("\nVista previa de los datos generados (SELECT * LIMIT 10):")
    print(f"{'ref_catastral':<20} | {'tipo_unit':<10} | {'es_h':<4} | {'dni_nie_nif':<12} | {'renta':<8} | {'phi':<5} | {'gamma':<5}")
    print("-" * 75)
    cursor.execute("SELECT * FROM Base_Datos_MACRO LIMIT 10")
    for fila in cursor.fetchall():
        print(f"{fila[0]:<20} | {fila[1]:<10} | {fila[2]:<4} | {fila[3]:<12} | {fila[4]:<8} | {fila[5]:<5} | {fila[6]:<5}")
        
    conn.close()

if __name__ == "__main__":
    crear_base_de_datos()
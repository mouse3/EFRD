import sqlite3
import random
import string
import os
import numpy as np

# Configuración
DATABASE_NAME = "conexion/outputs/Base_Datos_MACRO.db" if os.path.exists("conexion") else "Base_Datos_MACRO.db"
TOTAL_REGISTROS = 100000  # Población objetivo aproximada (N_total)

def generar_dni_nie():
    """Genera un DNI o NIE español con formato y letra de control válidos."""
    letras_control = "TRWAGMYFPDXBNJZSQVHLCKE"
    es_nie = random.random() < 0.15  # ~15% de población extranjera regulada
    
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

def generar_renta_log_normal():
    """
    Genera rentas individuales realistas usando una distribución log-normal.
    La mayoría se agrupa entre 900€ y 1800€, con una cola larga hacia rentas altas.
    """
    # Parámetros ajustados para una media en torno a los 1.400€ mensuales brutos por trabajador
    mode_target = 1100 
    sigma = 0.5
    mu = np.log(mode_target) + sigma**2
    
    renta = np.random.lognormal(mean=mu, sigma=sigma)
    # Acotamos por abajo (salarios mínimos/parciales) y por arriba para evitar infinitos anormales
    return float(np.clip(renta, 400.0, 15000.0))

def crear_base_de_datos():
    # Asegurar que el directorio de salida existe
    os.makedirs(os.path.dirname(DATABASE_NAME), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS Base_Datos_MACRO")
    
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
    
    ciudades = ['MAD', 'BAR', 'VAL', 'SEV', 'BIL', 'MAL', 'ZAR']
    registros = []
    contador_ciudadanos = 0
    id_vivienda = 1

    # Estructuramos por Hogares (Unidades de convivencia reales)
    while contador_ciudadanos < TOTAL_REGISTROS:
        tipo_unit = 'fisica' if random.random() < 0.85 else 'virtual'
        ciudad = random.choice(ciudades)
        
        # Asignación de coste de vida regional (Gamma) basado en la provincia
        if ciudad in ('MAD', 'BAR'):
            gamma_hogar = round(random.uniform(1.25, 1.45), 2)
        elif ciudad in ('VAL', 'BIL', 'MAL'):
            gamma_hogar = round(random.uniform(1.05, 1.20), 2)
        else:
            gamma_hogar = round(random.uniform(0.90, 1.00), 2)

        if tipo_unit == 'fisica':
            ref_catastral = f"REF_{ciudad}_{id_vivienda:06d}"
            id_vivienda += 1
            
            # Decidir composición del hogar
            # 1: Persona Sola, 2: Pareja, 3: Familia con 1-2 hijos/dependientes, 4: Piso compartido
            estructura = random.choices([1, 2, 3, 4], weights=[0.30, 0.35, 0.25, 0.10])[0]
            
            if estructura == 1: # Persona Sola
                dni = generar_dni_nie()
                # 80% trabaja/tiene ingresos, 20% desempleo/sin ingresos declarados
                renta = round(generar_renta_log_normal(), 2) if random.random() < 0.80 else 0.0
                registros.append((ref_catastral, 'fisica', 1, dni, renta, 1.0, gamma_hogar))
                contador_ciudadanos += 1
                
            elif estructura == 2: # Pareja
                for i in range(2):
                    if contador_ciudadanos >= TOTAL_REGISTROS: break
                    dni = generar_dni_nie()
                    renta = round(generar_renta_log_normal(), 2) if random.random() < 0.85 else 0.0
                    # El primer adulto computa 1.0 de escala de equivalencia (phi), el segundo 0.5
                    phi_individual = 1.0 if i == 0 else 0.5
                    registros.append((ref_catastral, 'fisica', 1, dni, renta, phi_individual, gamma_hogar))
                    contador_ciudadanos += 1
                    
            elif estructura == 3: # Familia con hijos/dependientes (Simula menores con renta = 0)
                num_adultos = random.choice([1, 2]) # Monoparental o biparental
                num_hijos = random.randint(1, 3)
                
                # Procesar Adultos
                for i in range(num_adultos):
                    if contador_ciudadanos >= TOTAL_REGISTROS: break
                    dni = generar_dni_nie()
                    renta = round(generar_renta_log_normal(), 2) if random.random() < 0.85 else 0.0
                    phi_individual = 1.0 if i == 0 and num_adultos == 2 else 0.5
                    registros.append((ref_catastral, 'fisica', 1, dni, renta, phi_individual, gamma_hogar))
                    contador_ciudadanos += 1
                
                # Procesar Hijos (Tienen escala phi de 0.3 pero NO tienen ingresos de renta)
                for _ in range(num_hijos):
                    if contador_ciudadanos >= TOTAL_REGISTROS: break
                    dni = generar_dni_nie()
                    registros.append((ref_catastral, 'fisica', 1, dni, 0.0, 0.3, gamma_hogar))
                    contador_ciudadanos += 1
                    
            elif estructura == 4: # Piso compartido (Estudiantes / Jóvenes trabajadores)
                inquilinos = random.randint(2, 4)
                for i in range(inquilinos):
                    if contador_ciudadanos >= TOTAL_REGISTROS: break
                    dni = generar_dni_nie()
                    renta = round(generar_renta_log_normal() * 0.7, 2) if random.random() < 0.90 else 0.0
                    # En pisos compartidos de adultos no familiares, cada uno es su propia unidad de consumo básica
                    registros.append((ref_catastral, 'fisica', 1, dni, renta, 1.0, gamma_hogar))
                    contador_ciudadanos += 1

        else: # Unidades Virtuales (Vulnerables, sin techo, empadronamientos flotantes)
            dni = generar_dni_nie()
            ref_catastral = f"VIRTUAL_{dni}"
            # Renta severamente deprimida o inexistente
            renta = round(random.uniform(100, 700), 2) if random.random() < 0.40 else 0.0
            registros.append((ref_catastral, 'virtual', 0, dni, renta, 1.0, gamma_hogar))
            contador_ciudadanos += 1

    # Inserción masiva eficiente
    cursor.executemany('''
        INSERT INTO Base_Datos_MACRO (ref_catastral, tipo_unit, es_habitual, dni_nie_nif, renta_mensual, phi, gamma)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', registros)
    
    conn.commit()
    print(f"¡Base de datos '{DATABASE_NAME}' creada con éxito con {len(registros)} registros!")
    
    # Vista previa de control
    print("\nVista previa de la distribución estructurada (SELECT * LIMIT 15):")
    print(f"{'ref_catastral':<20} | {'tipo_unit':<10} | {'es_h':<4} | {'dni_nie_nif':<12} | {'renta':<8} | {'phi':<5} | {'gamma':<5}")
    print("-" * 75)
    cursor.execute("SELECT * FROM Base_Datos_MACRO LIMIT 15")
    for fila in cursor.fetchall():
        print(f"{fila[0]:<20} | {fila[1]:<10} | {fila[2]:<4} | {fila[3]:<12} | {fila[4]:<8} | {fila[5]:<5} | {fila[6]:<5}")
        
    conn.close()

if __name__ == "__main__":
    crear_base_de_datos()
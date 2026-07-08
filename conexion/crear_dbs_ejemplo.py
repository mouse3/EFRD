import sqlite3
import os

os.makedirs('inputs', exist_ok=True)

def crear_inputs_efrd():
    # INE (Gammas)
    with sqlite3.connect('inputs/ine.db') as conn:
        conn.execute("CREATE TABLE Data_base_INE (codigo_postal INTEGER PRIMARY KEY, gamma REAL)")
        conn.executemany("INSERT INTO Data_base_INE VALUES (?, ?)", [(28001, 1.3), (41001, 0.9), (99999, 1.0)])

    # CNP (Identidad y Edad)
    with sqlite3.connect('inputs/cnp.db') as conn:
        conn.execute("CREATE TABLE Data_base_CNP (dni_nie_nif TEXT PRIMARY KEY, edad INTEGER)")
        conn.executemany("INSERT INTO Data_base_CNP VALUES (?, ?)", [
            ('11111111H', 45), ('22222222J', 10), # Familia Padrón
            ('X1234567L', 30),                     # Extranjero con nómina (Sin casa/Asistencia)
            ('Y9876543M', 60)                      # Sin hogar en Asistencia Social
        ])

    # HACIENDA (Rentas)
    with sqlite3.connect('inputs/hacienda.db') as conn:
        conn.execute("CREATE TABLE Data_base_Hacienda (dni_nie_nif TEXT PRIMARY KEY, renta_mensual REAL)")
        conn.executemany("INSERT INTO Data_base_Hacienda VALUES (?, ?)", [
            ('11111111H', 2500.0), # Padre
            ('X1234567L', 1500.0), # Extranjero activo
            ('Y9876543M', 0.0)     # Sin ingresos
        ])

    # MINISTERIO VIVIENDA (Catastro)
    with sqlite3.connect('inputs/vivienda.db') as conn:
        conn.execute("CREATE TABLE Data_base_Ministerio_Vivienda (ref_catastral TEXT PRIMARY KEY, codigo_postal INTEGER)")
        conn.execute("INSERT INTO Data_base_Ministerio_Vivienda VALUES ('REF_MAD_001', 28001)")

    # PADRÓN (Convivencia Física)
    with sqlite3.connect('inputs/padron.db') as conn:
        conn.execute("CREATE TABLE Data_base_Padron (dni_nie_nif TEXT PRIMARY KEY, ref_catastral TEXT)")
        conn.executemany("INSERT INTO Data_base_Padron VALUES (?, ?)", [
            ('11111111H', 'REF_MAD_001'), ('22222222J', 'REF_MAD_001')
        ])

    # ASISTENCIA SOCIAL (Vulnerabilidad)
    with sqlite3.connect('inputs/asistencia.db') as conn:
        conn.execute("""
            CREATE TABLE Data_base_Asistencia_Social (
                dni_nie_nif TEXT PRIMARY KEY, 
                municipio_asistencia TEXT,
                phi_social REAL,
                gamma_local REAL  -- El municipio define el coste de vida
            )
            """)
        conn.executemany("INSERT INTO Data_base_Asistencia_Social VALUES (?, ?, ?, ?)", [
            ('Y9876543M', 'Madrid', 0.85, 1.35), # Alta vulnerabilidad + ciudad cara
            ('Z1112223K', 'Teruel', 0.70, 0.95)  # Vulnerabilidad media + ciudad barata
        ])

    print(" 6 Bases de datos de INPUT creadas en /inputs")

if __name__ == "__main__":
    crear_inputs_efrd()
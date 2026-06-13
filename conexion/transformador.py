import sqlite3
import os

os.makedirs('outputs', exist_ok=True)
db_output = 'outputs/base_final_efrd.db'
if os.path.exists(db_output): os.remove(db_output)

def ejecutar_transformacion():
    try:
        # Conecta a una base de datos en MEMORIA para la tabla auxiliar
        conn = sqlite3.connect(':memory:') 
        cursor = conn.cursor()

        # Adjunta todas las bases de datos de entrada
        fuentes = ['cnp', 'hacienda', 'ine', 'vivienda', 'padron', 'asistencia']
        for f in fuentes:
            cursor.execute(f"ATTACH DATABASE 'inputs/{f}.db' AS db_{f}")

        # Crea una tabla auxiliar (Solo existe durante la ejecución)
        cursor.execute("""
            CREATE TABLE Habitabilidad_Auxiliar AS
            SELECT 
                C.dni_nie_nif,
                CASE 
                    WHEN P.ref_catastral IS NOT NULL THEN P.ref_catastral
                    ELSE 'VIRTUAL_' || C.dni_nie_nif 
                END as ref_final,
                CASE WHEN P.ref_catastral IS NOT NULL THEN 'fisica' ELSE 'virtual' END as tipo
            FROM db_cnp.Data_base_CNP C
            LEFT JOIN db_padron.Data_base_Padron P ON C.dni_nie_nif = P.dni_nie_nif
            LEFT JOIN db_hacienda.Data_base_Hacienda H ON C.dni_nie_nif = H.dni_nie_nif
            LEFT JOIN db_asistencia.Data_base_Asistencia_Social A ON C.dni_nie_nif = A.dni_nie_nif
            WHERE P.dni_nie_nif IS NOT NULL 
               OR A.dni_nie_nif IS NOT NULL 
               OR (H.renta_mensual IS NOT NULL AND H.renta_mensual > 0)
        """)

        # Crea una Base de datos final (Archivo Físico .db) con las columnas del inquilino aplanadas
        cursor.execute(f"ATTACH DATABASE '{db_output}' AS db_final")
        cursor.execute("""
            CREATE TABLE db_final.Base_Datos_FINAL (
                ref_catastral TEXT,
                tipo_unit TEXT,
                es_habitual INTEGER,
                dni_nie_nif TEXT,
                renta_mensual REAL,
                phi REAL,
                gamma REAL,
                PRIMARY KEY (ref_catastral, dni_nie_nif) -- Clave compuesta para evitar duplicados exactos
            )
        """)

        # Procesamiento e inserta directa (Sin bucles de Python)
        query_insercion_directa = """
        INSERT INTO db_final.Base_Datos_FINAL
        SELECT 
            AUX.ref_final as ref_catastral,
            AUX.tipo as tipo_unit,
            1 as es_habitual,
            C.dni_nie_nif,
            COALESCE(H.renta_mensual, 0.0) as renta_mensual,
            -- LÓGICA PHI
            CASE 
                WHEN C.edad < 18 THEN 0.3
                WHEN AUX.tipo = 'virtual' AND A.phi_social IS NOT NULL THEN A.phi_social
                WHEN C.edad >= 18 AND COALESCE(H.renta_mensual, 0.0) > 0 THEN 1
                ELSE 0.5 
            END as phi,
            -- LÓGICA GAMMA
            CASE 
                WHEN AUX.tipo = 'virtual' AND A.gamma_local IS NOT NULL THEN A.gamma_local 
                ELSE COALESCE(I.gamma, 1.0) 
            END as gamma
        FROM Habitabilidad_Auxiliar AUX
        JOIN db_cnp.Data_base_CNP C ON AUX.dni_nie_nif = C.dni_nie_nif
        LEFT JOIN db_hacienda.Data_base_Hacienda H ON C.dni_nie_nif = H.dni_nie_nif
        LEFT JOIN db_asistencia.Data_base_Asistencia_Social A ON C.dni_nie_nif = A.dni_nie_nif
        LEFT JOIN db_padron.Data_base_Padron P ON C.dni_nie_nif = P.dni_nie_nif
        LEFT JOIN db_vivienda.Data_base_Ministerio_Vivienda V ON P.ref_catastral = V.ref_catastral
        LEFT JOIN db_ine.Data_base_INE I ON V.codigo_postal = I.codigo_postal
        """

        # Ejecuta la inserción masiva directamente en SQL
        cursor.execute(query_insercion_directa)

        conn.commit()
        conn.close()
        print(f" Transformación completa (Formato Largo). Resultado en: {db_output}")

    except Exception as e:
        print(f"ERROR CRÍTICO: {type(e).__name__}\n{e}")

ejecutar_transformacion()
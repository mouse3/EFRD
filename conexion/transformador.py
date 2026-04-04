import sqlite3
import os

os.makedirs('outputs', exist_ok=True)
db_output = 'outputs/base_final_efrd.db'
if os.path.exists(db_output): os.remove(db_output)

def ejecutar_transformacion():
    try:
        # Conectamos a una base de datos en MEMORIA para la tabla auxiliar
        # Esto asegura que Habitabilidad_Real no sea un archivo físico

        conn = sqlite3.connect(':memory:') 
        cursor = conn.cursor()

        # Adjuntar todas las bases de datos de entrada
        fuentes = ['cnp', 'hacienda', 'ine', 'vivienda', 'padron', 'asistencia']
        for f in fuentes:
            cursor.execute(f"ATTACH DATABASE 'inputs/{f}.db' AS db_{f}")

        # crear tabla auxiliar (Solo existe durante la ejecución)
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
            -- REGLA DE EXCLUSIÓN: Solo entran si están en Padrón, Asistencia o tienen Nómina
            WHERE P.dni_nie_nif IS NOT NULL 
               OR A.dni_nie_nif IS NOT NULL 
               OR (H.renta_mensual IS NOT NULL AND H.renta_mensual > 0)
        """)

        # Crear Base de datos final (Archivo Físico .db)
        cursor.execute(f"ATTACH DATABASE '{db_output}' AS db_final")
        cursor.execute("""
            CREATE TABLE db_final.Base_Datos_FINAL (
                ref_catastral TEXT PRIMARY KEY,
                tipo_unit TEXT,
                es_habitual INTEGER,
                lista_inquilinos TEXT,
                gamma REAL
            )
        """)

        # PROCESAR Y AGRUPAR (Lógica Phi y Analogía CSV)
        # Obtenemos los datos detallados cruzando la auxiliar con el resto
        query_cruce = """
        SELECT 
            AUX.ref_final,
            AUX.tipo,
            C.dni_nie_nif,
            COALESCE(H.renta_mensual, 0.0),
            -- LÓGICA PHI (Ya definida)
            CASE 
                WHEN C.edad < 18 THEN 0.3
                WHEN AUX.tipo = 'virtual' AND A.phi_social IS NOT NULL THEN A.phi_social
                WHEN C.edad >= 18 AND COALESCE(H.renta_mensual, 0.0) > 0 THEN 1
                ELSE 0.5 
            END as phi_final,
            -- LÓGICA GAMMA (NUEVA PRIORIDAD)
            CASE 
                WHEN AUX.tipo = 'virtual' AND A.gamma_local IS NOT NULL THEN A.gamma_local -- Prioridad Municipio para Virtuales
                ELSE COALESCE(I.gamma, 1.0) -- Prioridad INE para Físicas (o fallback a 1.0)
            END as gamma_final
        FROM Habitabilidad_Auxiliar AUX
        JOIN db_cnp.Data_base_CNP C ON AUX.dni_nie_nif = C.dni_nie_nif
        LEFT JOIN db_hacienda.Data_base_Hacienda H ON C.dni_nie_nif = H.dni_nie_nif
        LEFT JOIN db_asistencia.Data_base_Asistencia_Social A ON C.dni_nie_nif = A.dni_nie_nif
        LEFT JOIN db_padron.Data_base_Padron P ON C.dni_nie_nif = P.dni_nie_nif
        LEFT JOIN db_vivienda.Data_base_Ministerio_Vivienda V ON P.ref_catastral = V.ref_catastral
        LEFT JOIN db_ine.Data_base_INE I ON V.codigo_postal = I.codigo_postal
        """

        cursor.execute(query_cruce)
        filas = cursor.fetchall()

        # Agrupación por vivienda
        agrupado = {}
        for ref, tipo, dni, renta, phi, gamma in filas:
            if ref not in agrupado:
                agrupado[ref] = {'tipo': tipo, 'gamma': gamma, 'inquilinos': []}
            agrupado[ref]['inquilinos'].append((dni, renta, phi))

        # Inserción final
        for ref, d in agrupado.items():
            cursor.execute("INSERT INTO db_final.Base_Datos_FINAL VALUES (?, ?, ?, ?, ?)",
                            (ref, d['tipo'], 1, str(d['inquilinos']), d['gamma']))

        conn.commit()
        conn.close()
        print(f" Transformación completa. Tabla auxiliar destruida. Resultado en: {db_output}")

    except Exception as e:
        print(f"ERROR CRÍTICO: {type(e).__name__}\n{e}")

ejecutar_transformacion()
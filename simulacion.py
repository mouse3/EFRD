# simulacion.py
"""
Procesador de simulación EFRD.
Calcula la cuota individual de cada ciudadano y escribe los resultados en la BD.
"""
import sqlite3
from math import exp

# Prefijos que identifican referencias catastrales sintéticas/virtuales.
PREFIJOS_REF_VIRTUAL = ("VIRTUAL_", "SIN_REF", "TEST_", "MOCK_")


def _es_ref_virtual(ref_catastral: str) -> bool:
    """Devuelve True si la referencia catastral es sintética, no real."""
    if not ref_catastral:
        return True
    ref_upper = ref_catastral.upper()
    return any(ref_upper.startswith(p) for p in PREFIJOS_REF_VIRTUAL)

def procesar_simulacion_efrd(motor, db_path: str, tabla_origen: str, ciclo_id: str = None):
    """
    Lee cada hogar del motor, calcula su cuota y escribe en 'resultados_ciudadanos'.

    Parámetro ciclo_id (Fleco 12): identificador del ciclo de ejecución (e.g. "2024-11").
    Si se proporciona, se guarda en cada fila para mantener histórico multiciclo.
    """
    tabla_destino = "resultados_ciudadanos"

    with sqlite3.connect(db_path) as conn:
        # Migración de esquema: si la tabla existe con el esquema antiguo la eliminamos.
        cursor = conn.execute(f"PRAGMA table_info({tabla_destino})")
        columnas_existentes = cursor.fetchall()
        if columnas_existentes and len(columnas_existentes) != 10:
            print(f"[simulacion] Esquema antiguo detectado ({len(columnas_existentes)} columnas). Recreando tabla...")
            conn.execute(f"DROP TABLE IF EXISTS {tabla_destino}")

        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {tabla_destino} (
                ciclo_id         TEXT,
                ref_catastral    TEXT,
                renta_total      REAL,
                phi_total        REAL,
                gamma            REAL,
                k_hogar          REAL,
                cuota            REAL,
                neto             REAL,
                tipo_efectivo    REAL,
                estado           TEXT
            )
        """)

        if ciclo_id is None:
            conn.execute(f"DELETE FROM {tabla_destino}")
        else:
            conn.execute(f"DELETE FROM {tabla_destino} WHERE ciclo_id = ?", (ciclo_id,))

        from EFRD import EFRD_Protocol_v4_1

        filas = []
        for hogar in motor.unidades_convivencia:
            renta         = hogar["renta_total"]
            phi           = hogar["phi_total"]
            gamma         = hogar["gamma"]
            ref_catastral = hogar.get("ref_catastral", "")
            k_hogar       = motor.k_base * phi * gamma
            diferencial   = renta - k_hogar

            if diferencial > 0:
                x      = EFRD_Protocol_v4_1._calcular_x(diferencial, k_hogar)
                tasa   = motor.L * (1 - exp(-motor.sigma * abs(x)))
                cuota  = diferencial * tasa
                neto   = renta - cuota
                tipo_e = (cuota / renta * 100) if renta > 0 else 0
                estado = "CONTRIBUYENTE"
            else:
                cuota  = diferencial                    # negativo → subsidio
                neto   = renta + abs(diferencial)
                tipo_e = -(abs(diferencial) / renta * 100) if renta > 0 else -100
                # -------------------------------------------------------------
                # ¡SOLUCIÓN AL ERROR! Inicializamos la variable faltante
                # -------------------------------------------------------------
                estado = "RECEPTOR" 

            filas.append((
                ciclo_id,
                ref_catastral,
                renta, phi, gamma, k_hogar,
                cuota, neto, tipo_e, estado
            ))

        conn.executemany(
            f"INSERT INTO {tabla_destino} VALUES (?,?,?,?,?,?,?,?,?,?)", filas
        )

        n_auditoria = sum(1 for f in filas if f[-1] == "AUDITORÍA")
        n_virtual   = sum(1 for f in filas if _es_ref_virtual(f[1] or ""))
        print(f"[simulacion] {len(filas):,} hogares procesados → tabla '{tabla_destino}'")
        if n_virtual:
            print(f"[simulacion]   {n_virtual:,} hogares con ref. virtual")
        if n_auditoria:
            print(f"[simulacion] ⚠ {n_auditoria:,} hogares marcados como AUDITORÍA (renta baja en zona de alto coste)")
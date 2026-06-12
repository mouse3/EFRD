# simulacion.py
"""
Procesador de simulación EFRD.
Calcula la cuota individual de cada ciudadano y escribe los resultados en la BD.
"""
import sqlite3
from math import exp

# ─────────────────────────────────────────────────────────────────────────────
# Fleco 13: parámetros de detección de fraude potencial
# ─────────────────────────────────────────────────────────────────────────────
UMBRAL_GAMMA_SOSPECHOSO = 1.3   # configurable: coste de vida alto
UMBRAL_RENTA_CERO = 100         # EUR/mes — por debajo se considera "declaración cero"


def _detectar_fraude_potencial(renta: float, gamma: float) -> bool:
    """
    Fleco 13: marca un hogar para revisión manual si declara renta muy baja
    pero vive en una zona de coste de vida elevado.
    No bloquea el subsidio automáticamente; lo pone en cola de auditoría.
    """
    return renta < UMBRAL_RENTA_CERO and gamma > UMBRAL_GAMMA_SOSPECHOSO


def procesar_simulacion_efrd(motor, db_path: str, tabla_origen: str, ciclo_id: str = None):
    """
    Lee cada hogar del motor, calcula su cuota y escribe en 'resultados_ciudadanos'.

    Parámetro ciclo_id (Fleco 12): identificador del ciclo de ejecución (e.g. "2024-11").
    Si se proporciona, se guarda en cada fila para mantener histórico multiciclo.
    """
    tabla_destino = "resultados_ciudadanos"

    with sqlite3.connect(db_path) as conn:
        # Migración de esquema: si la tabla existe con el esquema antiguo (5 columnas)
        # la eliminamos para recrearla con el nuevo esquema de 10 columnas.
        cursor = conn.execute(f"PRAGMA table_info({tabla_destino})")
        columnas_existentes = cursor.fetchall()
        if columnas_existentes and len(columnas_existentes) != 10:
            print(f"[simulacion] Esquema antiguo detectado ({len(columnas_existentes)} columnas). Recreando tabla...")
            conn.execute(f"DROP TABLE IF EXISTS {tabla_destino}")

        # Fleco 12: esquema completo con ciclo_id para histórico de ejecuciones
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

        # Si no hay ciclo_id se limpia la tabla (compatibilidad con ejecución simple)
        if ciclo_id is None:
            conn.execute(f"DELETE FROM {tabla_destino}")
        else:
            # Con ciclos: solo se borran las filas del ciclo actual para permitir re-ejecuciones
            conn.execute(f"DELETE FROM {tabla_destino} WHERE ciclo_id = ?", (ciclo_id,))

        filas = []
        for hogar in motor.unidades_convivencia:
            renta   = hogar["renta_total"]
            phi     = hogar["phi_total"]
            gamma   = hogar["gamma"]
            k_hogar = motor.k_base * phi * gamma

            diferencial = renta - k_hogar

            if diferencial > 0:
                # Fleco 4: usa _calcular_x (importado desde el motor)
                from EFRD import EFRD_Protocol_v4_1
                x      = EFRD_Protocol_v4_1._calcular_x(diferencial, k_hogar)
                tasa   = motor.L * (1 - exp(-motor.sigma * abs(x)))
                cuota  = diferencial * tasa
                neto   = renta - cuota
                tipo_e = (cuota / renta * 100) if renta > 0 else 0
                estado = "CONTRIBUYENTE"
            else:
                cuota  = diferencial           # negativo → subsidio
                neto   = renta + abs(diferencial)
                tipo_e = -(abs(diferencial) / renta * 100) if renta > 0 else -100

                # Fleco 13: detección de fraude potencial
                if _detectar_fraude_potencial(renta, gamma):
                    estado = "AUDITORÍA"       # subsidio emitido pero marcado para revisión
                else:
                    estado = "RECEPTOR"

            filas.append((
                ciclo_id,
                hogar.get("ref_catastral", ""),
                renta, phi, gamma, k_hogar,
                cuota, neto, tipo_e, estado
            ))

        conn.executemany(
            f"INSERT INTO {tabla_destino} VALUES (?,?,?,?,?,?,?,?,?,?)", filas
        )

        auditoria = sum(1 for f in filas if f[-1] == "AUDITORÍA")
        print(f"[simulacion] {len(filas)} hogares procesados → tabla '{tabla_destino}'")
        if auditoria > 0:
            print(f"[simulacion] ⚠ {auditoria} hogares marcados como AUDITORÍA (Fleco 13: fraude potencial)")
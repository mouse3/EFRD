"""
Procesador de simulación EFRD.
Calcula la cuota individual de cada hogar y escribe los resultados en la BD.

Coherencia con el núcleo matemático
------------------------------------
Usa EXACTAMENTE la misma fórmula que EFRD.simular_balance y
EFRD.calcular_cuota_hogar: T = L·[ r^(1+σ)/(r^σ+u^σ) − u/2 ], C = r − T.

La versión anterior calculaba la cuota con una tasa exponencial
`L·(1 − e^(−σ|x|))` distinta de la del motor, y encima llamaba a
`EFRD_Protocol_v4_1._calcular_x`, un método que ya no existe en el motor
corregido (era código muerto de una fórmula previa). Esa divergencia es
precisamente lo que 'main.py' detecta y reporta como hogares con
Σ cuotas individuales ≠ cuota del hogar: no es un hecho esperable del
modelo, era este bug. Con el cambio de abajo esa divergencia desaparece.
"""
import sqlite3

from EFRD import EFRD_Protocol_v4_1

# Prefijos que identifican referencias catastrales sintéticas/virtuales.
PREFIJOS_REF_VIRTUAL = ("VIRTUAL_", "SIN_REF", "TEST_", "MOCK_")

NUM_COLUMNAS_TABLA = 10


def _es_ref_virtual(ref_catastral: str) -> bool:
    """Devuelve True si la referencia catastral es sintética, no real."""
    if not ref_catastral:
        return True
    ref_upper = ref_catastral.upper()
    return any(ref_upper.startswith(p) for p in PREFIJOS_REF_VIRTUAL)


def procesar_simulacion_efrd(motor, db_path: str, tabla_origen: str, ciclo_id: str = None):
    """
    Lee cada hogar del motor, calcula su cuota con la fórmula general y escribe
    en 'resultados_ciudadanos'.

    Parámetro ciclo_id: identificador del ciclo de ejecución (p.ej. "2024-11").
    Si se proporciona, se guarda en cada fila para mantener histórico multiciclo
    y solo se borran las filas de ese ciclo; si es None se borra la tabla entera.
    """
    tabla_destino = "resultados_ciudadanos"

    with sqlite3.connect(db_path) as conn:
        # Migración de esquema: si la tabla existe con un esquema antiguo, se elimina.
        cursor = conn.execute(f"PRAGMA table_info({tabla_destino})")
        columnas_existentes = cursor.fetchall()
        if columnas_existentes and len(columnas_existentes) != NUM_COLUMNAS_TABLA:
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

        filas = []
        for hogar in motor.unidades_convivencia:
            renta = hogar["renta_total"]
            phi = hogar["phi_total"]
            gamma = hogar["gamma"]
            ref_catastral = hogar.get("ref_catastral", "")
            k_hogar = motor.k_base * phi * gamma

            # Fórmula general única: la misma que usan simular_balance,
            # calcular_cuota_hogar y las liquidaciones de main.py.
            neto, cuota = EFRD_Protocol_v4_1.formula_general(renta, k_hogar, motor.L, motor.sigma)
            tipo_e = (cuota / renta * 100) if renta > 0 else None

            if cuota > 0:
                estado = "CONTRIBUYENTE"
            elif cuota < 0:
                estado = "RECEPTOR"
            else:
                estado = "NEUTRO"

            filas.append((
                ciclo_id,
                ref_catastral,
                renta, phi, gamma, k_hogar,
                cuota, neto, tipo_e, estado
            ))

        conn.executemany(
            f"INSERT INTO {tabla_destino} VALUES (?,?,?,?,?,?,?,?,?,?)", filas
        )

        n_contribuyentes = sum(1 for f in filas if f[-1] == "CONTRIBUYENTE")
        n_receptores = sum(1 for f in filas if f[-1] == "RECEPTOR")
        n_neutros = sum(1 for f in filas if f[-1] == "NEUTRO")
        n_virtual = sum(1 for f in filas if _es_ref_virtual(f[1] or ""))

        print(f"[simulacion] {len(filas):,} hogares procesados → tabla '{tabla_destino}'")
        print(f"[simulacion]   Contribuyentes: {n_contribuyentes:,} | Receptores: {n_receptores:,} | Neutros: {n_neutros:,}")
        if n_virtual:
            print(f"[simulacion]   {n_virtual:,} hogares con ref. virtual")
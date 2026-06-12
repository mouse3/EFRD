import os
import argparse
import sqlite3
from EFRD import EFRD_Protocol_v4_1, EFRD_AdvancedVisualizer, EFRD_AnalyticVisualizer
from traductores import get_pib_nominal_precios_corrientes, get_IPC_mas_reciente
from simulacion import procesar_simulacion_efrd

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Motor EFRD v4.1")
parser.add_argument("--gop", type=float, default=0.0,
    help="Gastos operativos del Estado en EUR (OBLIGATORIO para análisis de solvencia real).")
parser.add_argument("--modo", type=str, default="interactivo",
    choices=["interactivo", "deuda", "ajuste", "test"],
    help="Modo de resolución de insolvencia: interactivo | deuda | ajuste | test")
args = parser.parse_args()

if args.gop == 0.0:
    print("[AVISO] G_op = 0. La inecuación de solvencia no incluye gastos operativos del Estado.")
    print("        Proporcione --gop <valor_EUR> para un análisis real.")

gastos_operativos_estado = args.gop
MODO_HEADLESS = os.environ.get("EFRD_HEADLESS", "0") == "1"

path_db  = "conexion/outputs/Base_Datos_MACRO.db"
tabla    = "Base_Datos_MACRO"
path_liquidaciones = "conexion/outputs/Liquidaciones_EFRD.db"

# ─────────────────────────────────────────────────────────────────────────────
# ARRANQUE DEL MOTOR
# ─────────────────────────────────────────────────────────────────────────────
PIB_anyo, PIB_valor = get_pib_nominal_precios_corrientes()
IPC_anyo, IPC_valor = get_IPC_mas_reciente()

print(f"PIB más reciente (año {PIB_anyo}): {PIB_valor} €")
print(f"IPC más reciente (año {IPC_anyo}): {IPC_valor}")
print("Iniciando motor EFRD. Procesando base de datos catastral...")

motor = EFRD_Protocol_v4_1(
    PIB_Y=PIB_valor,
    Gini=0.33,
    Alpha=0.05,
    Sigma=1.5,
    Limite_L=0.80,
    IPC_Pi=IPC_valor,
    G_op=gastos_operativos_estado,
    db_path=path_db,
    tabla_central=tabla,
    modo=args.modo
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. SIMULACIÓN (escribe resultados_ciudadanos en la BD principal)
# ─────────────────────────────────────────────────────────────────────────────
procesar_simulacion_efrd(
    motor=motor,
    db_path=path_db,
    tabla_origen=tabla,
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. TABLA DE LIQUIDACIONES POR HOGAR
#    Lee resultados_ciudadanos y agrega por ref_catastral:
#      - cuota_hogar   : suma de cuotas individuales del hogar (>0 contribuyente, <0 subsidio)
#      - tipo_efectivo : tipo efectivo medio ponderado por renta
#      - estado        : CONTRIBUYENTE | RECEPTOR | MIXTO | AUDITORÍA
#    Escribe en Liquidaciones_EFRD.db → tabla liquidaciones_hogares
# ─────────────────────────────────────────────────────────────────────────────
def generar_liquidaciones(path_origen: str, path_destino: str) -> int:
    """
    Agrega resultados_ciudadanos por ref_catastral y escribe la tabla
    liquidaciones_hogares en una BD separada.
    Devuelve el número de hogares procesados.
    """
    with sqlite3.connect(path_origen) as conn_src:
        cursor = conn_src.cursor()
        cursor.execute("""
            SELECT
                ref_catastral,
                SUM(renta_total)                                        AS renta_bruta_hogar,
                SUM(neto)                                               AS renta_neta_hogar,
                SUM(cuota)                                              AS cuota_hogar,
                CASE
                    WHEN SUM(renta_total) > 0
                    THEN ROUND(SUM(cuota) / SUM(renta_total) * 100, 4)
                    ELSE 0
                END                                                     AS tipo_efectivo_pct,
                CASE
                    WHEN SUM(cuota) > 0           THEN 'CONTRIBUYENTE'
                    WHEN SUM(cuota) < 0           THEN 'RECEPTOR'
                    WHEN MAX(estado) = 'AUDITORÍA' THEN 'AUDITORÍA'
                    ELSE 'NEUTRO'
                END                                                     AS estado_hogar
            FROM resultados_ciudadanos
            WHERE ref_catastral IS NOT NULL AND ref_catastral != ''
            GROUP BY ref_catastral
            ORDER BY cuota_hogar DESC
        """)
        filas = cursor.fetchall()

    os.makedirs(os.path.dirname(path_destino), exist_ok=True)
    with sqlite3.connect(path_destino) as conn_dst:
        conn_dst.execute("DROP TABLE IF EXISTS liquidaciones_hogares")
        conn_dst.execute("""
            CREATE TABLE liquidaciones_hogares (
                ref_catastral       TEXT PRIMARY KEY,
                renta_bruta_hogar   REAL,   -- suma de rentas individuales brutas del hogar (€/mes)
                renta_neta_hogar    REAL,   -- suma de rentas netas tras cuota/subsidio (€/mes)
                cuota_hogar         REAL,   -- importe a ingresar (+) o recibir (-) en €/mes
                tipo_efectivo_pct   REAL,   -- porcentaje efectivo sobre renta bruta
                estado_hogar        TEXT    -- CONTRIBUYENTE | RECEPTOR | AUDITORÍA | NEUTRO
            )
        """)
        conn_dst.executemany(
            "INSERT INTO liquidaciones_hogares VALUES (?,?,?,?,?,?)", filas
        )

    contribuyentes = sum(1 for f in filas if f[5] == "CONTRIBUYENTE")
    receptores     = sum(1 for f in filas if f[5] == "RECEPTOR")
    auditoria      = sum(1 for f in filas if f[5] == "AUDITORÍA")
    total_recaudado = sum(f[2] for f in filas if f[2] > 0)
    total_subsidios = sum(abs(f[2]) for f in filas if f[2] < 0)

    print(f"\n[liquidaciones] {len(filas):,} hogares escritos en '{path_destino}'")
    print(f"  Contribuyentes : {contribuyentes:,}")
    print(f"  Receptores     : {receptores:,}")
    print(f"  Auditoría      : {auditoria:,}")
    print(f"  Recaudación    : {total_recaudado:,.2f} €/mes")
    print(f"  Subsidios      : {total_subsidios:,.2f} €/mes")
    return len(filas)


generar_liquidaciones(path_db, path_liquidaciones)

# ─────────────────────────────────────────────────────────────────────────────
# 3. VISUALIZADOR
# ─────────────────────────────────────────────────────────────────────────────
visualizador = EFRD_AnalyticVisualizer(motor)

visualizador.graficar_curva_sostenibilidad(
    guardar=MODO_HEADLESS, ruta="ejemplos/salida/sostenibilidad.png")
visualizador.graficar_ingreso_bruto_vs_neto(
    guardar=MODO_HEADLESS, ruta="ejemplos/salida/bruto_vs_neto.png")
visualizador.graficar_tipo_impositivo_efectivo(
    guardar=MODO_HEADLESS, ruta="ejemplos/salida/tipo_efectivo.png")
visualizador.graficar_mapa_calor_bienestar(
    guardar=MODO_HEADLESS, ruta="ejemplos/salida/mapa_calor.png")
visualizador.graficar_distribucion_ingresos(
    guardar=MODO_HEADLESS, ruta="ejemplos/salida/distribucion_ingresos.png")
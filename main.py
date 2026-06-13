import os
import argparse
import sqlite3
from EFRD import EFRD_Protocol_v4_1, EFRD_AdvancedVisualizer, EFRD_AnalyticVisualizer
from traductores import get_pib_nominal_precios_corrientes, get_IPC_mas_reciente
from simulacion import procesar_simulacion_efrd

# CLI
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

path_db            = "conexion/outputs/Base_Datos_MACRO.db"
tabla              = "Base_Datos_MACRO"
path_liquidaciones = "conexion/outputs/Liquidaciones_EFRD.db"

# Arranque del motor
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

# Escribe resultados_ciudadanos en la BD principal)
procesar_simulacion_efrd(
    motor=motor,
    db_path=path_db,
    tabla_origen=tabla,
)

"""
Tabla de liquidaciones por hogar
Columnas:
  renta_bruta_hogar  — renta propia del hogar (siempre >= 0)
  cuota_hogar        — a ingresar en Hacienda (+) o a recibir del Estado (-)
  renta_neta_hogar   — renta_bruta - cuota  (contribuyentes)
                       renta_bruta + |cuota| (receptores con renta > 0)
                       0 cuando renta_bruta = 0  (el subsidio va a subsidio_estatal)
  subsidio_estatal   — aportación pura del Estado cuando renta_bruta = 0
  tipo_efectivo_pct  — cuota / renta_bruta * 100  (NULL si renta_bruta = 0)
  estado_hogar       — CONTRIBUYENTE | RECEPTOR | AUDITORÍA | NEUTRO
"""
def generar_liquidaciones(path_origen: str, path_destino: str) -> int:
    with sqlite3.connect(path_origen) as conn_src:
        cursor = conn_src.cursor()
        cursor.execute("""
            SELECT
                ref_catastral,

                MAX(SUM(renta_total), 0)            AS renta_bruta_hogar,

                SUM(cuota)                          AS cuota_hogar,

                -- Neto = renta propia tras cuota; 0 cuando no hay renta propia
                CASE
                    WHEN SUM(renta_total) > 0
                    THEN SUM(renta_total) - SUM(cuota)
                    ELSE 0
                END                                 AS renta_neta_hogar,

                -- Subsidio puro: solo cuando el hogar no tiene renta propia
                CASE
                    WHEN SUM(renta_total) <= 0 AND SUM(cuota) < 0
                    THEN ABS(SUM(cuota))
                    ELSE 0
                END                                 AS subsidio_estatal,

                -- Tipo efectivo: sin base imponible no tiene sentido calcularlo
                CASE
                    WHEN SUM(renta_total) > 0
                    THEN ROUND(SUM(cuota) / SUM(renta_total) * 100, 4)
                    ELSE NULL
                END                                 AS tipo_efectivo_pct,

                -- AUDITORÍA tiene prioridad sobre el signo de la cuota
                CASE
                    WHEN MAX(estado) = 'AUDITORÍA'  THEN 'AUDITORÍA'
                    WHEN SUM(cuota)  >  0            THEN 'CONTRIBUYENTE'
                    WHEN SUM(cuota)  <  0            THEN 'RECEPTOR'
                    ELSE 'NEUTRO'
                END                                 AS estado_hogar,

                -- phi_total y gamma son iguales para todos los miembros del hogar;
                -- MAX() los extrae sin necesidad de un subquery adicional.
                MAX(phi_total)                      AS phi_total,
                MAX(gamma)                          AS gamma

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
                ref_catastral      TEXT PRIMARY KEY,
                renta_bruta_hogar  REAL,  -- renta propia del hogar (€/mes, >= 0)
                cuota_hogar        REAL,  -- a ingresar (+) o recibir (-) del Estado (€/mes)
                renta_neta_hogar   REAL,  -- renta disponible tras cuota (0 si bruta era 0)
                subsidio_estatal   REAL,  -- aportación pura del Estado cuando bruta = 0 (€/mes)
                tipo_efectivo_pct  REAL,  -- cuota/bruta*100; NULL si sin base imponible
                estado_hogar       TEXT,  -- CONTRIBUYENTE | RECEPTOR | AUDITORÍA | NEUTRO
                phi_total          REAL,  -- multiplicador de composición familiar (k_base × phi × gamma = k_hogar)
                gamma              REAL   -- índice de coste de vida del municipio
            )
        """)
        conn_dst.executemany(
            "INSERT INTO liquidaciones_hogares VALUES (?,?,?,?,?,?,?,?,?)", filas
        )

    # Índices: 0=ref, 1=bruta, 2=cuota, 3=neta, 4=subsidio, 5=tipo, 6=estado, 7=phi, 8=gamma
    contribuyentes  = sum(1 for f in filas if f[6] == "CONTRIBUYENTE")
    receptores      = sum(1 for f in filas if f[6] == "RECEPTOR")
    auditoria       = sum(1 for f in filas if f[6] == "AUDITORÍA")
    sin_renta       = sum(1 for f in filas if f[1] == 0)
    total_recaudado = sum(f[2] for f in filas if f[2] is not None and f[2] > 0)
    total_subsidios = sum(abs(f[2]) for f in filas if f[2] is not None and f[2] < 0)
    total_subsidio_puro = sum(f[4] for f in filas if f[4] is not None and f[4] > 0)

    print(f"\n[liquidaciones] {len(filas):,} hogares escritos en '{path_destino}'")
    print(f"  Contribuyentes      : {contribuyentes:,}")
    print(f"  Receptores          : {receptores:,}")
    print(f"  Auditoría           : {auditoria:,}")
    print(f"  Sin renta propia    : {sin_renta:,}  (subsidio íntegro del Estado)")
    print(f"  Recaudación         : {total_recaudado:,.2f} €/mes")
    print(f"  Subsidios totales   : {total_subsidios:,.2f} €/mes")
    print(f"  Subsidio puro (bruta=0): {total_subsidio_puro:,.2f} €/mes")
    return len(filas)


generar_liquidaciones(path_db, path_liquidaciones)

# Visualizador
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
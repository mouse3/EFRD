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
                       k_hogar (receptores: garantiza suelo de dignidad)
  subsidio_estatal   — aportación pura del Estado (valor absoluto de la cuota negativa)
  tipo_efectivo_pct  — cuota / renta_bruta * 100  (NULL si renta_bruta = 0)
  estado_hogar       — CONTRIBUYENTE | RECEPTOR | NEUTRO
"""
def generar_liquidaciones(path_origen: str, path_destino: str) -> int:
    """"""
    with sqlite3.connect(path_origen) as conn_src:
        cursor = conn_src.cursor()
        # SQL agrupa los datos brutos por vivienda de forma eficiente
        cursor.execute("""
            SELECT
                ref_catastral,
                SUM(renta_total)  AS renta_bruta_raw,
                SUM(cuota)        AS cuota_hogar,
                MAX(phi_total)    AS phi_total,
                MAX(gamma)        AS gamma
            FROM resultados_ciudadanos
            WHERE ref_catastral IS NOT NULL AND ref_catastral != ''
            GROUP BY ref_catastral
            ORDER BY cuota_hogar DESC
        """)
        filas_raw = cursor.fetchall()

    filas = []
    for row in filas_raw:
        ref_catastral, renta_bruta_raw, cuota_hogar, phi_total, gamma = row
        
        # Asegurar consistencia de ingresos mínimos
        renta_bruta_hogar = max(renta_bruta_raw, 0.0)
        
        # Calcular el umbral de dignidad dinámico usando la instancia global 'motor'
        k_hogar = motor.k_base * phi_total * gamma
        
        # ---------------------------------------------------------------------
        # LÓGICA ADAPTADA ESTRICTAMENTE A LA DOCUMENTACIÓN
        # ---------------------------------------------------------------------
        
        # CASO 1: Contribuyente (renta > k_hogar)
        if renta_bruta_hogar > k_hogar:
            renta_neta_hogar = renta_bruta_hogar - cuota_hogar
            subsidio_estatal = 0.0
            tipo_efectivo_pct = round((cuota_hogar / renta_bruta_hogar) * 100, 4)
            estado_hogar = 'CONTRIBUYENTE'
            
        # CASO 2: Receptor con renta bajo el umbral (0 < renta <= k_hogar)
        elif 0 < renta_bruta_hogar <= k_hogar:
            renta_neta_hogar = k_hogar
            # Se usa el valor absoluto para representar el impacto positivo del subsidio en las arcas
            subsidio_estatal = abs(cuota_hogar) 
            tipo_efectivo_pct = round((cuota_hogar / renta_bruta_hogar) * 100, 4)
            estado_hogar = 'RECEPTOR'
            
        # CASO 3: Receptor estricto sin renta (renta = 0)
        else:
            renta_neta_hogar = k_hogar
            subsidio_estatal = abs(cuota_hogar)
            tipo_efectivo_pct = None  # Semánticamente correcto: sin base imponible
            estado_hogar = 'RECEPTOR'
            
        # Empaquetamos respetando el orden exacto de la base de datos destino
        filas.append((
            ref_catastral,
            renta_bruta_hogar,
            cuota_hogar,
            renta_neta_hogar,
            subsidio_estatal,
            tipo_efectivo_pct,
            estado_hogar,
            phi_total,
            gamma
        ))

    # Escritura en la base de datos de liquidaciones
    os.makedirs(os.path.dirname(path_destino), exist_ok=True)
    with sqlite3.connect(path_destino) as conn_dst:
        conn_dst.execute("DROP TABLE IF EXISTS liquidaciones_hogares")
        conn_dst.execute("""
            CREATE TABLE liquidaciones_hogares (
                ref_catastral      TEXT PRIMARY KEY,
                renta_bruta_hogar  REAL,
                cuota_hogar        REAL,
                renta_neta_hogar   REAL,
                subsidio_estatal   REAL,
                tipo_efectivo_pct  REAL,
                estado_hogar       TEXT,
                phi_total          REAL,
                gamma              REAL
            )
        """)
        conn_dst.executemany(
            "INSERT INTO liquidaciones_hogares VALUES (?,?,?,?,?,?,?,?,?)", filas
        )

    # Métricas consolidadas según la nueva estructura de la documentación
    contribuyentes  = sum(1 for f in filas if f[6] == "CONTRIBUYENTE")
    receptores      = sum(1 for f in filas if f[6] == "RECEPTOR")
    sin_renta       = sum(1 for f in filas if f[1] == 0)
    total_recaudado = sum(f[2] for f in filas if f[2] is not None and f[2] > 0)
    total_subsidios = sum(abs(f[2]) for f in filas if f[2] is not None and f[2] < 0)
    
    # Ajuste fino: Filtrado exacto para el subsidio puro donde la renta es estrictamente 0
    total_subsidio_puro = sum(f[4] for f in filas if f[1] == 0)

    print(f"\n[liquidaciones] {len(filas):,} hogares escritos en '{path_destino}'")
    print(f"  Contribuyentes      : {contribuyentes:,}")
    print(f"  Receptores          : {receptores:,}")
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
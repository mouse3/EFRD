"""
Punto de entrada del motor EFRD.

Coherencia con el núcleo matemático
-----------------------------------
Las liquidaciones por hogar se recalculan SIEMPRE con la fórmula general del
motor a partir de la renta agregada del hogar:

        T = L · [ r^(1+σ) / (r^σ + u^σ) − u/2 ]        u = k_base · γ · φ
        C = r − T

No se derivan sumando las cuotas individuales: la fórmula es no lineal, de modo
que Σ T(rᵢ) ≠ T(Σ rᵢ). El motor razona por unidad de convivencia, así que la
liquidación debe hacerlo también. La suma de cuotas individuales que dejó
`procesar_simulacion_efrd` se conserva únicamente como control de divergencia.

Escalas: k_base y las rentas de la BD son MENSUALES. --gop debe darse en €/mes.
"""

import argparse
import os
import sqlite3

import matplotlib

MODO_HEADLESS = os.environ.get("EFRD_HEADLESS", "0") == "1"
if MODO_HEADLESS:
    # Debe fijarse ANTES de importar EFRD (que importa pyplot en tiempo de carga)
    matplotlib.use("Agg")

from EFRD import (EFRD_Protocol_v4_1, EFRD_AnalyticVisualizer,
                  TASA_EXCEDENTE_ESTRATEGICO)
from traductores import get_pib_nominal_precios_corrientes, get_IPC_mas_reciente
from simulacion import procesar_simulacion_efrd


PATH_DB = "conexion/outputs/Base_Datos_MACRO.db"
TABLA = "Base_Datos_MACRO"
PATH_LIQUIDACIONES = "conexion/outputs/Liquidaciones_EFRD.db"
DIR_SALIDA = "ejemplos/salida"

# Parámetros de calibración del motor
GINI = 0.33
ALPHA = 0.35
SIGMA = 2
LIMITE_L = 0.47

# Tolerancia relativa al comparar la cuota canónica con la suma de cuotas individuales
TOLERANCIA_DIVERGENCIA = 0.01


def parsear_argumentos():
    parser = argparse.ArgumentParser(description="Motor EFRD v5.0")
    parser.add_argument(
        "--gop", type=float, default=0.0,
        help="Gastos operativos del Estado en EUR/MES (obligatorio para un análisis de solvencia real)."
    )
    parser.add_argument(
        "--modo", type=str, default="interactivo",
        choices=["interactivo", "deuda", "ajuste", "test"],
        help="Modo de resolución de insolvencia: interactivo | deuda | ajuste | test"
    )
    args = parser.parse_args()

    if args.modo == "interactivo" and MODO_HEADLESS:
        print("[AVISO] EFRD_HEADLESS=1 con --modo interactivo: el motor se bloqueará "
              "esperando entrada por consola. Use --modo deuda|ajuste|test.")

    if args.gop == 0.0:
        print("[AVISO] G_op = 0. La inecuación de solvencia no incluye gastos operativos del Estado.")
        print("        Proporcione --gop <valor_EUR_mensual> para un análisis real.")

    return args


def construir_motor(args):
    PIB_anyo, PIB_valor = get_pib_nominal_precios_corrientes()
    IPC_anyo, IPC_valor = get_IPC_mas_reciente()

    print(f"PIB más reciente (año {PIB_anyo}): {PIB_valor} €")
    print(f"IPC más reciente (año {IPC_anyo}): {IPC_valor}")
    print("Iniciando motor EFRD. Procesando base de datos catastral...")

    return EFRD_Protocol_v4_1(
        PIB_Y=PIB_valor,
        Gini=GINI,
        Alpha=ALPHA,
        Sigma=SIGMA,
        Limite_L=LIMITE_L,
        IPC_Pi=IPC_valor,
        G_op=args.gop,
        db_path=PATH_DB,
        tabla_central=TABLA,
        modo=args.modo
    )


def generar_liquidaciones(motor, path_origen: str, path_destino: str) -> int:
    """
    Tabla de liquidaciones por hogar.

    Columnas:
      renta_bruta_hogar  — renta propia del hogar (>= 0)
      umbral_hogar       — u = k_base · γ · φ
      cuota_hogar        — T: a ingresar en Hacienda (+) o a recibir del Estado (−)
      renta_neta_hogar   — C = renta_bruta − cuota, SIEMPRE, para ambos signos
      subsidio_estatal   — max(0, −cuota)
      tipo_efectivo_pct  — cuota / renta_bruta · 100 (NULL si renta_bruta = 0)
      estado_hogar       — CONTRIBUYENTE | RECEPTOR | NEUTRO

    Nota sobre renta_neta_hogar: la versión anterior forzaba `renta_neta = k_hogar`
    para los receptores, es decir, un complemento íntegro hasta el umbral. Eso
    contradecía la cuota que el propio motor calculaba y descuadraba el balance.
    Con la fórmula vigente el neto de un hogar sin renta es L·u/2, no u.
    """
    with sqlite3.connect(path_origen) as conn_src:
        cursor = conn_src.cursor()
        try:
            cursor.execute("""
                SELECT
                    ref_catastral,
                    SUM(renta_total) AS renta_bruta_raw,
                    SUM(cuota)       AS cuota_sumada,
                    MAX(phi_total)   AS phi_total,
                    MAX(gamma)       AS gamma
                FROM resultados_ciudadanos
                WHERE ref_catastral IS NOT NULL AND ref_catastral != ''
                GROUP BY ref_catastral
            """)
            filas_raw = cursor.fetchall()
        except sqlite3.OperationalError as e:
            print(f"[liquidaciones] No se pudo leer 'resultados_ciudadanos': {e}")
            return 0

    if not filas_raw:
        print("[liquidaciones] No hay hogares con referencia catastral válida.")
        return 0

    filas = []
    divergencias = 0

    for ref_catastral, renta_bruta_raw, cuota_sumada, phi_total, gamma in filas_raw:
        renta_bruta_hogar = max(float(renta_bruta_raw or 0.0), 0.0)
        phi_total = float(phi_total or 1.0)
        gamma = float(gamma or 1.0)

        umbral_hogar = motor.k_base * phi_total * gamma

        # Fórmula general, única fuente de verdad
        renta_neta_hogar, cuota_hogar = EFRD_Protocol_v4_1.formula_general(
            renta_bruta_hogar, umbral_hogar, motor.L, motor.sigma
        )

        subsidio_estatal = max(0.0, -cuota_hogar)
        tipo_efectivo_pct = round((cuota_hogar / renta_bruta_hogar) * 100, 4) if renta_bruta_hogar > 0 else None

        if cuota_hogar > 0:
            estado_hogar = "CONTRIBUYENTE"
        elif cuota_hogar < 0:
            estado_hogar = "RECEPTOR"
        else:
            estado_hogar = "NEUTRO"

        # Control: ¿cuánto se aleja la suma de cuotas individuales de la cuota del hogar?
        if cuota_sumada is not None:
            margen = max(1.0, TOLERANCIA_DIVERGENCIA * abs(cuota_hogar))
            if abs(float(cuota_sumada) - cuota_hogar) > margen:
                divergencias += 1

        filas.append((
            ref_catastral,
            renta_bruta_hogar,
            umbral_hogar,
            cuota_hogar,
            renta_neta_hogar,
            subsidio_estatal,
            tipo_efectivo_pct,
            estado_hogar,
            phi_total,
            gamma
        ))

    filas.sort(key=lambda f: f[3], reverse=True)

    os.makedirs(os.path.dirname(path_destino), exist_ok=True)
    with sqlite3.connect(path_destino) as conn_dst:
        conn_dst.execute("DROP TABLE IF EXISTS liquidaciones_hogares")
        conn_dst.execute("""
            CREATE TABLE liquidaciones_hogares (
                ref_catastral      TEXT PRIMARY KEY,
                renta_bruta_hogar  REAL,
                umbral_hogar       REAL,
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
            "INSERT INTO liquidaciones_hogares VALUES (?,?,?,?,?,?,?,?,?,?)", filas
        )

    _informe_liquidaciones(motor, filas, path_destino, divergencias)
    return len(filas)


def _informe_liquidaciones(motor, filas, path_destino, divergencias):
    contribuyentes = sum(1 for f in filas if f[7] == "CONTRIBUYENTE")
    receptores = sum(1 for f in filas if f[7] == "RECEPTOR")
    neutros = sum(1 for f in filas if f[7] == "NEUTRO")
    sin_renta = sum(1 for f in filas if f[1] <= 0)

    total_recaudado = sum(f[3] for f in filas if f[3] > 0)
    total_subsidios = sum(-f[3] for f in filas if f[3] < 0)
    total_subsidio_puro = sum(f[5] for f in filas if f[1] <= 0)

    excedente = total_recaudado * TASA_EXCEDENTE_ESTRATEGICO
    saldo = total_recaudado - total_subsidios - motor.G_op - excedente

    print(f"\n[liquidaciones] {len(filas):,} hogares escritos en '{path_destino}'")
    print(f"  Contribuyentes         : {contribuyentes:,}")
    print(f"  Receptores             : {receptores:,}")
    print(f"  Neutros (r = u)        : {neutros:,}")
    print(f"  Sin renta propia       : {sin_renta:,}")
    print(f"  Recaudación            : {total_recaudado:,.2f} €/mes")
    print(f"  Subsidios totales      : {total_subsidios:,.2f} €/mes")
    print(f"  Subsidio a hogares sin renta: {total_subsidio_puro:,.2f} €/mes")
    print(f"  Excedente estratégico  : {excedente:,.2f} €/mes")
    print(f"  Gasto fijo del Estado  : {motor.G_op:,.2f} €/mes")
    print(f"  SALDO                  : {saldo:,.2f} €/mes")

    # Cuadre contra el balance interno del motor
    saldo_motor, rec_motor, ayu_motor, _ = motor.simular_balance(motor.k_base)
    desfase = saldo - saldo_motor
    print(f"\n  [cuadre] Saldo del motor: {saldo_motor:,.2f} €/mes | desfase: {desfase:,.2f} €")
    if abs(desfase) > max(1.0, 0.001 * abs(saldo_motor)):
        print("  ⚠ El universo de hogares de 'resultados_ciudadanos' no coincide con el")
        print("    que cargó el motor desde la tabla central. Revise filtros y ref_catastral nulas.")

    if divergencias:
        print(f"\n  ⚠ {divergencias:,} hogares donde Σ cuotas individuales ≠ cuota del hogar.")
        print("    Es lo esperable si 'simulacion.py' liquida por ciudadano: la fórmula no es")
        print("    aditiva. Manda la cuota del hogar; ajuste simulacion.py si quiere coherencia.")


def generar_graficas(motor, headless: bool):
    visualizador = EFRD_AnalyticVisualizer(motor)
    graficas = [
        (visualizador.graficar_curva_sostenibilidad, "sostenibilidad.png"),
        (visualizador.graficar_ingreso_bruto_vs_neto, "bruto_vs_neto.png"),
        (visualizador.graficar_tipo_impositivo_efectivo, "tipo_efectivo.png"),
        (visualizador.graficar_mapa_calor_bienestar, "mapa_calor.png"),
        (visualizador.graficar_distribucion_ingresos, "distribucion_ingresos.png"),
    ]
    for funcion, nombre in graficas:
        funcion(guardar=headless, ruta=os.path.join(DIR_SALIDA, nombre))


def main():
    args = parsear_argumentos()
    motor = construir_motor(args)

    if motor.N_total == 0 or not motor.k_base:
        print("\n[ABORTADO] El motor no pudo inicializarse (censo vacío o k_base nulo).")
        return 1

    # Escribe resultados_ciudadanos en la BD principal
    procesar_simulacion_efrd(motor=motor, db_path=PATH_DB, tabla_origen=TABLA)

    generar_liquidaciones(motor, PATH_DB, PATH_LIQUIDACIONES)
    generar_graficas(motor, MODO_HEADLESS)
    return 0


if __name__ == "__main__":
    main()
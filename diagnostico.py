import numpy as np
import pandas as pd
import os
import sqlite3
import json
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime
from math import exp


# ─────────────────────────────────────────────────────────────────────────────
# Carga de parámetros del sistema desde efrd_config.json
# ─────────────────────────────────────────────────────────────────────────────
def _cargar_parametros_sistema(ruta_db: str) -> dict:
    ruta_config = os.path.join(os.path.dirname(ruta_db), "efrd_config.json")
    defaults = {"k_base": 900.0, "sigma": 1.5, "L": 0.80}
    if os.path.exists(ruta_config):
        with open(ruta_config, encoding="utf-8") as f:
            datos = json.load(f)
        print(f"[diagnostico] Parámetros cargados desde: {ruta_config}")
        return {
            "k_base": datos.get("k_base", defaults["k_base"]),
            "sigma":  datos.get("sigma",  defaults["sigma"]),
            "L":      datos.get("L",      defaults["L"]),
        }
    print(f"[diagnostico] AVISO: No se encontró efrd_config.json. Usando valores por defecto: {defaults}")
    return defaults


def _leer_saldos_netos_reales(conn, tabla: str, k_base: float, sigma: float, L: float) -> list:
    """Fórmula EFRD: neto real por ciudadano (no renta*phi)."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT renta_mensual, phi, gamma FROM {tabla} WHERE renta_mensual IS NOT NULL")
    saldos = []
    for renta, phi, gamma in cursor.fetchall():
        if renta is None or phi is None or gamma is None:
            continue
        k_hogar = k_base * phi * gamma
        diferencial = renta - k_hogar
        if diferencial > 0 and k_hogar > 0:
            x    = diferencial / k_hogar
            tasa = L * (1 - exp(-sigma * abs(x)))
            neto = renta - diferencial * tasa
        else:
            neto = k_hogar
        saldos.append(neto)
    return saldos


# ─────────────────────────────────────────────────────────────────────────────
# Helpers estadísticos
# ─────────────────────────────────────────────────────────────────────────────
def _calcular_gini(array: np.ndarray) -> float:
    """Coeficiente de Gini sobre un array de valores positivos."""
    a = np.sort(array[array > 0])
    n = len(a)
    if n == 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return float((2 * np.sum(idx * a) - (n + 1) * np.sum(a)) / (n * np.sum(a)))


def _calcular_alpha_pareto(array: np.ndarray, percentil_cola: int = 90) -> float:
    """Exponente de Pareto estimado por MLE sobre la cola superior."""
    umbral = np.percentile(array, percentil_cola)
    cola   = array[array >= umbral]
    if len(cola) < 2:
        return float("nan")
    return len(cola) / np.sum(np.log(cola / umbral))


def _stats_bloque(array: np.ndarray, percentil_cola: int = 90) -> dict:
    """Calcula el bloque completo de estadísticas para un conjunto de rentas."""
    a = array[array > 0]
    if len(a) == 0:
        return {}
    p20 = np.percentile(a, 20)
    p40 = np.percentile(a, 40)
    p80 = np.percentile(a, 80)
    p_cola = np.percentile(a, percentil_cola)
    masa_b20 = np.sum(a[a <= p20])
    masa_b40 = np.sum(a[a <= p40])
    masa_t20 = np.sum(a[a >= p80])
    masa_cola = np.sum(a[a >= p_cola])
    return {
        "n":            len(a),
        "media":        float(np.mean(a)),
        "mediana":      float(np.median(a)),
        "std":          float(np.std(a)),
        "p25":          float(np.percentile(a, 25)),
        "p75":          float(np.percentile(a, 75)),
        "min":          float(np.min(a)),
        "max":          float(np.max(a)),
        "gini":         _calcular_gini(a),
        "alpha_pareto": _calcular_alpha_pareto(a, percentil_cola),
        "palma":        masa_cola / masa_b40 if masa_b40 > 0 else float("nan"),
        "s80_s20":      masa_t20  / masa_b20 if masa_b20 > 0 else float("nan"),
        "data":         a,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gráfica comparativa ANTES / DESPUÉS (4 paneles)
# ─────────────────────────────────────────────────────────────────────────────
def graficar_diagnostico_comparativo(
        ruta_db: str,
        nombre_db: str,
        percentil_cola: int = 90,
        guardar: bool = True,
        ruta_salida: str = "ejemplos/salida/diagnostico_comparativo.png"):
    """
    Genera una figura de 4 paneles que compara la distribución de salarios
    ANTES (brutos) y DESPUÉS (netos EFRD) del sistema redistributivo:

      Panel 1  — Histogramas superpuestos (bruto vs neto)
      Panel 2  — Boxplots lado a lado
      Panel 3  — Curva de Lorenz (bruto vs neto + línea de igualdad)
      Panel 4  — Cuadro de métricas comparativas (Gini, Pareto α, Palma, S80/S20)
    """
    if not os.path.exists(ruta_db):
        print(f"[diagnostico] Error: BD no encontrada en '{ruta_db}'")
        return

    # ── Lectura de datos ──────────────────────────────────────────────────────
    try:
        params = _cargar_parametros_sistema(ruta_db)
        with sqlite3.connect(ruta_db) as conn:
            # ANTES: rentas brutas mensuales individuales
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT renta_mensual FROM {nombre_db} WHERE renta_mensual IS NOT NULL AND renta_mensual > 0"
            )
            brutos = np.array([float(r[0]) for r in cursor.fetchall()])

            # DESPUÉS: netos calculados con la fórmula EFRD
            netos_lista = _leer_saldos_netos_reales(
                conn, nombre_db,
                k_base=params["k_base"],
                sigma=params["sigma"],
                L=params["L"]
            )
            netos = np.array([v for v in netos_lista if v > 0])
    except Exception as e:
        print(f"[diagnostico] Error crítico al leer BD: {e}")
        return

    if brutos.size < 10 or netos.size < 10:
        print("[diagnostico] Datos insuficientes para el diagnóstico comparativo.")
        return

    sb = _stats_bloque(brutos, percentil_cola)
    sn = _stats_bloque(netos,  percentil_cola)

    # ── Figura ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 14))
    fig.suptitle(
        f"Diagnóstico Distributivo EFRD — Antes (Bruto) vs Después (Neto)\n"
        f"Tabla: {nombre_db}  |  N={sb['n']:,}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        fontsize=14, fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)

    COLOR_BRUTO = "#E07B39"   # naranja — bruto
    COLOR_NETO  = "#2E86AB"   # azul    — neto
    ALPHA       = 0.55

    # ── Panel 1: Histogramas superpuestos ─────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])

    # Rango común para comparación justa
    x_min = min(brutos.min(), netos.min())
    x_max = np.percentile(np.concatenate([brutos, netos]), 99)  # cortar outliers extremos
    bins_comunes = np.linspace(x_min, x_max, 60)

    ax1.hist(brutos, bins=bins_comunes, color=COLOR_BRUTO, alpha=ALPHA,
             label=f"Bruto  (media {sb['media']:,.0f}€)", edgecolor="none")
    ax1.hist(netos,  bins=bins_comunes, color=COLOR_NETO,  alpha=ALPHA,
             label=f"Neto   (media {sn['media']:,.0f}€)", edgecolor="none")

    ax1.axvline(sb["media"],   color=COLOR_BRUTO, linestyle="--", lw=1.8)
    ax1.axvline(sn["media"],   color=COLOR_NETO,  linestyle="--", lw=1.8)
    ax1.axvline(sb["mediana"], color=COLOR_BRUTO, linestyle=":",  lw=1.4)
    ax1.axvline(sn["mediana"], color=COLOR_NETO,  linestyle=":",  lw=1.4)

    ax1.set_title("Histograma Comparativo (-- media  ··· mediana)", fontsize=10, fontweight="bold")
    ax1.set_xlabel("Renta mensual (€)")
    ax1.set_ylabel("Frecuencia")
    ax1.legend(fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.3)
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # ── Panel 2: Boxplots lado a lado ─────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])

    bp = ax2.boxplot(
        [brutos, netos],
        vert=False,
        patch_artist=True,
        labels=["Bruto", "Neto"],
        widths=0.5,
        boxprops=dict(linewidth=1.2),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
        medianprops=dict(linewidth=2.2, color="white"),
        flierprops=dict(marker="o", markersize=3, linestyle="none", alpha=0.3)
    )
    bp["boxes"][0].set_facecolor(COLOR_BRUTO); bp["boxes"][0].set_alpha(0.7)
    bp["boxes"][1].set_facecolor(COLOR_NETO);  bp["boxes"][1].set_alpha(0.7)
    for flier in bp["fliers"]:
        flier.set(markerfacecolor="gray", alpha=0.2)

    ax2.set_title("Boxplot Comparativo", fontsize=10, fontweight="bold")
    ax2.set_xlabel("Renta mensual (€)")
    ax2.grid(True, linestyle="--", alpha=0.3)
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # ── Panel 3: Curva de Lorenz ──────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])

    def _lorenz(arr):
        s = np.sort(arr)
        cumsum = np.cumsum(s)
        cumsum = cumsum / cumsum[-1]
        x = np.linspace(0, 1, len(s))
        return x, cumsum

    lx_b, ly_b = _lorenz(brutos)
    lx_n, ly_n = _lorenz(netos)

    ax3.plot([0, 1], [0, 1], color="black", linestyle="--", lw=1.2, label="Igualdad perfecta")
    ax3.plot(lx_b, ly_b, color=COLOR_BRUTO, lw=2,   label=f"Bruto  (Gini={sb['gini']:.3f})")
    ax3.plot(lx_n, ly_n, color=COLOR_NETO,  lw=2,   label=f"Neto   (Gini={sn['gini']:.3f})")
    ax3.fill_between(lx_b, ly_b, lx_b, color=COLOR_BRUTO, alpha=0.08)
    ax3.fill_between(lx_n, ly_n, lx_n, color=COLOR_NETO,  alpha=0.08)

    ax3.set_title("Curva de Lorenz", fontsize=10, fontweight="bold")
    ax3.set_xlabel("Fracción acumulada de población")
    ax3.set_ylabel("Fracción acumulada de renta")
    ax3.legend(fontsize=9)
    ax3.grid(True, linestyle="--", alpha=0.3)

    # ── Panel 4: Tabla de métricas ────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis("off")

    def _fmt(v, decimales=3):
        if isinstance(v, float) and np.isnan(v):
            return "N/D"
        if decimales == 0:
            return f"{v:,.0f}"
        return f"{v:,.{decimales}f}"

    reduccion_gini   = (sb["gini"]  - sn["gini"])  / sb["gini"]  * 100 if sb["gini"]  > 0 else 0
    reduccion_palma  = (sb["palma"] - sn["palma"])  / sb["palma"] * 100 if (not np.isnan(sb["palma"]) and sb["palma"] > 0) else 0
    cambio_media_pct = (sn["media"] - sb["media"])  / sb["media"] * 100 if sb["media"] > 0 else 0

    metricas = [
        ("",                    "BRUTO",                 "NETO",                  "VARIACIÓN"),
        ("─" * 14,              "─" * 14,                "─" * 14,                "─" * 14),
        ("N (personas)",        _fmt(sb["n"], 0),        _fmt(sn["n"], 0),        "—"),
        ("Media (€/mes)",       _fmt(sb["media"], 0),    _fmt(sn["media"], 0),    f"{cambio_media_pct:+.1f}%"),
        ("Mediana (€/mes)",     _fmt(sb["mediana"], 0),  _fmt(sn["mediana"], 0),  ""),
        ("Desv. Std. (€)",      _fmt(sb["std"], 0),      _fmt(sn["std"], 0),      ""),
        ("P25 (€/mes)",         _fmt(sb["p25"], 0),      _fmt(sn["p25"], 0),      ""),
        ("P75 (€/mes)",         _fmt(sb["p75"], 0),      _fmt(sn["p75"], 0),      ""),
        ("─" * 14,              "─" * 14,                "─" * 14,                "─" * 14),
        ("Gini",                _fmt(sb["gini"]),        _fmt(sn["gini"]),        f"{reduccion_gini:+.1f}%"),
        ("Alpha Pareto",        _fmt(sb["alpha_pareto"]),_fmt(sn["alpha_pareto"]),""),
        ("Palma Ratio",         _fmt(sb["palma"]),       _fmt(sn["palma"]),       f"{reduccion_palma:+.1f}%"),
        ("S80/S20",             _fmt(sb["s80_s20"]),     _fmt(sn["s80_s20"]),     ""),
    ]

    col_x = [0.01, 0.30, 0.55, 0.78]
    for fila_i, fila in enumerate(metricas):
        y_pos = 0.97 - fila_i * 0.073
        for col_j, celda in enumerate(fila):
            peso = "bold" if fila_i in (0, 1) else "normal"
            color_texto = "black"
            if fila_i > 1 and col_j == 3 and celda.startswith("-"):
                color_texto = "#2E86AB"   # reducción positiva → azul
            elif fila_i > 1 and col_j == 3 and celda.startswith("+"):
                color_texto = "#C0392B"   # aumento → rojo
            ax4.text(col_x[col_j], y_pos, celda,
                     transform=ax4.transAxes, fontsize=9,
                     fontweight=peso, color=color_texto,
                     verticalalignment="top", fontfamily="monospace")

    ax4.set_title("Métricas Comparativas", fontsize=10, fontweight="bold")
    rect = plt.Rectangle((0, 0), 1, 1, fill=True, color="#F8F9FA",
                          transform=ax4.transAxes, zorder=0)
    ax4.add_patch(rect)

    # ── Guardar / mostrar ─────────────────────────────────────────────────────
    if guardar:
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        plt.savefig(ruta_salida, format="png", bbox_inches="tight", dpi=150)
        print(f"[diagnostico] Gráfica comparativa guardada en: '{ruta_salida}'")
    else:
        plt.show()
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Histograma + Boxplot de saldos netos (función original, conservada)
# ─────────────────────────────────────────────────────────────────────────────
def graficar_distribucion_saldos(ruta_db, nombre_db,
                                  guardar: bool = True,
                                  ruta_salida: str = "ejemplos/salida/distribucion_saldos_histograma.png"):
    if not os.path.exists(ruta_db):
        print(f"Error: No se encontró la base de datos en la ruta: '{ruta_db}'")
        return
    try:
        params = _cargar_parametros_sistema(ruta_db)
        conn = sqlite3.connect(ruta_db)
        saldos_lista = _leer_saldos_netos_reales(
            conn, nombre_db,
            k_base=params["k_base"], sigma=params["sigma"], L=params["L"]
        )
        conn.close()
    except Exception as e:
        print(f"Error crítico al leer la base de datos: {e}")
        return

    if not saldos_lista:
        print("Error: No se obtuvieron saldos de la base de datos.")
        return

    saldos = np.array(saldos_lista)
    saldos_positivos = saldos[saldos > 0]

    if len(saldos_positivos) < 5:
        print("Error: Se necesitan al menos 5 registros con saldos > 0 para graficar la distribución.")
        return

    media   = np.mean(saldos_positivos)
    mediana = np.median(saldos_positivos)

    fig, (ax_hist, ax_box) = plt.subplots(1, 2, figsize=(15, 6))

    ax_hist.hist(saldos_positivos, bins=20, color='#2CA02C', edgecolor='black', alpha=0.7, label='Saldos')
    ax_hist.axvline(media,   color='#D62728', linestyle='--', linewidth=2, label=f'Media: {media:,.2f}')
    ax_hist.axvline(mediana, color='#1F77B4', linestyle='-',  linewidth=2, label=f'Mediana: {mediana:,.2f}')
    ax_hist.set_title('Histograma de Frecuencias (Saldos > 0)', fontsize=11, fontweight='bold')
    ax_hist.set_xlabel('Saldo Neto (€)')
    ax_hist.set_ylabel('Frecuencia Absoluta (Personas)')
    ax_hist.grid(True, linestyle='--', alpha=0.3)
    ax_hist.legend(loc='upper right')
    ax_hist.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    ax_box.boxplot(saldos_positivos, vert=False, patch_artist=True,
                   boxprops=dict(facecolor='#1F77B4', color='black', alpha=0.6),
                   whiskerprops=dict(color='black', linewidth=1.5),
                   capprops=dict(color='black', linewidth=1.5),
                   medianprops=dict(color='#D62728', linewidth=2.5),
                   flierprops=dict(marker='o', markerfacecolor='black',
                                   markersize=5, linestyle='none', alpha=0.5))
    ax_box.set_title('Diagrama de Caja (Boxplot) y Dispersión', fontsize=11, fontweight='bold')
    ax_box.set_xlabel('Saldo Neto (€)')
    ax_box.set_yticks([])
    ax_box.grid(True, linestyle='--', alpha=0.3)
    ax_box.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    plt.suptitle(f'Análisis de Distribución de Saldos — Tabla: {nombre_db}',
                 fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()

    if guardar:
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        plt.savefig(ruta_salida, format='png', bbox_inches='tight', dpi=150)
        print(f"Gráfica de distribución guardada en: '{ruta_salida}'")
    else:
        plt.show()
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Análisis Pareto semilogarítmico (función original, conservada)
# ─────────────────────────────────────────────────────────────────────────────
def calcular_analizar_y_graficar_pareto_semilog(ruta_db, nombre_db, percentil_cola=90,
                                                 guardar: bool = True,
                                                 ruta_salida: str = "ejemplos/salida/grafica_diagnostico_macro_semilog.png"):
    if not os.path.exists(ruta_db):
        print(f"Error: No se encontró la base de datos en la ruta: '{ruta_db}'")
        return None
    try:
        params = _cargar_parametros_sistema(ruta_db)
        conn = sqlite3.connect(ruta_db)
        saldos_lista = _leer_saldos_netos_reales(
            conn, nombre_db,
            k_base=params["k_base"], sigma=params["sigma"], L=params["L"]
        )
        conn.close()
    except Exception as e:
        print(f"Error crítico al leer la base de datos: {e}")
        return None

    if not saldos_lista:
        print("Error: No se obtuvieron saldos de la base de datos.")
        return None

    ingresos = np.array(saldos_lista)
    ingresos = ingresos[ingresos > 0]

    if len(ingresos) < 10:
        print("Error: Se necesitan al menos 10 registros con saldos > 0.")
        return None

    ingresos = np.sort(ingresos)
    N_total  = len(ingresos)

    p20_corte  = np.percentile(ingresos, 20)
    p40_corte  = np.percentile(ingresos, 40)
    p80_corte  = np.percentile(ingresos, 80)
    p_cola     = np.percentile(ingresos, percentil_cola)
    top_pct    = 100 - percentil_cola

    masa_b20   = np.sum(ingresos[ingresos <= p20_corte])
    masa_b40   = np.sum(ingresos[ingresos <= p40_corte])
    masa_t20   = np.sum(ingresos[ingresos >= p80_corte])
    masa_cola  = np.sum(ingresos[ingresos >= p_cola])

    palma      = masa_cola / masa_b40 if masa_b40 > 0 else np.nan
    s80_s20    = masa_t20  / masa_b20 if masa_b20 > 0 else np.nan

    cola_ing   = ingresos[ingresos >= p_cola]
    n_cola     = len(cola_ing)
    alpha      = n_cola / np.sum(np.log(cola_ing / p_cola))

    if alpha > 2.2:
        rango, comp, din, cons, riesgo = ("alpha > 2.2", "Caída hiper-rápida. Sin outliers. Clase media hipertrofiada.", "g >> r (El crecimiento supera al retorno de inversión).", "Cooperativo, basado en bienes y servicios del Estado.", "Casi nulo. Riesgo en estancamiento de productividad.")
    elif 1.5 <= alpha <= 2.2:
        rango, comp, din, cons, riesgo = ("1.5 <= alpha <= 2.2", "Relación equilibrada. Distribución saludable de ingresos altos.", "r ≈ g (Equilibrio macroeconómico capital/trabajo).", "Consumo masivo robusto, impulsado por clase media fuerte.", "Bajo. Resiliencia financiera ante burbujas.")
    elif 1.2 <= alpha < 1.5:
        rango, comp, din, cons, riesgo = ("1.2 <= alpha < 1.5", "Cola pesada transicional. Alta concentración en la cúspide.", "r > g (Acumulación financiera supera a economía real).", "Segmentado. Demanda de bienes de lujo y especulación.", "Moderado-Alto. Tensiones fiscales y paros estructurales.")
    else:
        rango, comp, din, cons, riesgo = ("alpha < 1.2", "Ley de potencias extrema. Dominio de mega-ricos (outliers).", "r >> g (Riqueza financiera domina por completo).", "Dual. Subsistencia en la base, evasión en la cima.", "Crítico. Polarización, corrupción y fragilidad soberana.")

    diag_palma = "Brecha extrema (Oligarquía)" if palma > 3.0 else ("Equilibrio saludable" if palma <= 1.2 else "Desigualdad intermedia")

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas_informe = [
        "=" * 70,
        " INFORME EJECUTIVO INTERNIVEL: ANÁLISIS MACROECONÓMICO AVANZADO",
        "=" * 70,
        f" Fecha del Análisis      : {fecha_actual}",
        f" Base de Datos de Origen : {os.path.basename(ruta_db)}",
        f" Registros Procesados    : {N_total:,}",
        "-" * 70,
        " SECCIÓN 1: DISTRIBUCIÓN DE COLA (PARETO)",
        "-" * 70,
        f" Umbral xmin (Top {top_pct}%)    : {p_cola:,.2f}",
        f" Muestra en Cola (n)      : {n_cola:,}",
        f" FACTOR ALPHA CALCULADO   : {alpha:.4f}",
        f" Rango Asignado           : {rango}",
        f" Comportamiento Matemático: {comp}",
        f" Dinámica de Capital      : {din}",
        f" Modelo de Consumo        : {cons}",
        f" Riesgo de Colapso        : {riesgo}",
        "-" * 70,
        " SECCIÓN 2: BRECHAS ESTRUCTURALES Y DESIGUALDAD RELATIVA",
        "-" * 70,
        f" PALMA RATIO (Top {top_pct}%/Bot 40%): {palma:.4f} ({diag_palma})",
        f" RATIO S80/S20 (Quintiles)    : {s80_s20:.4f}",
        "=" * 70
    ]
    texto_final = "\n".join(lineas_informe)
    print("\n" + texto_final + "\n")

    ruta_txt = "ejemplos/salida/ingresos_informe_pareto.txt"
    os.makedirs(os.path.dirname(ruta_txt), exist_ok=True)
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(texto_final)

    x_grafica = ingresos
    y_grafica = N_total - np.arange(N_total)

    plt.figure(figsize=(10, 6))
    plt.semilogx(x_grafica, y_grafica, color='#1F77B4', linewidth=2.5, label='Curva Real de Población')
    plt.axvline(x=p_cola,    color='#D62728', linestyle='--', alpha=0.8, label=f'Umbral xmin (Top {top_pct}%): {p_cola:,.0f}')
    plt.axvline(x=p40_corte, color='#2CA02C', linestyle=':', alpha=0.7, label=f'Corte Base Palma (P40): {p40_corte:,.0f}')
    plt.text(p_cola * 1.15,    N_total * 0.20, f'Cola de Pareto\n(Alpha = {alpha:.2f})', color='#D62728', fontweight='bold', fontsize=9)
    plt.text(p40_corte / 1.4,  N_total * 0.70, 'Sustento\nBase 40%', color='#2CA02C', fontsize=9, ha='right')

    info_box = (f"Indicadores Estructurales:\n"
                f"• Palma Ratio: {palma:.2f}\n"
                f"• Ratio S80/S20: {s80_s20:.2f}\n"
                f"• Riesgo Económico: {riesgo.split('.')[0]}")
    plt.gca().text(0.95, 0.95, info_box, transform=plt.gca().transAxes, fontsize=10,
                   verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', alpha=0.9, edgecolor='#DEE2E6'))

    plt.gca().get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.title('Análisis Macroeconómico del Saldo Neto (Eje X Log / Eje Y Lineal)', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('Saldos Netos por Persona (Escala Logarítmica)', fontsize=10)
    plt.ylabel('Cantidad Acumulada de Personas (Escala Lineal)', fontsize=10)
    plt.grid(True, which="both", linestyle='--', alpha=0.3)
    plt.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='#DEE2E6')

    if guardar:
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
        plt.savefig(ruta_salida, format='png', bbox_inches='tight', dpi=150)
        print(f"Gráfica semilogarítmica guardada en: '{ruta_salida}'\n")
    else:
        plt.show()
    plt.close()

    return alpha


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Diagnóstico macroeconómico EFRD")
    parser.add_argument("--db",    default=os.path.join(BASE_DIR, "conexion", "outputs", "Base_Datos_MACRO.db"))
    parser.add_argument("--tabla", default="Base_Datos_MACRO")
    parser.add_argument("--percentil-cola", type=int, default=90,
        help="Percentil para la cola de Pareto (por defecto 90 → Top 10%%)")
    parser.add_argument("--headless", action="store_true",
        help="Guardar gráficas en disco en lugar de mostrarlas")
    args = parser.parse_args()

    # Diagnóstico comparativo ANTES / DESPUÉS  ← nuevo
    graficar_diagnostico_comparativo(
        ruta_db=args.db,
        nombre_db=args.tabla,
        percentil_cola=args.percentil_cola,
        guardar=args.headless
    )

    # Análisis clásicos (conservados)
    calcular_analizar_y_graficar_pareto_semilog(
        ruta_db=args.db,
        nombre_db=args.tabla,
        percentil_cola=args.percentil_cola,
        guardar=args.headless
    )
    graficar_distribucion_saldos(
        ruta_db=args.db,
        nombre_db=args.tabla,
        guardar=args.headless
    )
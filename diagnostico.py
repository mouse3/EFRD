import numpy as np
import pandas as pd
import os
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

def graficar_distribucion_saldos(ruta_db, nombre_db):
    """
    Extrae los saldos netos de la BD y genera una gráfica doble de distribución:
    un Histograma de frecuencias y un Diagrama de Caja (Boxplot).
    """
    # 1. Validar existencia de la Base de Datos
    if not os.path.exists(ruta_db):
        print(f" Error: No se encontró la base de datos en la ruta: '{ruta_db}'")
        return
        
    try:
        # 2. Conectar a la BD y leer datos
        conn = sqlite3.connect(ruta_db)
        query = f"SELECT (renta_mensual * phi) AS saldo_neto FROM {nombre_db}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            print(" Error: La tabla de la base de datos está vacía o no existe.")
            return
            
        saldos = df['saldo_neto'].dropna().to_numpy()
        saldos_positivos = saldos[saldos > 0]
        
    except Exception as e:
        print(f" Error crítico al leer la base de datos: {e}")
        return

    if len(saldos_positivos) < 5:
        print(" Error: Se necesitan al menos 5 registros con saldos mayores a 0 para graficar la distribución.")
        return

    # Calcular métricas básicas para la gráfica
    media = np.mean(saldos_positivos)
    mediana = np.median(saldos_positivos)

    # 3. Configurar la figura con 2 subplots en paralelo (1 fila, 2 columnas)
    fig, (ax_hist, ax_box) = plt.subplots(1, 2, figsize=(15, 6))
    
    # --- SUBPLOT 1: HISTOGRAMA DE FRECUENCIAS ---
    ax_hist.hist(saldos_positivos, bins=20, color='#2CA02C', edgecolor='black', alpha=0.7, label='Saldos')
    ax_hist.axvline(media, color='#D62728', linestyle='--', linewidth=2, label=f'Media: {media:,.2f}')
    ax_hist.axvline(mediana, color='#1F77B4', linestyle='-', linewidth=2, label=f'Mediana: {mediana:,.2f}')
    
    ax_hist.set_title('Histograma de Frecuencias (Saldos > 0)', fontsize=11, fontweight='bold')
    ax_hist.set_xlabel('Saldo Neto (€)')
    ax_hist.set_ylabel('Frecuencia Absoluta (Personas)')
    ax_hist.grid(True, linestyle='--', alpha=0.3)
    ax_hist.legend(loc='upper right')
    ax_hist.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    # --- SUBPLOT 2: DIAGRAMA DE CAJA (BOXPLOT) ---
    ax_box.boxplot(saldos_positivos, vert=False, patch_artist=True,
                   boxprops=dict(facecolor='#1F77B4', color='black', alpha=0.6),
                   whiskerprops=dict(color='black', linewidth=1.5),
                   capprops=dict(color='black', linewidth=1.5),
                   medianprops=dict(color='#D62728', linewidth=2.5),
                   flierprops=dict(marker='o', markerfacecolor='black', markersize=5, linestyle='none', alpha=0.5))
    
    ax_box.set_title('Diagrama de Caja (Boxplot) y Dispersión', fontsize=11, fontweight='bold')
    ax_box.set_xlabel('Saldo Neto (€)')
    ax_box.set_yticks([])  # Ocultar el eje Y ya que es un boxplot horizontal de una sola variable
    ax_box.grid(True, linestyle='--', alpha=0.3)
    ax_box.get_xaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    # Título global y ajustes de guardado
    plt.suptitle(f'Análisis de Distribución de Saldos - Tabla: {nombre_db}', fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    ruta_grafica_dist = "ejemplos/salida/distribucion_saldos_histograma.png"
    os.makedirs(os.path.dirname(ruta_grafica_dist), exist_ok=True)
    plt.savefig(ruta_grafica_dist, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    print(f" Gráfica de distribución (Histograma/Boxplot) guardada en: '{ruta_grafica_dist}'")


def calcular_analizar_y_graficar_pareto_semilog(ruta_db, nombre_db, percentil_cola=90):
    """
    Procesa los saldos netos desde la BD SQLite, calcula alpha, Palma, S80/S20, 
    genera un informe .txt y guarda una gráfica con eje X logarítmico y eje Y lineal.
    """
    if not os.path.exists(ruta_db):
        print(f" Error: No se encontró la base de datos en la ruta: '{ruta_db}'")
        return None
        
    try:
        conn = sqlite3.connect(ruta_db)
        query = f"""
            SELECT (renta_mensual * phi) AS saldo_neto 
            FROM {nombre_db}
            """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            print(" Error: La tabla de la base de datos está vacía o no existe.")
            return None
            
        nombre_columna = "saldo_neto"
        ingresos = df[nombre_columna].dropna().to_numpy()
        ingresos = ingresos[ingresos > 0]
        
    except Exception as e:
        print(f" Error crítico al leer la base de datos: {e}")
        return None

    if len(ingresos) < 10:
        print(" Error: Se necesitan al menos 10 registros con ingresos mayores a 0.")
        return None

    ingresos = np.sort(ingresos)
    N_total = len(ingresos)

    # CÁLCULOS MACROECONÓMICOS
    p20_corte = np.percentile(ingresos, 20)
    p40_corte = np.percentile(ingresos, 40)
    p80_corte = np.percentile(ingresos, 80)
    p90_corte = np.percentile(ingresos, 90)
    
    masa_bottom_20 = np.sum(ingresos[ingresos <= p20_corte])
    masa_bottom_40 = np.sum(ingresos[ingresos <= p40_corte])
    masa_top_20 = np.sum(ingresos[ingresos >= p80_corte])
    masa_top_10 = np.sum(ingresos[ingresos >= p90_corte])
    
    palma_ratio = masa_top_10 / masa_bottom_40 if masa_bottom_40 > 0 else np.nan
    s80_s20_ratio = masa_top_20 / masa_bottom_20 if masa_bottom_20 > 0 else np.nan

    # Cálculo de Pareto
    umbral_xmin = p90_corte
    cola_ingresos = ingresos[ingresos >= umbral_xmin]
    n_cola = len(cola_ingresos)
    alpha = n_cola / np.sum(np.log(cola_ingresos / umbral_xmin))
    
    if alpha > 2.2:
        rango, comp, din, cons, riesgo = ("alpha > 2.2", "Caída hiper-rápida. Sin outliers. Clase media hipertrofiada.", "g >> r (El crecimiento supera al retorno de inversión).", "Cooperativo, basado en bienes y servicios del Estado.", "Casi nulo. Riesgo en estancamiento de productividad.")
    elif 1.5 <= alpha <= 2.2:
        rango, comp, din, cons, riesgo = ("1.5 <= alpha <= 2.2", "Relación equilibrada. Distribución saludable de ingresos altos.", "r ≈ g (Equilibrio macroeconómico capital/trabajo).", "Consumo masivo robusto, impulsado por clase media fuerte.", "Bajo. Resiliencia financiera ante burbujas.")
    elif 1.2 <= alpha < 1.5:
        rango, comp, din, cons, riesgo = ("1.2 <= alpha < 1.5", "Cola pesada transicional. Alta concentración en la cúspide.", "r > g (Acumulación financiera supera a economía real).", "Segmentado. Demanda de bienes de lujo y especulación.", "Moderado-Alto. Tensiones fiscales y paros estructurales.")
    else:
        rango, comp, din, cons, riesgo = ("alpha < 1.2", "Ley de potencias extrema. Dominio de mega-ricos (outliers).", "r >> g (Riqueza financiera domina por completo).", "Dual. Subsistencia en la base, evasión en la cima.", "Crítico. Polarización, corrupción y fragilidad soberana.")

    diag_palma = "Brecha extrema (Oligarquía)" if palma_ratio > 3.0 else ("Equilibrio saludable" if palma_ratio <= 1.2 else "Desigualdad intermedia")

    # Generación de informe textual
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas_informe = [
        "=" * 70,
        " INFORME EJECUTIVO INTERNIVEL: ANÁLISIS MACROECONÓMICO AVANZADO",
        "=" * 70,
        f" Fecha del Análisis      : {fecha_actual}",
        f" Base de Datos de Origen : {os.path.basename(ruta_db)}",
        f" Registros Procesados    : {N_total:,}",
        "-"* 70,
        " SECCIÓN 1: DISTRIBUCIÓN DE COLA (PARETO)",
        "-" * 70,
        f" Umbral xmin (Top 10%)    : {umbral_xmin:,.2f}",
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
        f" PALMA RATIO (Top 10%/Bot 40%): {palma_ratio:.4f} ({diag_palma})",
        f" RATIO S80/S20 (Quintiles)    : {s80_s20_ratio:.4f}",
        "=" * 70
    ]
    texto_final = "\n".join(lineas_informe)
    print("\n" + texto_final + "\n")

    ruta_txt = "ejemplos/salida/ingresos_informe_pareto.txt"
    os.makedirs(os.path.dirname(ruta_txt), exist_ok=True)
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(texto_final)

    # Gráfica semi-logarítmica
    x_grafica = ingresos
    y_grafica = N_total - np.arange(N_total) 

    plt.figure(figsize=(10, 6))
    plt.semilogx(x_grafica, y_grafica, color='#1F77B4', linewidth=2.5, label='Curva Real de Población')
    plt.axvline(x=umbral_xmin, color='#D62728', linestyle='--', alpha=0.8, label=f'Umbral xmin (Top 10%): {umbral_xmin:,.0f}')
    plt.axvline(x=p40_corte, color='#2CA02C', linestyle=':', alpha=0.7, label=f'Corte Base Palma (P40): {p40_corte:,.0f}')

    plt.text(umbral_xmin * 1.15, N_total * 0.20, f'Cola de Pareto\n(Alpha = {alpha:.2f})', color='#D62728', fontweight='bold', fontsize=9)
    plt.text(p40_corte / 1.4, N_total * 0.70, 'Sustento\nBase 40%', color='#2CA02C', fontsize=9, ha='right')

    info_box = (f"Indicadores Estructurales:\n"
                f"• Palma Ratio: {palma_ratio:.2f}\n"
                f"• Ratio S80/S20: {s80_s20_ratio:.2f}\n"
                f"• Riesgo Económico: {riesgo.split('.')[0]}")
    plt.gca().text(0.95, 0.95, info_box, transform=plt.gca().transAxes, fontsize=10,
                   verticalalignment='top', horizontalalignment='right', 
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA', alpha=0.9, edgecolor='#DEE2E6'))

    plt.gca().get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    plt.title('Análisis Macroeconómico del Saldo Neto (Eje X Logarítmico / Eje Y Lineal)', fontsize=12, fontweight='bold', pad=15)
    plt.xlabel('Saldos Netos por Persona (Escala Logarítmica)', fontsize=10)
    plt.ylabel('Cantidad Acumulada de Personas (Escala Lineal)', fontsize=10)
    plt.grid(True, which="both", linestyle='--', alpha=0.3)
    plt.legend(loc='lower left', frameon=True, facecolor='white', edgecolor='#DEE2E6')

    ruta_grafica = "ejemplos/salida/grafica_diagnostico_macro_semilog.png"
    plt.savefig(ruta_grafica, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Gráfica de diagnóstico semi-logarítmica guardada en: '{ruta_grafica}'\n")

    return alpha


# --- MODO DE USO ---
if __name__ == "__main__":
    RUTA = "C:/Users/dragu/Desktop/clonesGithub/EFRD/conexion/outputs/Base_Datos_MACRO.db"
    TABLA = "Base_Datos_MACRO"
    
    # 1. Ejecutar análisis macroeconómico previo (Pareto/Semilog)
    calcular_analizar_y_graficar_pareto_semilog(ruta_db=RUTA, nombre_db=TABLA)
    
    # 2. Ejecutar la nueva gráfica analítica de distribución clásica
    graficar_distribucion_saldos(ruta_db=RUTA, nombre_db=TABLA)
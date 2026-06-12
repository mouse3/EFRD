from math import exp, ceil
import matplotlib.pyplot as plt
from numpy import zeros, linspace
from copy import deepcopy
from traductores import get_renta_mediana
from sqlite3 import connect
from os import path

class EFRD_Protocol_v3_2:
    def __init__(self, PIB_Y, Gini, Alpha, Sigma, Limite_L, G_op, IPC_Pi, db_path, tabla_central):
        # Parámetros de configuración
        self.Y = PIB_Y
        self.G = Gini   
        self.alpha = Alpha  
        self.sigma = Sigma 
        self.L = Limite_L 
        self.G_op = G_op 
        self.pi = IPC_Pi
        self.renta_mediana_nacional = get_renta_mediana()
        self.db_path = db_path
        self.tabla_central = tabla_central
        
        # Inicialización de contadores
        self.unidades_convivencia = []
        self.N_total = 0 
        
        # EXTRACCIÓN DE DATOS (Adaptada al nuevo formato largo explotado)
        self._cargar_datos_desde_db()

        if self.N_total == 0:
            print(" ERROR: No se han encontrado ciudadanos en la base de datos.")
            self.k_base = 0
            return

        # CÁLCULO DE MACROMAGNITUDES
        self.k_base = self.alpha * (self.Y / self.N_total) * (1 - self.G) * self.pi
        self.k_arope = 0.6 * self.renta_mediana_nacional

        print(f" PROTOCOLO EFRD: CARGANDO SIST.")
        print(f" Ciudadanos censados (N_total): {self.N_total}")
        print(f" Hogares procesados: {len(self.unidades_convivencia)}")
        print(f" Suelo Vitalicio (k_base): {self.k_base:.2f} €")
        print(f" Umbral Pobreza (AROPE): {self.k_arope:.2f} €")
        print("-" * 40)

        # EJECUCIÓN DE PROTOCOLOS DE SOLVENCIA Y DIGNIDAD
        self._ejecutar_logica_central()

    def _cargar_datos_desde_db(self):
        """
        Recorre la DB explotada agrupando dinámicamente por vivienda directamente en SQL.
        Eficiencia O(N) nativa de base de datos.
        """
        if not path.exists(self.db_path):
            print(f"Archivo no encontrado: {self.db_path}")
            return

        with connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Aprovechamos el formato largo para agrupar ingresos y phis por hogar en la propia query
            query_agrupada = f"""
                SELECT 
                    SUM(renta_mensual) AS renta_total,
                    SUM(phi) AS phi_total,
                    MAX(gamma) AS gamma,
                    COUNT(dni_nie_nif) AS num_inquilinos
                FROM {self.tabla_central}
                GROUP BY ref_catastral
            """
            cursor.execute(query_agrupada)
            
            for renta_total, phi_total, gamma, num_inquilinos in cursor.fetchall():
                # Actualizamos el censo nacional total
                self.N_total += num_inquilinos
                
                # Agregamos la estructura consolidada del hogar para simulaciones
                self.unidades_convivencia.append({
                    'renta_total': renta_total,
                    'phi_total': phi_total,
                    'gamma': gamma
                })

    def calcular_cuota_hogar(self, renta, num_adultos_extra=0, num_hijos=0, gamma=1.0):
        """Método de soporte para compatibilidad con EFRD_AdvancedVisualizer."""
        # Reconstrucción del factor compuesto phi según la convención del visualizador
        phi_total = 1.0 + (num_adultos_extra * 0.5) + (num_hijos * 0.3)
        umbral_hogar = self.k_base * gamma * phi_total
        diferencial = renta - umbral_hogar
        
        if diferencial > 0:
            x = diferencial / (renta * 0.1) if umbral_hogar <= 0 else diferencial / umbral_hogar
            tasa = self.L * (1 - exp(-self.sigma * abs(x)))
            impuesto = diferencial * tasa
            neto = renta - impuesto
            tipo_efectivo = (impuesto / renta) * 100 if renta > 0 else 0
        else:
            subsidio = abs(diferencial)
            impuesto = -subsidio
            neto = renta + subsidio
            tipo_efectivo = -(subsidio / renta) * 100 if renta > 0 else -100
            
        return {"C_cuota": max(0, impuesto), "Tipo_Efectivo": tipo_efectivo, "Neto": neto}

    def simular_balance(self, k_prueba):
        total_recaudado = 0
        total_ayudas = 0
        
        for hogar in self.unidades_convivencia:
            umbral_hogar = k_prueba * hogar['gamma'] * hogar['phi_total']
            renta = hogar['renta_total']
            diferencial = renta - umbral_hogar
            
            if diferencial > 0:
                x = diferencial / (renta * 0.1) if umbral_hogar <= 0 else diferencial / umbral_hogar
                tasa = self.L * (1 - exp(-self.sigma * abs(x)))
                total_recaudado += diferencial * tasa
            else:
                total_ayudas += abs(diferencial)
                
        saldo = total_recaudado - total_ayudas - self.G_op
        return saldo, total_recaudado, total_ayudas

    def _ejecutar_logica_central(self):
        saldo_actual, rec_actual, ayudas_actual = self.simular_balance(self.k_base)
        ajuste_emergencia_activado = False

        if saldo_actual < 0:
            print(f"\n [ALERTA CRÍTICA] El sistema es INSOLVENTE.")
            print(f" Déficit detectado: {abs(saldo_actual):.2f} €")
            
            k_min, k_max = 0.0, self.k_base
            for _ in range(100):
                k_mid = (k_min + k_max) / 2
                s_mid, _, _ = self.simular_balance(k_mid)
                if s_mid >= 0: k_min = k_mid
                else: k_max = k_mid
            
            print(f"\nDECISIÓN DE EMERGENCIA REQUERIDA:")
            print(f" 1 - Adquirir DEUDA PÚBLICA para mantener k_base ({self.k_base:.2f}€).")
            print(f" 2 - AJUSTE FISCAL: Reducir k_base al punto de equilibrio ({k_min:.2f}€).")
            
            while True:
                opcion = input("Seleccione una opción (1/2): ")
                if opcion == "1":
                    print("\nRESOLUCIÓN: Se asume déficit vía Deuda Pública. k_base mantenido.")
                    break
                elif opcion == "2":
                    self.k_base = k_min
                    ajuste_emergencia_activado = True
                    print(f"\nAJUSTE APLICADO: k_base reducido a {self.k_base:.2f}€ para garantizar solvencia.")
                    break
                else:
                    print("Opción no válida.")

        if self.k_base < self.k_arope:
            print(f"\n[EVALUACIÓN DE DIGNIDAD] k_base ({self.k_base:.2f}€) < AROPE ({self.k_arope:.2f}€).")
            
            if ajuste_emergencia_activado:
                print("PROTOCOLO PSD BLOQUEADO: No se puede aumentar el gasto tras un recorte de emergencia.")
            else:
                saldo_psd, _, _ = self.simular_balance(self.k_arope)
                if saldo_psd >= 0:
                    print(f"PROYECCIÓN: El sistema tiene superávit suficiente para alcanzar el estándar AROPE.")
                    print(f" 1 - NO: Mantener k_base actual y maximizar ahorro estatal.")
                    print(f" 2 - SÍ: Activar PROTOCOLO PSD (Subir sueldo a {self.k_arope:.2f}€).")
                    
                    while True:
                        op_psd = input("¿Desea aplicar el ajuste de dignidad? (1/2): ")
                        if op_psd == "2":
                            self.k_base = self.k_arope
                            print("PROTOCOLO PSD ACTIVADO: El sistema ahora cumple con el estándar de dignidad.")
                            break
                        elif op_psd == "1":
                            print("PSD RECHAZADO: Se mantiene k_base original por prudencia fiscal.")
                            break
                        else:
                            print("Opción no válida.")
                else:
                    print(f"PSD NO VIABLE: Subir a nivel AROPE generaría un déficit de {abs(saldo_psd):.2f} €.")
        else:
            print(f"\n[SISTEMA ÓPTIMO] El suelo vitalicio ya supera el umbral de pobreza.")

        self._finalizar_auditoria()

    def _finalizar_auditoria(self):
        saldo, rec, ayu = self.simular_balance(self.k_base)
        print(f"\n LIQUIDACIÓN FINAL")
        print(f"k_base definitivo: {self.k_base:.2f} €")
        print(f"Recaudación: {rec:.2f} € | Ayudas: {ayu:.2f} € | Gasto Estado: {self.G_op:.2f} €")
        print(f"SALDO NETO: {saldo:.2f} €")
        print(f"Estado: {'SOLVENTE' if saldo >= 0 else 'DÉFICIT (DEUDA)'}")
        print("-" * 40)


class EFRD_AdvancedVisualizer:
    def __init__(self, motor):
        self.motor = motor

    def comparar_sigmas(self, ingresos, sigmas, adultos_extra, hijos):
        plt.figure()
        for sigma in sigmas:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.sigma = sigma
            cuotas = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos)["C_cuota"] for i in ingresos]
            plt.plot(ingresos, cuotas, label=f"sigma={sigma}")

        plt.title("Impacto de σ en la progresividad")
        plt.xlabel("Ingreso (€)")
        plt.ylabel("Cuota (€)")
        plt.legend()
        plt.grid()
        plt.show()

    def comparar_limite_L(self, ingresos, limites, adultos_extra=0, hijos=0):
        plt.figure()
        for L in limites:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.L = L
            tipos = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos)["Tipo_Efectivo"] for i in ingresos]
            plt.plot(ingresos, tipos, label=f"L={L}")

        plt.title("Impacto del límite máximo L")
        plt.xlabel("Ingreso (€)")
        plt.ylabel("Tipo efectivo (%)")
        plt.legend()
        plt.grid()
        plt.show()

    def comparar_alpha(self, ingresos, alphas, adultos_extra=0, hijos=0):
        plt.figure()
        for alpha in alphas:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.alpha = alpha
            motor_tmp.k_base = motor_tmp.alpha * (motor_tmp.Y / motor_tmp.N_total * (1 - motor_tmp.G)) * motor_tmp.pi
            netos = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos)["Neto"] for i in ingresos]
            plt.plot(ingresos, netos, label=f"alpha={alpha}")

        plt.title("Impacto de α (nivel de renta garantizada)")
        plt.xlabel("Ingreso (€)")
        plt.ylabel("Ingreso Neto (€)")
        plt.legend()
        plt.grid()
        plt.show()

    def mapa_calor(self, ingresos, phis):
        matriz = zeros((len(phis), len(ingresos)))
        for i, phi in enumerate(phis):
            for j, ingreso in enumerate(ingresos):
                adultos_extra = int((phi - 1) / 0.5)
                hijos = int((phi - 1 - adultos_extra * 0.5) / 0.3)
                r = self.motor.calcular_cuota_hogar(
                    ingreso, num_adultos_extra=max(0, adultos_extra), num_hijos=max(0, hijos)
                )
                matriz[i, j] = r["Neto"]

        plt.figure()
        plt.imshow(matriz, aspect='auto', origin='lower', extent=[min(ingresos), max(ingresos), min(phis), max(phis)])
        plt.colorbar(label="Ingreso Neto (€)")
        plt.title("Mapa de Calor del Sistema Redistributivo")
        plt.xlabel("Ingreso Bruto (€)")
        plt.ylabel("Factor hogar (φ)")
        plt.show()

        
class EFRD_AnalyticVisualizer:
    def __init__(self, motor_efrd):
        self.motor = motor_efrd

    def _calcular_individual(self, renta, gamma, phi_total, k_base_test=None):
        k = k_base_test if k_base_test is not None else self.motor.k_base
        umbral_hogar = k * gamma * phi_total
        diferencial = renta - umbral_hogar
        
        if diferencial > 0:
            x = diferencial / (renta * 0.1) if umbral_hogar <= 0 else diferencial / umbral_hogar
            tasa = self.motor.L * (1 - exp(-self.motor.sigma * abs(x)))
            impuesto = diferencial * tasa
            neto = renta - impuesto
            tipo_efectivo = (impuesto / renta) * 100 if renta > 0 else 0
        else:
            subsidio = abs(diferencial)
            neto = renta + subsidio
            tipo_efectivo = -(subsidio / renta) * 100 if renta > 0 else -100
            
        return neto, tipo_efectivo

    def graficar_curva_sostenibilidad(self, rango_k=None):
        if rango_k is None:
            rango_k = linspace(0, self.motor.k_base * 2, 100)
            
        recaudaciones = []
        ayudas = []
        saldos = []
        
        for k in rango_k:
            saldo, rec, ayu = self.motor.simular_balance(k)
            recaudaciones.append(rec)
            ayudas.append(ayu)
            saldos.append(saldo)
            
        plt.figure(figsize=(10, 6))
        plt.plot(rango_k, recaudaciones, label="Recaudación Total (Impuestos)", color="green", lw=2)
        plt.plot(rango_k, ayudas, label="Ayudas Totales (Subsidios)", color="red", lw=2)
        plt.plot(rango_k, saldos, label="Saldo Neto del Estado", color="blue", linestyle="--", lw=2)
        
        plt.axhline(0, color="black", linestyle=":", alpha=0.6)
        plt.axvline(self.motor.k_base, color="purple", linestyle="-.", label=f"k_base Actual ({self.motor.k_base:.2f}€)")
        
        plt.title("Análisis de Sostenibilidad Presupuestaria EFRD", fontsize=14, fontweight='bold')
        plt.xlabel("Suelo Vitalicio de Prueba (k_base en €)", fontsize=12)
        plt.ylabel("Euros (€)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def graficar_ingreso_bruto_vs_neto(self, max_ingreso=60000, phis=[1.0, 1.5, 2.3], gamma=1.0):
        ingresos_brutos = linspace(0, max_ingreso, 500)
        plt.figure(figsize=(10, 6))
        plt.plot(ingresos_brutos, ingresos_brutos, color="black", linestyle=":", label="Sin Sistema (Neto = Bruto)", alpha=0.7)
        
        for phi in phis:
            netos = [self._calcular_individual(b, gamma, phi)[0] for b in ingresos_brutos]
            plt.plot(ingresos_brutos, netos, label=rf"Hogar con $\phi$ = {phi}")
            
        plt.title("Redistribución del Ingreso: Bruto vs Neto", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto del Hogar (€ / año)", fontsize=12)
        plt.ylabel("Ingreso Neto Disponible (€ / año)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def graficar_tipo_impositivo_efectivo(self, max_ingreso=80000, phis=[1.0, 2.0], gamma=1.0):
        ingresos_brutos = linspace(1000, max_ingreso, 500)
        plt.figure(figsize=(10, 6))
        
        for phi in phis:
            tipos = [self._calcular_individual(b, gamma, phi)[1] for b in ingresos_brutos]
            plt.plot(ingresos_brutos, tipos, label=rf"Hogar con $\phi$ = {phi}")
            
        plt.axhline(self.motor.L * 100, color="red", linestyle="--", label=f"Límite asíntota L ({self.motor.L*100}%)")
        plt.axhline(0, color="black", lw=1)
        
        plt.title("Tipo Impositivo Efectivo (Progresividad Asintótica)", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto del Hogar (€)", fontsize=12)
        plt.ylabel("Tipo Efectivo (%)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    def graficar_mapa_calor_bienestar(self, max_ingreso=50000, phi_min=1.0, phi_max=3.0, gamma=1.0):
        ingresos = linspace(0, max_ingreso, 100)
        phis = linspace(phi_min, phi_max, 100)
        matriz_neto = zeros((len(phis), len(ingresos)))
        
        for i, phi in enumerate(phis):
            for j, ing in enumerate(ingresos):
                matriz_neto[i, j] = self._calcular_individual(ing, gamma, phi)[0]
                
        plt.figure(figsize=(11, 7))
        hd = plt.imshow(matriz_neto, aspect='auto', origin='lower', 
                        extent=[min(ingresos), max(ingresos), min(phis), max(phis)],
                        cmap='viridis')
        
        cbar = plt.colorbar(hd)
        cbar.set_label('Ingreso Neto Final del Hogar (€)', fontsize=12)
        
        plt.title("Mapa de Calor Macroeconómico: Ingreso Neto del Sistema", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto (€)", fontsize=12)
        plt.ylabel(r"Factor de Multiplicación del Hogar ($\phi$)", fontsize=12)
        plt.tight_layout()
        plt.show()


    def graficar_distribucion_ingresos(self, ingresos=None, bins=50):
        """
        Grafica la distribución real de la población (Nº de personas x ingreso bruto anual).
        Muestra la media, mediana, percentiles y ajusta el límite al máximo de la BD.
        """
        import numpy as np
        import matplotlib.pyplot as plt
        import sqlite3
        import os

        # 1. Recuperación y limpieza de datos de la BD
        if ingresos is None:
            # Intento 1: Buscar en memoria del motor
            if hasattr(self.motor, 'ingresos_brutos') and self.motor.ingresos_brutos is not None:
                ingresos = self.motor.ingresos_brutos
            elif hasattr(self.motor, 'poblacion') and self.motor.poblacion is not None:
                pob = self.motor.poblacion
                if hasattr(pob, 'columns') and 'renta_mensual' in pob.columns:
                    ingresos = pob['renta_mensual'].to_numpy() * 12
                elif isinstance(pob, list) and len(pob) > 0:
                    if hasattr(pob[0], 'renta_mensual'):
                        ingresos = [p.renta_mensual * 12 for p in pob]

            # Intento 2: Fallback directo a la tabla ya procesada en SQLite
            if (ingresos is None or len(ingresos) == 0) and hasattr(self.motor, 'db_path'):
                ruta_db = self.motor.db_path
                # Si la ruta relativa falla, intentamos resolver de forma absoluta
                if not os.path.exists(ruta_db):
                    ruta_db = os.path.join(os.getcwd(), ruta_db)

                if os.path.exists(ruta_db):
                    try:
                        conn = sqlite3.connect(ruta_db)
                        cursor = conn.cursor()
                        # Leemos directamente de la tabla que el log confirmó como exitosa
                        cursor.execute("SELECT renta_mensual FROM Base_Datos_MACRO")
                        filas = cursor.fetchall()
                        if filas:
                            ingresos = [float(f[0]) * 12 for f in filas if f[0] is not None]
                        conn.close()
                    except Exception as e:
                        print(f"[Aviso Visualizador] No se pudo leer la tabla: {e}")

        # 2. Conversión estricta a NumPy
        if ingresos is not None:
            ingresos = np.array(ingresos, dtype=float)
            ingresos = ingresos[~np.isnan(ingresos)]
        else:
            ingresos = np.array([])

        if ingresos.size == 0:
            print("Error crítico: El visualizador no pudo extraer los ingresos desde ninguna fuente.")
            return

        # 3. Procesamiento de métricas estadísticas
        min_ingreso = np.min(ingresos)
        max_ingreso_real = np.max(ingresos)
        media = np.mean(ingresos)
        mediana = np.median(ingresos)
        desviacion = np.std(ingresos)
        p25 = np.percentile(ingresos, 25)
        p75 = np.percentile(ingresos, 75)
        total_poblacion = len(ingresos)

        # 4. Construcción del gráfico
        plt.figure(figsize=(12, 7))

        plt.hist(ingresos, bins=bins, range=(min_ingreso, max_ingreso_real),
                 color="skyblue", edgecolor="steelblue", alpha=0.7, 
                 label="Densidad de Población")

        # Líneas analíticas (Media y Mediana)
        plt.axvline(media, color="darkgreen", linestyle="--", lw=2, label=f"Media: {media:,.2f}€")
        plt.axvline(mediana, color="darkorange", linestyle="-", lw=2, label=f"Mediana: {mediana:,.2f}€")

        if hasattr(self.motor, 'k_base') and self.motor.k_base is not None:
            plt.axvline(self.motor.k_base, color="purple", linestyle="-.", lw=2, 
                        label=f"k_base Sistema ({self.motor.k_base:,.2f}€)")
            plt.axvspan(0, self.motor.k_base, color='red', alpha=0.04, label="Zona de Subsidio Neto")

        # 5. Cuadro informativo
        info_panel = (
            f"Análisis de la BD:\n"
            f"  Población (N): {total_poblacion:,}\n"
            f"  Mínimo: {min_ingreso:,.2f}€\n"
            f"  Máximo: {max_ingreso_real:,.2f}€\n"
            f"  Desv. Estándar: {desviacion:,.2f}€\n"
            f"  Percentil 25 (P25): {p25:,.2f}€\n"
            f"  Percentil 75 (P75): {p75:,.2f}€"
        )

        props = dict(boxstyle='round,pad=0.6', facecolor='white', alpha=0.9, edgecolor='lightgray')
        plt.gca().text(0.97, 0.95, info_panel, transform=plt.gca().transAxes, 
                        fontsize=10, verticalalignment='top', horizontalalignment='right', bbox=props, family='monospace')

        # 6. Formateo estético y visualización
        plt.title("Análisis de Distribución de Ingresos Brutos Anuales", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Ingreso Bruto Anual (€)", fontsize=12)
        plt.ylabel("Número de Personas (Frecuencia)", fontsize=12)

        plt.xlim(min_ingreso, max_ingreso_real)
        plt.legend(loc="upper left", fontsize=10)
        plt.grid(True, alpha=0.25, linestyle="--")

        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

        plt.tight_layout()
        plt.show()
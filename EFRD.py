from math import exp, ceil
import matplotlib
# matplotlib.use('Agg') # Fuerza renderizado en memoria para guardar a PNG
import matplotlib.pyplot as plt
from numpy import zeros, linspace
from copy import deepcopy
from traductores import get_renta_mediana
from sqlite3 import connect
from os import path
import os
import json


RATIO_MASA_CRITICA_MIN = 0.40   # Al menos el 40 % de la población debe ser contribuyente neto


class EFRD_Protocol_v4_1:
    def __init__(self, PIB_Y, Gini, Alpha, Sigma, Limite_L, G_op, IPC_Pi,
                 db_path, tabla_central, modo: str = "interactivo"):
        """
        Parámetro `modo`:
          'interactivo' → pide decisión al usuario por consola.
          'deuda'       → asume automáticamente emitir deuda pública.
          'ajuste'      → asume automáticamente el recorte de k_base al equilibrio.
          'test'        → no ejecuta ningún protocolo de emergencia.
        """
        self.Y = PIB_Y
        self.G = Gini
        self.alpha = Alpha
        self.sigma = Sigma
        self.L = Limite_L
        self.G_op = G_op
        self.pi = IPC_Pi
        self.modo = modo
        self.renta_mediana_nacional = get_renta_mediana()
        self.db_path = db_path
        self.tabla_central = tabla_central

        self.unidades_convivencia = []
        self.N_total = 0

        self._cargar_datos_desde_db()

        if self.N_total == 0:
            print(" ERROR: No se han encontrado ciudadanos en la base de datos.")
            self.k_base = 0
            return

        # CÁLCULO DE MACROMAGNITUDES (Corregido a escala mensual y nacional)
        self.k_base = self.calcular_k_base(self.alpha, self.Y, self.N_total, self.G, self.pi)
        
        # El AROPE también debe ser mensual (la renta mediana suele venir anual)
        self.k_arope = (0.6 * self.renta_mediana_nacional) / 12.0

        print(f" PROTOCOLO EFRD: CARGANDO SIST.")
        print(f" Ciudadanos censados (N_total): {self.N_total}")
        print(f" Hogares procesados: {len(self.unidades_convivencia)}")
        print(f" Suelo Vitalicio (k_base): {self.k_base:.2f} €/mes")
        print(f" Umbral Pobreza (AROPE): {self.k_arope:.2f} €/mes")
        print("-" * 40)

        self._ejecutar_logica_central()

    @staticmethod
    def calcular_k_base(alpha, Y, N_muestra, G, pi):
        """Fórmula canónica del suelo vitalicio base: α·(Y/N)·(G)·π ajustado a mes."""
        if N_muestra == 0:
            raise ValueError("N (población) no puede ser cero.")
        
        # CORRECCIÓN 1: Evitar que el PIB nacional se divida entre una muestra pequeña
        # Si la BD tiene menos de 40 millones, usamos la población aproximada de España.
        N_real = N_muestra if N_muestra > 40000000 else 48060000
        pib_per_capita_anual = Y / N_real
        
        k_base_anual = alpha * pib_per_capita_anual * G * pi
        
        # CORRECCIÓN 2: Escalar a mensual para cuadrar con la renta de la DB
        k_base_mensual = k_base_anual / 12.0
        return k_base_mensual

    @staticmethod
    def _calcular_x(diferencial: float, k_hogar: float) -> float:
        if k_hogar > 0:
            return diferencial / k_hogar
        return 10.0

    def _cargar_datos_desde_db(self):
        if not path.exists(self.db_path):
            print(f"Archivo no encontrado: {self.db_path}")
            return

        with connect(self.db_path) as conn:
            cursor = conn.cursor()
            query_agrupada = f"""
                SELECT
                    ref_catastral,
                    SUM(renta_mensual) AS renta_total,
                    SUM(phi) AS phi_total,
                    MAX(gamma) AS gamma,
                    COUNT(dni_nie_nif) AS num_inquilinos
                FROM {self.tabla_central}
                GROUP BY ref_catastral
            """
            cursor.execute(query_agrupada)

            for ref_catastral, renta_total, phi_total, gamma, num_inquilinos in cursor.fetchall():
                self.N_total += num_inquilinos
                self.unidades_convivencia.append({
                    'ref_catastral': ref_catastral,
                    'renta_total': renta_total,
                    'phi_total': phi_total,
                    'gamma': gamma
                })

    def calcular_cuota_hogar(self, renta, num_adultos_extra=0, num_hijos=0, gamma=1.0, es_anual=True):
        """
        Calcula la cuota. Si 'es_anual' es True (usado por visualizadores), 
        escala el k_base a anual para la comparación.
        """
        phi_total = 1.0 + (num_adultos_extra * 0.5) + (num_hijos * 0.3)
        k_b = self.k_base * 12 if es_anual else self.k_base
        umbral_hogar = k_b * gamma * phi_total
        diferencial = renta - umbral_hogar

        if diferencial > 0:
            x = EFRD_Protocol_v4_1._calcular_x(diferencial, umbral_hogar)
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
            renta = hogar['renta_total'] # Renta mensual
            diferencial = renta - umbral_hogar

            if diferencial > 0:
                x = EFRD_Protocol_v4_1._calcular_x(diferencial, umbral_hogar)
                tasa = self.L * (1 - exp(-self.sigma * abs(x)))
                total_recaudado += diferencial * tasa
            else:
                total_ayudas += abs(diferencial)

        # AÑADIDO: Excedente Estratégico (5% de lo recaudado) para sustento del Estado
        excedente_estrategico = total_recaudado * 0.05
        saldo = total_recaudado - total_ayudas - self.G_op - excedente_estrategico
        
        return saldo, total_recaudado, total_ayudas, excedente_estrategico

    def _ejecutar_logica_central(self):
        saldo_actual, rec_actual, ayudas_actual, exc_actual = self.simular_balance(self.k_base)
        ajuste_emergencia_activado = False

        if saldo_actual < 0:
            print(f"\n [ALERTA CRÍTICA] El sistema es INSOLVENTE.")
            print(f" Déficit detectado: {abs(saldo_actual):.2f} €/mes (incluye excedente estatal)")

            k_min, k_max = 0.0, self.k_base
            for _ in range(25):
                k_mid = (k_min + k_max) / 2
                s_mid, _, _, _ = self.simular_balance(k_mid)
                if s_mid >= 0:
                    k_min = k_mid
                else:
                    k_max = k_mid

            if self.modo == "interactivo":
                opcion = self._pedir_decision_insolvencia(k_min)
            elif self.modo == "deuda":
                opcion = "1"
            elif self.modo in ("ajuste", "test"):
                opcion = "2"
            else:
                opcion = "1"

            if opcion == "2":
                self.k_base = k_min
                ajuste_emergencia_activado = True
                print(f"\nAJUSTE APLICADO: k_base reducido a {self.k_base:.2f}€/mes para garantizar solvencia.")
            else:
                print("\nRESOLUCIÓN: Se asume déficit vía Deuda Pública. k_base mantenido.")

        if self.k_base < self.k_arope:
            print(f"\n[EVALUACIÓN DE DIGNIDAD] k_base ({self.k_base:.2f}€) < AROPE ({self.k_arope:.2f}€).")

            if ajuste_emergencia_activado:
                print("PROTOCOLO PSD BLOQUEADO: No se puede aumentar el gasto tras un recorte de emergencia.")
            else:
                saldo_psd, _, _, _ = self.simular_balance(self.k_arope)
                if saldo_psd >= 0:
                    print(f"PROYECCIÓN: El sistema tiene superávit suficiente para alcanzar el estándar AROPE.")
                    if self.modo == "interactivo":
                        self._pedir_decision_psd()
                else:
                    print(f"PSD NO VIABLE: Subir a nivel AROPE generaría un déficit de {abs(saldo_psd):.2f} €/mes.")
        else:
            print(f"\n[SISTEMA ÓPTIMO] El suelo vitalicio ya supera el umbral de pobreza mensual.")

        self._finalizar_auditoria()

    def _pedir_decision_insolvencia(self, k_equilibrio: float) -> str:
        print(f"\nDECISIÓN DE EMERGENCIA REQUERIDA:")
        print(f" 1 - Adquirir DEUDA PÚBLICA para mantener k_base ({self.k_base:.2f}€).")
        print(f" 2 - AJUSTE FISCAL: Reducir k_base al punto de equilibrio ({k_equilibrio:.2f}€).")
        while True:
            opcion = input("Seleccione una opción (1/2): ")
            if opcion in ("1", "2"):
                return opcion
            print("Opción no válida.")

    def _pedir_decision_psd(self):
        print(f" 1 - NO: Mantener k_base actual y maximizar ahorro estatal.")
        print(f" 2 - SÍ: Activar PROTOCOLO PSD (Subir suelo a {self.k_arope:.2f}€).")
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

    def _verificar_masa_critica(self):
        total = len(self.unidades_convivencia)
        if total == 0:
            return

        contribuyentes = sum(
            1 for h in self.unidades_convivencia
            if h["renta_total"] > self.k_base * h["phi_total"] * h["gamma"]
        )
        ratio = contribuyentes / total

        print(f"\n[MASA CRÍTICA] Contribuyentes: {contribuyentes}/{total} ({ratio:.1%})")
        if ratio < RATIO_MASA_CRITICA_MIN:
            print(f"  ⚠ ALERTA: Ratio ({ratio:.1%}) por debajo del mínimo ({RATIO_MASA_CRITICA_MIN:.0%}).")
            print(f"  El sistema depende de demasiados receptores. Riesgo estructural elevado.")
        else:
            print(f"  ✓ Masa crítica sostenible.")

    def _finalizar_auditoria(self):
        self._verificar_masa_critica()

        saldo, rec, ayu, exc = self.simular_balance(self.k_base)
        print(f"\n LIQUIDACIÓN FINAL MENSUAL")
        print(f"k_base definitivo: {self.k_base:.2f} €/mes")
        print(f"Recaudación: {rec:.2f} € | Ayudas: {ayu:.2f} €")
        print(f"Gasto Fijo Estado: {self.G_op:.2f} € | Excedente Reservado: {exc:.2f} €")
        print(f"SALDO NETO (Tras reservas): {saldo:.2f} €")
        print(f"Estado: {'SOLVENTE' if saldo >= 0 else 'DÉFICIT (DEUDA)'}")
        print("-" * 40)

        ruta_config = os.path.join(os.path.dirname(self.db_path), "efrd_config.json")
        os.makedirs(os.path.dirname(ruta_config), exist_ok=True)
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump({
                "k_base": self.k_base,
                "sigma": self.sigma,
                "L": self.L,
                "tabla": self.tabla_central,
                "db_path": self.db_path
            }, f, indent=2)
        print(f"[EFRD] Configuración guardada en: {ruta_config}")


class EFRD_AdvancedVisualizer:
    def __init__(self, motor):
        self.motor = motor

    def comparar_sigmas(self, ingresos, sigmas, adultos_extra, hijos):
        plt.figure()
        for sigma in sigmas:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.sigma = sigma
            cuotas = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos, es_anual=True)["C_cuota"] for i in ingresos]
            plt.plot(ingresos, cuotas, label=f"sigma={sigma}")

        plt.title("Impacto de σ en la progresividad")
        plt.xlabel("Ingreso Bruto Anual (€)")
        plt.ylabel("Cuota Anual (€)")
        plt.legend()
        plt.grid()
        plt.show()

    def comparar_limite_L(self, ingresos, limites, adultos_extra=0, hijos=0):
        plt.figure()
        for L in limites:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.L = L
            tipos = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos, es_anual=True)["Tipo_Efectivo"] for i in ingresos]
            plt.plot(ingresos, tipos, label=f"L={L}")

        plt.title("Impacto del límite máximo L")
        plt.xlabel("Ingreso Bruto Anual (€)")
        plt.ylabel("Tipo efectivo (%)")
        plt.legend()
        plt.grid()
        plt.show()

    def comparar_alpha(self, ingresos, alphas, adultos_extra=0, hijos=0):
        plt.figure()
        for alpha in alphas:
            motor_tmp = deepcopy(self.motor)
            motor_tmp.alpha = alpha
            motor_tmp.k_base = EFRD_Protocol_v4_1.calcular_k_base(
                alpha, motor_tmp.Y, motor_tmp.N_total, motor_tmp.G, motor_tmp.pi
            )
            netos = [motor_tmp.calcular_cuota_hogar(i, adultos_extra, hijos, es_anual=True)["Neto"] for i in ingresos]
            plt.plot(ingresos, netos, label=f"alpha={alpha}")

        plt.title("Impacto de α (nivel de renta garantizada)")
        plt.xlabel("Ingreso Bruto Anual (€)")
        plt.ylabel("Ingreso Neto Anual (€)")
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
                    ingreso, num_adultos_extra=max(0, adultos_extra), num_hijos=max(0, hijos), es_anual=True
                )
                matriz[i, j] = r["Neto"]

        plt.figure()
        plt.imshow(matriz, aspect='auto', origin='lower',
                   extent=[min(ingresos), max(ingresos), min(phis), max(phis)])
        plt.colorbar(label="Ingreso Neto Anual (€)")
        plt.title("Mapa de Calor del Sistema Redistributivo")
        plt.xlabel("Ingreso Bruto Anual (€)")
        plt.ylabel("Factor hogar (φ)")
        plt.show()


class EFRD_AnalyticVisualizer:
    def __init__(self, motor_efrd):
        self.motor = motor_efrd

    @property
    def _L(self):
        return self.motor.L

    def _calcular_individual_anual(self, renta_anual, gamma, phi_total, k_base_test=None):
        # Transforma el k_base mensual del motor a anual para la gráfica
        k_b = (k_base_test if k_base_test is not None else self.motor.k_base) * 12
        umbral_hogar = k_b * gamma * phi_total
        diferencial = renta_anual - umbral_hogar

        if diferencial > 0:
            x = EFRD_Protocol_v4_1._calcular_x(diferencial, umbral_hogar)
            tasa = self.motor.L * (1 - exp(-self.motor.sigma * abs(x)))
            impuesto = diferencial * tasa
            neto = renta_anual - impuesto
            tipo_efectivo = (impuesto / renta_anual) * 100 if renta_anual > 0 else 0
        else:
            subsidio = abs(diferencial)
            neto = renta_anual + subsidio
            tipo_efectivo = -(subsidio / renta_anual) * 100 if renta_anual > 0 else -100

        return neto, tipo_efectivo

    def graficar_curva_sostenibilidad(self, rango_k=None,
                                      guardar: bool = False,
                                      ruta: str = "ejemplos/salida/sostenibilidad.png"):
        if rango_k is None:
            rango_k = linspace(0, self.motor.k_base * 2, 100)

        recaudaciones = []
        ayudas = []
        saldos = []

        for k in rango_k:
            saldo, rec, ayu, _ = self.motor.simular_balance(k)
            recaudaciones.append(rec)
            ayudas.append(ayu)
            saldos.append(saldo)

        plt.figure(figsize=(10, 6))
        plt.plot(rango_k, recaudaciones, label="Recaudación Mensual", color="green", lw=2)
        plt.plot(rango_k, ayudas, label="Ayudas Mensuales", color="red", lw=2)
        plt.plot(rango_k, saldos, label="Saldo Neto (Tras Excedente)", color="blue", linestyle="--", lw=2)

        plt.axhline(0, color="black", linestyle=":", alpha=0.6)
        plt.axvline(self.motor.k_base, color="purple", linestyle="-.",
                    label=f"k_base Actual ({self.motor.k_base:.2f}€/mes)")

        plt.title("Análisis de Sostenibilidad Presupuestaria EFRD", fontsize=14, fontweight='bold')
        plt.xlabel("Suelo Vitalicio Mensual de Prueba (k_base en €)", fontsize=12)
        plt.ylabel("Euros (€/mes)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if guardar:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            plt.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Gráfica guardada en: {ruta}")
        else:
            plt.show()
        plt.close()

    def graficar_ingreso_bruto_vs_neto(self, max_ingreso=60000, phis=None, gamma=1.0,
                                       guardar: bool = False,
                                       ruta: str = "ejemplos/salida/bruto_vs_neto.png"):
        if phis is None:
            phis = [1.0, 1.5, 2.3]
        ingresos_brutos = linspace(0, max_ingreso, 500)
        plt.figure(figsize=(10, 6))
        plt.plot(ingresos_brutos, ingresos_brutos, color="black", linestyle=":",
                 label="Sin Sistema (Neto = Bruto)", alpha=0.7)

        for phi in phis:
            netos = [self._calcular_individual_anual(b, gamma, phi)[0] for b in ingresos_brutos]
            plt.plot(ingresos_brutos, netos, label=rf"Hogar con $\phi$ = {phi}")

        plt.title("Redistribución del Ingreso: Bruto vs Neto Anual", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto del Hogar (€ / año)", fontsize=12)
        plt.ylabel("Ingreso Neto Disponible (€ / año)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if guardar:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            plt.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Gráfica guardada en: {ruta}")
        else:
            plt.show()
        plt.close()

    def graficar_tipo_impositivo_efectivo(self, max_ingreso=80000, phis=None, gamma=1.0,
                                          guardar: bool = False,
                                          ruta: str = "ejemplos/salida/tipo_efectivo.png"):
        if phis is None:
            phis = [1.0, 2.0]
        ingresos_brutos = linspace(1000, max_ingreso, 500)
        plt.figure(figsize=(10, 6))

        for phi in phis:
            tipos = [self._calcular_individual_anual(b, gamma, phi)[1] for b in ingresos_brutos]
            plt.plot(ingresos_brutos, tipos, label=rf"Hogar con $\phi$ = {phi}")

        plt.axhline(self._L * 100, color="red", linestyle="--",
                    label=f"Límite asíntota L ({self._L * 100:.0f}%)")
        plt.axhline(0, color="black", lw=1)

        plt.title("Tipo Impositivo Efectivo (Progresividad Asintótica)", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto del Hogar (€ / año)", fontsize=12)
        plt.ylabel("Tipo Efectivo (%)", fontsize=12)
        plt.legend(loc="best")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if guardar:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            plt.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Gráfica guardada en: {ruta}")
        else:
            plt.show()
        plt.close()

    def graficar_mapa_calor_bienestar(self, max_ingreso=50000, phi_min=1.0, phi_max=3.0, gamma=1.0,
                                      guardar: bool = False,
                                      ruta: str = "ejemplos/salida/mapa_calor.png"):
        ingresos = linspace(0, max_ingreso, 100)
        phis = linspace(phi_min, phi_max, 100)
        matriz_neto = zeros((len(phis), len(ingresos)))

        for i, phi in enumerate(phis):
            for j, ing in enumerate(ingresos):
                matriz_neto[i, j] = self._calcular_individual_anual(ing, gamma, phi)[0]

        plt.figure(figsize=(11, 7))
        hd = plt.imshow(matriz_neto, aspect='auto', origin='lower',
                        extent=[min(ingresos), max(ingresos), min(phis), max(phis)],
                        cmap='viridis')

        cbar = plt.colorbar(hd)
        cbar.set_label('Ingreso Neto Final del Hogar Anual (€)', fontsize=12)

        plt.title("Mapa de Calor Macroeconómico: Ingreso Neto del Sistema", fontsize=14, fontweight='bold')
        plt.xlabel("Ingreso Bruto Anual (€)", fontsize=12)
        plt.ylabel(r"Factor de Multiplicación del Hogar ($\phi$)", fontsize=12)
        plt.tight_layout()

        if guardar:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            plt.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Gráfica guardada en: {ruta}")
        else:
            plt.show()
        plt.close()

    def graficar_distribucion_ingresos(self, bins=50,
                                       guardar: bool = False,
                                       ruta: str = "ejemplos/salida/distribucion_ingresos.png"):
        import numpy as np
        import sqlite3

        ruta_db = self.motor.db_path
        if not os.path.exists(ruta_db):
            ruta_db = os.path.join(os.getcwd(), ruta_db)

        if not os.path.exists(ruta_db):
            print(f"[Visualizador] No se encontró la BD en: {self.motor.db_path}")
            return

        try:
            with sqlite3.connect(ruta_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT renta_mensual FROM {self.motor.tabla_central} WHERE renta_mensual IS NOT NULL"
                )
                # Convierte la renta mensual a anual
                ingresos = np.array([float(f[0]) * 12 for f in cursor.fetchall()])
        except Exception as e:
            print(f"[Visualizador] Error al leer la BD: {e}")
            return

        if ingresos.size == 0:
            print("[Visualizador] La tabla de ingresos está vacía.")
            return

        ingresos = ingresos[~np.isnan(ingresos)]

        if ingresos.size == 0:
            print("[Visualizador] No hay datos válidos tras filtrar NaN.")
            return

        min_ingreso = np.min(ingresos)
        max_ingreso_real = np.max(ingresos)
        media = np.mean(ingresos)
        mediana = np.median(ingresos)
        desviacion = np.std(ingresos)
        p25 = np.percentile(ingresos, 25)
        p75 = np.percentile(ingresos, 75)
        total_poblacion = len(ingresos)

        plt.figure(figsize=(12, 7))
        plt.hist(ingresos, bins=bins, range=(min_ingreso, max_ingreso_real),
                 color="skyblue", edgecolor="steelblue", alpha=0.7,
                 label="Densidad de Población")

        plt.axvline(media, color="darkgreen", linestyle="--", lw=2, label=f"Media: {media:,.2f}€")
        plt.axvline(mediana, color="darkorange", linestyle="-", lw=2, label=f"Mediana: {mediana:,.2f}€")

        if hasattr(self.motor, 'k_base') and self.motor.k_base is not None:
            # Multiplicamos el k_base por 12 para situarlo en el eje X de renta anual
            plt.axvline(self.motor.k_base * 12, color="purple", linestyle="-.", lw=2,
                        label=f"k_base Anualizado ({(self.motor.k_base * 12):,.2f}€)")
            plt.axvspan(0, self.motor.k_base * 12, color='red', alpha=0.04, label="Zona de Subsidio Neto")

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
                       fontsize=10, verticalalignment='top', horizontalalignment='right',
                       bbox=props, family='monospace')

        plt.title("Análisis de Distribución de Ingresos Brutos Anuales", fontsize=14, fontweight='bold', pad=15)
        plt.xlabel("Ingreso Bruto Anual (€)", fontsize=12)
        plt.ylabel("Número de Personas (Frecuencia)", fontsize=12)
        plt.xlim(min_ingreso, max_ingreso_real)
        plt.legend(loc="upper left", fontsize=10)
        plt.grid(True, alpha=0.25, linestyle="--")
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
        plt.tight_layout()

        if guardar:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            plt.savefig(ruta, dpi=150, bbox_inches="tight")
            print(f"Gráfica guardada en: {ruta}")
        else:
            plt.show()
        plt.close()
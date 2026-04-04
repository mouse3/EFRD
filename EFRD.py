from math import exp, ceil
import matplotlib.pyplot as plt
from numpy import zeros
from copy import deepcopy
from traductores import get_renta_mediana
from sqlite3 import connect
from ast import literal_eval
from os import path
import sqlite3
import ast
from math import exp, ceil

class EFRD_Protocol_v3_2:
    def __init__(self, PIB_Y, Gini, Alpha, Sigma, Limite_L, G_op, IPC_Pi=1.0, db_path='outputs/base_final_efrd.db'):
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
        
        # Inicialización de contadores
        self.unidades_convivencia = []
        self.N_total = 0 
        
        # EXTRACCIÓN DE DATOS (Paso crítico: Contar ciudadanos)
        self._cargar_datos_desde_db()

        if self.N_total == 0:
            print(" ERROR: No se han encontrado ciudadanos en la base de datos.")
            self.k_base = 0
            return

        # CÁLCULO DE MACROMAGNITUDES (Ahora con N_total real)
        # k_base = (Renta per cápita media) * (Equidad) * (Factor de cobertura)
        self.k_base = self.alpha * (self.Y / self.N_total) * (1 - self.G) * self.pi
        self.k_arope = 0.6 * self.renta_mediana_nacional

        print(f" === PROTOCOLO EFRD: CARGA DE SISTEMA ===")
        print(f" Ciudadanos censados (N_total): {self.N_total}")
        print(f" Hogares procesados: {len(self.unidades_convivencia)}")
        print(f" Suelo Vitalicio (k_base): {self.k_base:.2f} €")
        print(f" Umbral Pobreza (AROPE): {self.k_arope:.2f} €")
        print("-" * 40)

        # EJECUCIÓN DE PROTOCOLOS DE SOLVENCIA Y DIGNIDAD
        self._ejecutar_logica_central()

    def _cargar_datos_desde_db(self):
        """
        Recorre la DB y suma cada individuo de las listas para obtener el N_total real.
        """
        if not path.exists(self.db_path):
            print(f"Archivo no encontrado: {self.db_path}")
            return

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT lista_inquilinos, gamma FROM Base_Datos_FINAL")
            
            for fila in cursor.fetchall():
                # lista_inquilinos es una cadena que representa: [(DNI, Renta, Phi), ...]
                inquilinos = ast.literal_eval(fila[0])
                gamma = fila[1]
                
                # ACTUALIZACIÓN DE N_TOTAL: Sumamos la cantidad de personas en esta vivienda
                self.N_total += len(inquilinos)
                
                # Agregamos el hogar para las simulaciones fiscales
                self.unidades_convivencia.append({
                    'renta_total': sum(per[1] for per in inquilinos),
                    'phi_total': sum(per[2] for per in inquilinos),
                    'gamma': gamma
                })

    def simular_balance(self, k_prueba):
        """Calcula recaudación vs ayudas para un k_base dado."""
        total_recaudado = 0
        total_ayudas = 0
        
        for hogar in self.unidades_convivencia:
            # k_hogar = k_base * gamma (zona) * phi (familia)
            umbral_hogar = k_prueba * hogar['gamma'] * hogar['phi_total']
            renta = hogar['renta_total']
            diferencial = renta - umbral_hogar
            
            if diferencial > 0:
                # Impuesto progresivo asintótico
                # Si el umbral es 0 (ajuste extremo), el diferencial tributa sobre sí mismo
                x = diferencial / (renta * 0.1) if umbral_hogar <= 0 else diferencial / umbral_hogar
                tasa = self.L * (1 - exp(-self.sigma * abs(x)))
                total_recaudado += diferencial * tasa
            else:
                # Subsidio de cobertura
                total_ayudas += abs(diferencial)
                
        saldo = total_recaudado - total_ayudas - self.G_op
        return saldo, total_recaudado, total_ayudas

    def _ejecutar_logica_central(self):
        """Protocolo de toma de decisiones interactivo (Solvencia y Dignidad)."""
        saldo_actual, rec_actual, ayudas_actual = self.simular_balance(self.k_base)
        ajuste_emergencia_activado = False

        # Escenario: insolvencia (déficit) ---
        if saldo_actual < 0:
            print(f"\n [ALERTA CRÍTICA] El sistema es INSOLVENTE.")
            print(f" Déficit detectado: {abs(saldo_actual):.2f} €")
            
            # Búsqueda Binaria para hallar el k_base de equilibrio
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

        # Escenario: Ausencia dignidad (protocolo PSD)
        # Se evalúa si el sueldo está por debajo de la pobreza (AROPE)
        if self.k_base < self.k_arope:
            print(f"\n[EVALUACIÓN DE DIGNIDAD] k_base ({self.k_base:.2f}€) < AROPE ({self.k_arope:.2f}€).")
            
            if ajuste_emergencia_activado:
                print("PROTOCOLO PSD BLOQUEADO: No se puede aumentar el gasto tras un recorte de emergencia.")
            else:
                # Simulamos si el sistema aguantaría subir a AROPE
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

        # Finalizamos con la liquidación definitiva
        self._finalizar_auditoria()

    def _finalizar_auditoria(self):
        saldo, rec, ayu = self.simular_balance(self.k_base)
        print(f"\n--- LIQUIDACIÓN FINAL DEL SISTEMA ---")
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
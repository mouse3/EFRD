import math

class EFRD_Protocol_v3_2:
    def __init__(self, PIB_Y, Poblacion_N, Gini, Alpha, Sigma, Limite_L, G_op, IPC_Pi=1.0):
        # Variables de Entrada (Realidad y Política)
        self.Y = PIB_Y
        self.N = Poblacion_N
        self.G = Gini
        self.alpha = Alpha
        self.sigma = Sigma
        self.L = Limite_L
        self.G_op = G_op  # Gastos Operativos del Estado
        self.pi = IPC_Pi
        
        # Cálculo del Suelo Vitalicio Base (k) - Ajustado por Gini e Inflación
        # Implementa la Renta de Bienestar de Sen
        self.k_base = self.alpha * (self.Y / self.N * (1 - self.G)) * self.pi

    def calcular_cuota_hogar(self, ingresos_brutos_totales, num_adultos_extra=0, num_hijos=0):
        """
        Calcula la Cuota Líquida (C) basada en la Unidad de Convivencia (OCDE modificada).
        phi = 1.0 (principal) + 0.5 (adultos extra) + 0.3 (hijos)
        """
        phi = 1.0 + (num_adultos_extra * 0.5) + (num_hijos * 0.3)
        k_hogar = self.k_base * phi
        
        B = ingresos_brutos_totales
        diferencial = B - k_hogar
        
        # Normalización del excedente para la curva exponencial
        x = diferencial / k_hogar if k_hogar != 0 else 0
        
        # Función de Tipo Impositivo Continuo (Asíntota L)
        tipo_impositivo = self.L * (1 - math.exp(-self.sigma * abs(x)))
        
        cuota_C = diferencial * tipo_impositivo
        return {
            "B_bruto": B,
            "phi": phi,
            "k_hogar": round(k_hogar, 2),
            "C_cuota": round(cuota_C, 2),
            "Neto": round(B - cuota_C, 2),
            "Tipo_Efectivo": round((cuota_C / B * 100), 2) if B > 0 else 0
        }

    def auditoria_sistema(self, dataset_poblacion):
        """
        Ejecuta las 4 Inecuaciones de Seguridad del Protocolo.
        Dataset esperado: lista de dicts con {'ingreso': float, 'adultos': int, 'hijos': int}
        """
        resultados = [self.calcular_cuota_hogar(p['ingreso'], p['adultos'], p['hijos']) for p in dataset_poblacion]
        
        recaudacion = sum(r['C_cuota'] for r in resultados if r['C_cuota'] > 0)
        ayudas = sum(abs(r['C_cuota']) for r in resultados if r['C_cuota'] < 0)
        
        # 1. Condición de Solvencia
        solvente = recaudacion >= (ayudas + self.G_op)
        
        # 2. Ratio Crítico de Contribuyentes (R_c)
        contribuyentes = [r for r in resultados if r['C_cuota'] > 0]
        n_contrib = len(contribuyentes)
        c_media_pos = sum(c['C_cuota'] for c in contribuyentes) / n_contrib if n_contrib > 0 else 0
        min_contrib_req = (ayudas + self.G_op) / c_media_pos if c_media_pos > 0 else float('inf')
        
        return {
            "Solvencia_Estado": "OK" if solvente else "RIESGO_DE_QUIEBRA",
            "Balance_Neto_Efectivo": round(recaudacion - ayudas - self.G_op, 2),
            "N_Contribuyentes_Actual": n_contrib,
            "N_Contribuyentes_Minimo_Req": math.ceil(min_contrib_req),
            "Masa_Critica_Suficiente": n_contrib >= min_contrib_req
        }

# --- EJEMPLO DE EJECUCIÓN (Huelva - Escenario Base) ---

# Configuración: PIB 1.6T, 48.5M hab, Gini 0.33, Alpha 0.45, Sigma 0.75, L 0.60, G_op 200B
motor = EFRD_Protocol_v3_2(1.6e12, 48.5e6, 0.33, 0.45, 0.75, 0.60, 200e9)

# Simulación de una familia (2 adultos, 1 hijo, ingresos 22.000€)
print("--- CÁLCULO INDIVIDUAL ---")
familia = motor.calcular_cuota_hogar(22000, num_adultos_extra=1, num_hijos=1)
print(f"Sueldo Hogar Protegido: {familia['k_hogar']}€")
print(f"Cuota Final (C): {familia['C_cuota']}€ ({'Recibe' if familia['C_cuota'] < 0 else 'Paga'})")
print(f"Dinero Neto en Bolsillo: {familia['Neto']}€")

# Auditoría de Solvencia (Muestra pequeña de población)
print("\n--- AUDITORÍA DE SEGURIDAD DEL SISTEMA ---")
poblacion_ejemplo = [
    {'ingreso': 12000, 'adultos': 1, 'hijos': 2},
    {'ingreso': 45000, 'adultos': 1, 'hijos': 0},
    {'ingreso': 90000, 'adultos': 1, 'hijos': 1},
    {'ingreso': 500000, 'adultos': 0, 'hijos': 0}
]
# Ajustamos G_op a escala de la muestra para el ejemplo (ej. 50.000€)
motor.G_op = 50000 
reporte = motor.auditoria_sistema(poblacion_ejemplo)
for k, v in reporte.items():
    print(f"{k}: {v}")
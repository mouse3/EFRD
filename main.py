from EFRD import EFRD_Protocol_v3_2, EFRD_AdvancedVisualizer
from numpy import linspace
from math import exp

# ==========================================================
# DATOS MACROECONÓMICOS DE ENTRADA
# ==========================================================
# Ya no necesitamos diccionarios de población ni gammas manuales.
# El sistema leerá a los contribuyentes desde 'outputs/base_final_efrd.db'

PIB_actual = 5000
gastos_operativos_estado = 0
path_db = "conexion/outputs/base_final_efrd.db"
# ==========================================================
# INICIALIZACIÓN DEL MOTOR (Conecta a SQLite)
# ==========================================================
print("Iniciando motor EFRD. Procesando base de datos catastral...")

motor = EFRD_Protocol_v3_2(
    PIB_Y=PIB_actual, 
    Gini=0.33, 
    Alpha=0.05,
    Sigma=1.5, 
    Limite_L=0.80, 
    G_op=gastos_operativos_estado, 
    db_path = path_db
)

# Nota: La auditoría de seguridad ahora se ejecuta y se imprime de 
# forma automática dentro del __init__ del motor, auditando al 100% 
# de la población guardada en la base de datos.

# ==========================================================
# SIMULADOR AISLADO (Para pruebas individuales)
# ==========================================================
print("\n" + "="*40)
print("--- SIMULADOR DE CÁLCULO INDIVIDUAL ---")
print("="*40)

def simular_caso_aislado(renta_bruta, phi_hogar, gamma_zona, motor_activo):
    """
    Simula cómo trataría el motor a un hogar específico usando 
    la fórmula asintótica continua del Modelo Sen.
    """
    k_hogar = motor_activo.k_base * gamma_zona * phi_hogar
    diferencial = renta_bruta - k_hogar
    
    if diferencial > 0:
        x = diferencial / k_hogar if k_hogar > 0 else 0
        tasa = motor_activo.L * (1 - exp(-motor_activo.sigma * abs(x)))
        cuota = diferencial * tasa
    else:
        # Si la renta no supera el k_hogar, la cuota es negativa (Recibe subsidio)
        cuota = diferencial 

    print(f"Renta Bruta: {renta_bruta:.2f}€")
    print(f"γ (Coste Zona): {gamma_zona} | φ (Composición): {phi_hogar}")
    print(f"Sueldo Hogar Protegido (k_hogar): {k_hogar:.2f}€")
    print("-" * 40)
    print(f"Cuota Final (C): {cuota:.2f}€ ({'RECIBE' if cuota < 0 else 'PAGA AL ESTADO'})")
    print(f"Dinero Neto Final: {(renta_bruta - cuota):.2f}€\n")

# Ejemplo: Familia numerosa en zona muy cara (ej. Madrid Centro)
# 2 adultos (1.0 + 0.5) + 4 hijos (4 * 0.3) = phi de 2.7
simular_caso_aislado(
    renta_bruta=22000, 
    phi_hogar=2.7, 
    gamma_zona=1.28, 
    motor_activo=motor
)

# Ejemplo: Soltero sin hijos en zona barata (ej. León)
# 1 adulto = phi de 1.0
simular_caso_aislado(
    renta_bruta=90000, 
    phi_hogar=1.0, 
    gamma_zona=0.87, 
    motor_activo=motor
)


# VISUALIZACIÓN AVANZADA / GRÄFICOS
"""
adv = EFRD_AdvancedVisualizer(motor)

rango_ingresos = linspace(0, 150000, 150)
rango_phis = linspace(1.0, 3.0, 30)


adv.comparar_sigmas(rango_ingresos, [0.3, 0.75, 1.5], 1, 3) 
adv.comparar_limite_L(rango_ingresos, [0.4, 0.6, 0.8]) 
adv.comparar_alpha(rango_ingresos, [0.3, 0.45, 0.6]) 
adv.mapa_calor(rango_ingresos, rango_phis)
"""
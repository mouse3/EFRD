from EFRD import EFRD_Protocol_v3_2, EFRD_AdvancedVisualizer, EFRD_AnalyticVisualizer
from traductores import get_pib_nominal_precios_corrientes, get_IPC_mas_reciente
from pruebita import procesar_simulacion_efrd

PIB_anyo, PIB_valor = get_pib_nominal_precios_corrientes()
IPC_anyo, IPC_valor = get_IPC_mas_reciente()
gastos_operativos_estado = 0
path_db = "conexion/outputs/Base_Datos_MACRO.db"
tabla = "Base_Datos_MACRO"

print(f"PIB más reciente (año {PIB_anyo}): {PIB_valor} €")
print(f"IPC más reciente (año {IPC_anyo}): {IPC_valor}")
print("Iniciando motor EFRD. Procesando base de datos catastral...")

motor = EFRD_Protocol_v3_2(
    PIB_Y=PIB_valor, 
    Gini=0.33, 
    Alpha=0.05,
    Sigma=1.5, 
    Limite_L=0.80,
    IPC_Pi=IPC_valor, 
    G_op=gastos_operativos_estado, 
    db_path=path_db,
    tabla_central=tabla
)

# 1. EJECUTAR SIMULACIÓN (Esto llena y procesa la BD)
procesar_simulacion_efrd(
    motor=motor,
    db_path=path_db,
    tabla_origen=tabla,
)

# 2. CONECTAR VISUALIZADOR
visualizador = EFRD_AnalyticVisualizer(motor)

# 3. LANZAR GRÁFICOS (Ahora leerán la tabla generada 'resultados_ciudadanos')
visualizador.graficar_curva_sostenibilidad()
visualizador.graficar_ingreso_bruto_vs_neto()
visualizador.graficar_tipo_impositivo_efectivo()
visualizador.graficar_mapa_calor_bienestar()
visualizador.graficar_distribucion_ingresos()
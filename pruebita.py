import sqlite3
import numpy as np
import pandas as pd

def procesar_simulacion_efrd(motor, db_path, tabla_origen="central", tabla_destino="resultados_ciudadanos"):
    """
    Lee los ciudadanos de la BD, aplica el modelo matemático EFRD anualizado
    y exporta los resultados mensuales solicitados a una nueva tabla.
    """
    # 1. Conectar a la base de datos y extraer la tabla central
    conn = sqlite3.connect(db_path)
    query = f"SELECT dni_nie_nif, renta_mensual, phi, gamma FROM {tabla_origen}"
    df = pd.read_sql_query(query, conn)
    
    resultados = []
    
    # 2. Iterar por cada ciudadano aplicando la lógica del motor
    for _, fila in df.iterrows():
        dni = fila['dni_nie_nif']
        renta_mensual = fila['renta_mensual']
        phi = fila['phi']
        gamma = fila['gamma']
        
        # Convertimos a anual para que coincida con los umbrales de k_base
        renta_anual = renta_mensual * 12
        
        # Lógica del motor EFRD extraída de tu _calcular_individual
        umbral_hogar = motor.k_base * gamma * phi
        diferencial = renta_anual - umbral_hogar
        
        if diferencial > 0:
            # Caso: Paga cuota (Impuesto)
            x = diferencial / (renta_anual * 0.1) if umbral_hogar <= 0 else diferencial / umbral_hogar
            tasa = motor.L * (1 - np.exp(-motor.sigma * abs(x)))
            impuesto_anual = diferencial * tasa
            neto_anual = renta_anual - impuesto_anual
            tipo_efectivo = (impuesto_anual / renta_anual) * 100
            
            # Mensualización de salidas
            cuota_mensual = impuesto_anual / 12
            neto_mensual = neto_anual / 12
            regimen = "Paga Cuota"
        else:
            # Caso: Recibe subsidio
            subsidio_anual = abs(diferencial)
            neto_anual = renta_anual + subsidio_anual
            tipo_efectivo = -(subsidio_anual / renta_anual) * 100 if renta_anual > 0 else -100
            
            # Mensualización de salidas
            cuota_mensual = subsidio_anual / 12  # Valor absoluto del beneficio
            neto_mensual = neto_anual / 12
            regimen = "Recibe Subsidio"
            
        # Almacenar la información solicitada
        resultados.append({
            "DNI_NIE_NIF": dni,
            "Neto_Mensual": round(neto_mensual, 2),
            "Cuota_Impuesto_Mensual": round(cuota_mensual, 2),
            "Tipo_Efectivo_Porcentaje": round(tipo_efectivo, 2),
            "Condicion_Sistema": regimen
        })
        
    # 3. Convertir a DataFrame y guardar los resultados en la BD
    df_salida = pd.DataFrame(resultados)
    df_salida.to_sql(tabla_destino, conn, if_exists='replace', index=False)
    
    conn.close()
    print(f"🎉 ¡Procesamiento completado con éxito!")
    print(f"Se han analizado {len(df_salida)} registros y se han guardado en la tabla '{tabla_destino}'.")
    
    # 1. Creamos la conexión con el archivo .db (pon el nombre que quieras)
    # Si el archivo no existe, se creará automáticamente en el directorio actual
    conexion = sqlite3.connect("efrd_simulacion.db")

    # 2. Guardamos el DataFrame en la base de datos
    df_salida.to_sql(
        name="resultados_ciudadanos",  # Nombre que tendrá la tabla dentro de la BD
        con=conexion,                  # La conexión que acabamos de abrir
        if_exists="replace",           # Opciones: 'replace' (sobrescribe), 'append' (añade filas) o 'fail'
        index=False                    # Evita que el índice de pandas se guarde como una columna extra
    )

    # 3. Cerramos la conexión para asegurar que los datos se escriban en el disco
    conexion.close()

    print("DONE!")


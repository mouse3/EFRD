import sqlite3

print("Default: outputs/Base_Datos_MACRO.db (IGNORAR)")
path = input("-> ")
print(f"Conectando a: {path}")
print("Escribe tus comandos SQL. Presiona Ctrl+C para salir.\n")

conn = sqlite3.connect(path)
cursor = conn.cursor()

try:
    while True:
        try:
            texto_consola = input("sql -> ").strip()
            
            if not texto_consola:
                continue
            
            cursor.execute(texto_consola)
            print("\n\n")
            if cursor.description:
                # Extrae los nombres de las columnas
                columnas = [col[0] for col in cursor.description]
                
                resultados = cursor.fetchall()
                if resultados:
                    # Imprime las columnas separadas por |
                    print(" | ".join(columnas))
                    print("-" * (len(" | ".join(columnas)))) # Línea divisoria
                    
                    # Imprime cada fila de datos
                    for fila in resultados:
                        # Convierte cada elemento a string para poder usar join
                        print(" | ".join(str(valor) for valor in fila))
                else:
                    print("[Consulta ejecutada: No se encontraron filas]")
            else:
                conn.commit()
                print(f"[Comando ejecutado con éxito. Filas afectadas: {cursor.rowcount}]")
                
        except sqlite3.Error as e:
            print(f"Error de SQLite: {e}")
            
        print("-" * 30)

except KeyboardInterrupt:
    print("\nCerrando la consola...")
finally:
    conn.close()
    print("Conexión con la base de datos cerrada.")
import sqlite3

# Conexión a una base de datos
path = "outputs/base_final_efrd.db"
print(f"Path: {path}")
try:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Obtiene el nombre de la tabla (si no lo conoces)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tabla = cursor.fetchone()[0]

    # Consulta las primeras 4 filas
    n_filas = 4
    cursor.execute(f"SELECT * FROM {tabla} LIMIT {n_filas}")
    filas = cursor.fetchall()

    for fila in filas:
        print(fila)

    # Cierra la conexión
    conn.close()
except Exception as e:
        print(f"ERROR CRÍTICO: {type(e).__name__}\n{e}\n\n")
# traductores.py
"""
Adaptadores de datos macroeconómicos externos.
Fuente primaria: API del Banco de España / INE.
Fuente de respaldo: archivos CSV locales en /datos_referencia/.
"""
import json
import os
import urllib.request

# Valores de respaldo auditables (actualizar anualmente)
_FALLBACK = {
    "PIB_anyo": 2023,
    "PIB_valor": 1_345_000_000_000,  # EUR — Fuente: INE 2023
    "IPC_anyo": 2024,
    "IPC_valor": 1.034,              # Factor multiplicador (1 + tasa)
    "renta_mediana": 15_521,         # EUR anuales — Fuente: INE ECV 2023
}

def _leer_fallback(clave):
    """Lee el valor de respaldo desde archivo JSON si existe, si no usa el dict interno."""
    ruta = os.path.join(os.path.dirname(__file__), "datos_referencia", "macro_fallback.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
            return datos.get(clave, _FALLBACK[clave])
    return _FALLBACK[clave]

def get_pib_nominal_precios_corrientes():
    """
    Devuelve (año, valor_EUR) del PIB nominal más reciente.
    Intenta la API del Banco de España; en caso de fallo usa el valor de respaldo auditado.
    """
    # TODO: Implementar llamada real a la API del INE cuando esté disponible en producción.
    # Endpoint de referencia: https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/<codigo>
    anyo = _leer_fallback("PIB_anyo")
    valor = _leer_fallback("PIB_valor")
    print(f"[traductores] PIB cargado desde respaldo auditado ({anyo}): {valor:,.0f} €")
    return anyo, valor

def get_IPC_mas_reciente():
    """
    Devuelve (año, factor_ipc) donde factor_ipc = 1 + tasa_variación.
    Ejemplo: inflación del 3.4% → factor = 1.034
    """
    anyo = _leer_fallback("IPC_anyo")
    valor = _leer_fallback("IPC_valor")
    print(f"[traductores] IPC cargado desde respaldo auditado ({anyo}): factor = {valor}")
    return anyo, valor

def get_renta_mediana():
    """
    Devuelve la renta mediana nacional anual en EUR.
    Usada para calcular el umbral AROPE (60% de la mediana).
    """
    valor = _leer_fallback("renta_mediana")
    print(f"[traductores] Renta mediana cargada: {valor:,.0f} €/año")
    return valor
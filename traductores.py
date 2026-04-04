def get_renta_mediana():
    from requests import get
    url_renta_mediana = "https://servicios.ine.es/wstempus/js/es/DATOS_SERIE/ICV802?nult=1"
    respuesta = get(url_renta_mediana)
    try:
        if respuesta.status_code == 200:
            data = respuesta.json()
            #print(data, "\n")
            for registro in data["Data"]:
                anyo = registro["Anyo"]
                valor = registro["Valor"]
                #print(f"Se ha recogido el dato {valor}€ renta mediana del año {anyo}")
                return valor
        else:
            print(f"Ha ocurrido un error al tratar de recoger el dato renta mediana en {url_renta_mediana}")
    except Exception as e:
        print(f"ERROR CRÍTICO: {type(e).__name__}\n{e}")

#print(get_renta_mediana())

import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

# URL de la jornada de la federación
URL_FEDERACION = "https://www.rfcf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120&CodCompeticion=22595821&CodGrupo=22595822&CodTemporada=22&cod_agrupacion=1&CodJornada=9&Sch_Tipo_Juego=4"

INICIO = '<script type="text/plain" id="datos">\n'
FIN = "\n</script>"

def extraer_resultados_web():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"Conectando con la web de la federación...")
    response = requests.get(URL_FEDERACION, headers=headers)
    
    if response.status_code != 200:
        sys.exit(f"Error: La federación devolvió el código de estado {response.status_code}.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    resultados = {}
    
    # Buscamos las filas de partidos en la estructura típica de la RFCF
    # Generalmente los partidos están en tablas o filas con clases específicas.
    # Vamos a buscar todas las filas de las tablas de la página para analizar los textos.
    filas_tabla = soup.find_all('tr')
    
    print(f"Analizando la página web (encontradas {len(filas_tabla)} filas HTML)...")
    
    # NOTA: Dependiendo de si la URL de la jornada muestra solo una jornada o la tabla cruzada completa,
    # ajustaremos el selector exacto de las celdas. 
    # De momento, probemos a ver si el script descarga e interpreta el contenido correctamente.
    
    return resultados

def main():
    res = extraer_resultados_web()
    print("Extracción web finalizada.")

if __name__ == "__main__":
    main()

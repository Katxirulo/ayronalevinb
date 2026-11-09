import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

# URL de la jornada de la federación que usas habitualmente
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
        sys.exit(f"Error: La federación devolvió el código de estado {response.status_code}. Es posible que bloquee el acceso automático.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # AQUÍ ES DONDE DEBEMOS ADAPTAR LA BÚSQUEDA SEGÚN EL HTML DE LA FEDERACIÓN
    # Por ejemplo, buscar las filas de la tabla de partidos:
    resultados = {}
    
    # NOTA: Como la estructura HTML exacta de la RFCF puede cambiar, 
    # este bloque se personalizará una vez comprobemos si nos deja pasar el "Access Denied".
    
    return resultados

def main():
    res = extraer_resultados_web()
    print("Prueba de conexión realizada con éxito.")

if __name__ == "__main__":
    main()

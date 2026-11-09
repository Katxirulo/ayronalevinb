import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

URL_TABLA_CRUZADA = "https://www.rfcf.es/pnfg/NPcd/NFG_VisTablaCruzada?cod_primaria=1000120&CodGrupo=22595822"

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("Conectando con la tabla cruzada de la federación...")
    response = requests.get(URL_TABLA_CRUZADA, headers=headers)
    
    if response.status_code != 200:
        sys.exit(f"Error: La federación devolvió el estado {response.status_code}.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Buscamos cuántas tablas HTML hay en la página
    tablas = soup.find_all('table')
    print(f"Número de tablas HTML encontradas en la página: {len(tablas)}")
    
    # Imprimimos una muestra del texto de la página para ver qué nos devuelve
    texto_muestra = soup.get_text()[:500].replace('\n', ' ')
    print(f"Muestra de texto de la web: {texto_muestra}...")
    
    # Buscamos si aparece alguna palabra clave de equipos
    if "AYRON" in texto_muestra.upper() or "BEZANA" in texto_muestra.upper():
        print("¡Éxito! Los nombres de los equipos aparecen en el texto descargado.")
    else:
        print("Aviso: No veo los nombres de los equipos en la muestra. Es posible que la página cargue los datos por JavaScript.")

if __name__ == "__main__":
    main()

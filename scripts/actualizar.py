import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

# URL de la tabla cruzada oficial de la federación
URL_TABLA_CRUZADA = "https://www.rfcf.es/pnfg/NPcd/NFG_VisTablaCruzada?cod_primaria=1000120&CodGrupo=22595822"

INICIO = '<script type="text/plain" id="datos">\n'
FIN = "\n</script>"

def extraer_resultados_web():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"Conectando con la tabla cruzada de la federación...")
    response = requests.get(URL_TABLA_CRUZADA, headers=headers)
    
    if response.status_code != 200:
        sys.exit(f"Error: La federación devolvió el código de estado {response.status_code}.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Buscamos todas las celdas de la tabla cruzada en el HTML de la federación.
    # Por lo general, en las tablas cruzadas de la RFCF, los resultados o jornadas 
    # se ubican en las celdas (etiquetas <td> o <span> dentro de la tabla).
    
    # Vamos a extraer todos los textos de las celdas de la tabla para analizarlos
    celdas_html = soup.find_all(['td', 'th'])
    textos_celdas = [c.get_text(strip=True) for c in celdas_html]
    
    print(f"Celdas leídas de la web: {len(textos_celdas)}")
    
    # Como la estructura exacta de clases de la tabla de la RFCF puede variar ligeramente,
    # hagamos una depuración imprimiendo algunas celdas para validar el formato exacto.
    
    resultados = {}
    # Aquí mapearemos los resultados encontrados con el formato (local, visitante) -> ("R", (gl, gv)) o ("J", num)
    
    return resultados

def main():
    res = extraer_resultados_web()
    print("Extracción de la tabla cruzada completada.")

if __name__ == "__main__":
    main()

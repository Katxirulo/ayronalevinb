import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

URL_TABLA_CRUZADA = "https://www.rfcf.es/pnfg/NPcd/NFG_VisTablaCruzada?cod_primaria=1000120&CodGrupo=22595822"

# Mapeo exacto de cómo aparecen los nombres en la web de la federación a cómo los usas en la web
EQUIPOS = {
    "SAN AGUSTIN": "San Agustín", "AYRON": "Ayron", "AMISTAD": "Amistad Sniace",
    "BEZANA": "Bezana", "CALASANZ": "Calasanz", "ESCLAVAS": "Esclavas",
    "MARINA": "Marina Sport", "MILINDE": "Milinde Reocín", "NAVAL": "Naval",
    "TROPEZON": "Tropezón", "VALLE": "Valle Lebaniego", "VIMENOR": "Vimenor",
    "POLANCO": "Polanco", "GIMNASTICA": "Gimnástica", "SAN MARTIN": "San Martín",
    "TEXTIL": "Textil Escudo",
}

INICIO = '<script type="text/plain" id="datos">\n'
FIN = "\n</script>"

def extraer_resultados_web():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("Conectando con la tabla cruzada de la federación...")
    response = requests.get(URL_TABLA_CRUZADA, headers=headers)
    
    if response.status_code != 200:
        sys.exit(f"Error: La federación devolvió el estado {response.status_code}.")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Buscamos todas las celdas de las tablas de la página
    celdas = [c.get_text(strip=True) for c in soup.find_all(['td', 'th'])]
    
    texto_completo = "\n".join(celdas)
    posiciones = {}
    for clave in EQUIPOS:
        m = re.search(r"\b" + clave + r"\b", texto_completo)
        if not m:
            sys.exit(f"No encuentro el equipo {clave} en la web de la federación.")
        posiciones[clave] = m.start()
        
    orden = [EQUIPOS[k] for k in sorted(posiciones, key=posiciones.get)]
    
    # Extraemos todos los patrones de resultados (ej: "3-3", "1-0") o jornadas pendientes (ej: "J9") de todo el texto de la página
    celdas_filtradas = re.findall(r"\bJ\s?\d{1,2}\b|\b\d{1,2}\s?-\s?\d{1,2}\b", soup.text)
    
    n = len(orden)
    resultados = {}
    k = 0
    
    # Recorremos la matriz de equipos (local x visitante)
    for local in orden:
        for visitante in orden:
            if local == visitante:
                continue
            if k >= len(celdas_filtradas):
                break
            c = celdas_filtradas[k].replace(" ", "")
            k += 1
            if c.startswith("J"):
                resultados[(local, visitante)] = ("J", int(c[1:]))
            else:
                partes = c.split("-")
                if len(partes) == 2 and partes[0].isdigit() and partes[1].isdigit():
                    resultados[(local, visitante)] = ("R", (int(partes[0]), int(partes[1])))
                else:
                    resultados[(local, visitante)] = ("J", 0)
                    
    return resultados

def main():
    res = extraer_resultados_web()
    print(f"Extraídos {len(res)} cruces de la web de la federación.")

    html = HTML.read_text(encoding="utf-8")
    i = html.index(INICIO) + len(INICIO)
    j = html.index(FIN, i)
    lineas = html[i:j].strip().splitlines()
    cabecera, filas = lineas[0], lineas[1:]

    nuevas, cambios = [], 0
    for fila in filas:
        jornada, local, visitante, gl, gv = fila.split(",")
        dato = res.get((local, visitante))
        if dato is None:
            nuevas.append(fila)
            continue
            
        if dato[0] == "R":
            ngl, ngv = map(str, dato[1])
        else:
            ngl, ngv = "", ""
            
        if (ngl, ngv) != (gl, gv):
            cambios += 1
            print(f"  J{jornada} {local} - {visitante}: {gl or '·'}-{gv or '·'} -> {ngl or '·'}-{ngv or '·'}")
        nuevas.append(",".join([jornada, local, visitante, ngl, ngv]))

    HTML.write_text(html[:i] + "\n".join([cabecera] + nuevas) + html[j:], encoding="utf-8")
    print(f"Listo: {cambios} partido(s) actualizado(s) automáticamente desde la web.")

if __name__ == "__main__":
    main()

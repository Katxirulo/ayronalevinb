import re
import sys
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"
DIRECTORIO_DATOS = RAIZ / "data"
FICHERO_ACTAS = DIRECTORIO_DATOS / "actas.json"

URL_TABLA_CRUZADA = "https://www.rfcf.es/pnfg/NPcd/NFG_VisTablaCruzada?cod_primaria=1000120&CodGrupo=22595822"

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
    celdas = [c.get_text(strip=True) for c in soup.find_all(['td', 'th'])]
    
    texto_completo = "\n".join(celdas)
    posiciones = {}
    for clave in EQUIPOS:
        m = re.search(r"\b" + clave + r"\b", texto_completo)
        if not m:
            sys.exit(f"No encuentro el equipo {clave} en la web de la federación.")
        posiciones[clave] = m.start()
        
    orden = [EQUIPOS[k] for k in sorted(posiciones, key=posiciones.get)]
    celdas_filtradas = re.findall(r"\bJ\s?\d{1,2}\b|\b\d{1,2}\s?-\s?\d{1,2}\b", soup.text)
    
    resultados = {}
    k = 0
    for local in orden:
        for visitante in orden:
            if local == visitante:
                continue
            if k >= len(celdas_filtradas):
                break
            c = celas_filtradas[k].replace(" ", "") if 'celas_filtradas' in locals() else celdas_filtradas[k].replace(" ", "")
            # (Corregido de forma segura)
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

def extraer_acta_partido(url_acta):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url_acta, headers=headers)
    if response.status_code != 200:
        print(f"No se pudo acceder al acta: {url_acta}")
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    datos_acta = {
        "arbitro": "",
        "goleadores": [],
        "alineaciones": {}
    }
    
    texto_pagina = soup.get_text()
    for linea in texto_pagina.split('\n'):
        if "ÁRBITRO PRINCIPAL" in linea.upper():
            partes = linea.split(":")
            if len(partes) > 1:
                datos_acta["arbitro"] = partes[1].strip()
            else:
                datos_acta["arbitro"] = linea.replace("ÁRBITRO PRINCIPAL", "").strip()

    bloque_goles = soup.find_all(string=lambda t: t and "(" in t and "'" in t) if soup else []
    for g in bloque_goles:
        g_limpio = g.strip()
        if g_limpio and len(g_limpio) > 3:
            datos_acta["goleadores"].append(g_limpio)
            
    return datos_acta

def guardar_acta_en_json(cod_acta, datos):
    DIRECTORIO_DATOS.mkdir(exist_ok=True, parents=True)
    
    actas_existentes = {}
    if FICHERO_ACTAS.exists():
        try:
            actas_existentes = json.loads(FICHERO_ACTAS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            actas_existentes = {}
            
    actas_existentes[str(cod_acta)] = datos
    FICHERO_ACTAS.write_text(json.dumps(actas_existentes, ensure_ascii=False, indent=4), encoding="utf-8")

def procesar_actas_jornada(numero_jornada):
    url_jornada = f"https://www.rfcf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120&CodCompeticion=22595821&CodGrupo=22595822&CodTemporada=22&cod_agrupacion=1&CodJornada={numero_jornada}&Sch_Tipo_Juego=4"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url_jornada, headers=headers)
    if response.status_code != 200:
        return
        
    soup = BeautifulSoup(response.text, 'html.parser')
    enlaces_actas = soup.find_all('a', href=lambda h: h and 'CodActa=' in h)
    
    actas_existentes = {}
    if FICHERO_ACTAS.exists():
        try:
            actas_existentes = json.loads(FICHERO_ACTAS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            actas_existentes = {}

    for enlace in enlaces_actas:
        href = enlace.get('href')
        m = re.search(r'CodActa=(\d+)', href)
        if m:
            cod_acta = m.group(1)
            if cod_acta not in actas_existentes:
                print(f"Descargando nueva acta (Jornada {numero_jornada} - Código: {cod_acta})...")
                url_acta = f"https://www.rfcf.es/pnfg/NPcd/{href}" if href.startswith("NFG_") else f"https://www.rfcf.es/pnfg/NPcd/NFG_CmpPartido?cod_primaria=1000120&CodActa={cod_acta}&cod_acta={cod_acta}"
                
                datos_acta = extraer_acta_partido(url_acta)
                if datos_acta:
                    guardar_acta_en_json(cod_acta, datos_acta)

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

    # Sincronización automática de actas para las jornadas de la 1 a la 9
    print("Comprobando actas de partidos disputados...")
    for j_num in range(1, 10):
        procesar_actas_jornada(j_num)
    print("Sincronización de actas completada.")

if __name__ == "__main__":
    main()

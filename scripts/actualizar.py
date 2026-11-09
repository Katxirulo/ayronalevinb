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
        "alineaciones_raw": []
    }
    
    # 1. Extracción y limpieza del Árbitro
    for elem in soup.find_all(text=True):
        if "ÁRBITRO" in elem.upper():
            padre = elem.parent
            texto_padre = padre.get_text(strip=True)
            if ":" in texto_padre:
                partes = texto_padre.split(":")
                if len(partes) > 1 and len(partes[-1].strip()) > 3:
                    # Limpiamos la palabra clave para dejar solo el nombre
                    sucia = partes[-1].strip()
                    limpia = re.sub(r'ARBITRO PRINCIPAL', '', sucia, flags=re.IGNORECASE).strip()
                    datos_acta["arbitro"] = limpia
                    break
            siguiente = padre.find_next_sibling()
            if siguiente and len(siguiente.get_text(strip=True)) > 3:
                sucia = siguiente.get_text(strip=True)
                limpia = re.sub(r'ARBITRO PRINCIPAL', '', sucia, flags=re.IGNORECASE).strip()
                datos_acta["arbitro"] = limpia
                break

    # 2. Extracción ultra-limpia y sin duplicados de Goles
    goles_encontrados = []
    for elem in soup.find_all(['div', 'span', 'td', 'li']):
        texto = elem.get_text(separator=" ", strip=True)
        # Buscamos patrones que tengan el minuto y además contengan letras (el nombre del jugador)
        if re.search(r"\(\d{1,2}'\)", texto) and any(c.isalpha() for c in texto):
            texto_limpio = re.sub(r'\s+', ' ', texto).strip()
            # Filtramos que sea una línea de goles real (evitando textos largos o duplicados cortos)
            if len(texto_limpio) < 50 and "Goles" not in texto_limpio and "Gol" not in texto_limpio:
                if texto_limpio not in goles_encontrados:
                    goles_encontrados.append(texto_limpio)
                    
    datos_acta["goleadores"] = goles_encontrados

    # 3. Extracción de Alineaciones (Titulares y Suplentes)
    jugadores_actuales = []
    filas = soup.find_all(['tr', 'li', 'div'])
    for fila in filas:
        texto = fila.get_text(separator=" ", strip=True)
        match_jugador = re.match(r"^(\d{1,2})\s+([A-ZÁÉÍÓÚÑ\s,]+)$", texto)
        if match_jugador:
            dorsal, nombre = match_jugador.groups()
            jugador_dict = {"dorsal": dorsal, "nombre": nombre.strip()}
            if jugador_dict not in jugadores_actuales:
                jugadores_actuales.append(jugador_dict)

    datos_acta["alineaciones_raw"] = jugadores_actuales

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

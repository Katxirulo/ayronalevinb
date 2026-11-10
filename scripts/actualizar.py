import re
import sys
import json
import time
import unicodedata
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

SESION = requests.Session()
SESION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
})
URL_ACTA = "https://www.rfcf.es/pnfg/NPcd/NFG_CmpPartido?cod_primaria=1000120&CodActa={cod}&cod_acta={cod}"
URL_JORNADA = ("https://www.rfcf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120&CodCompeticion=22595821"
               "&CodGrupo=22595822&CodTemporada=22&cod_agrupacion=1&CodJornada={j}&Sch_Tipo_Juego=4")
VERSION_ACTA = 2      # sube este número si cambias el formato y quieres volver a descargar todo
PAUSA = 4             # segundos entre peticiones a la federación
PAUSA_BLOQUEO = 90    # espera antes de reintentar si la web deja de responder bien


class Bloqueado(Exception):
    pass


def diagnostico(r, motivo):
    """Imprime en el log qué ha devuelto realmente la web."""
    soup = BeautifulSoup(r.text, "html.parser")
    titulo = soup.title.get_text(strip=True) if soup.title else "(sin título)"
    texto = re.sub(r"\s+", " ", soup.get_text(" "))[:300]
    print(f"    DIAGNÓSTICO ({motivo}): HTTP {r.status_code} · {len(r.text)} bytes · título: {titulo}")
    print(f"    Texto: {texto}")


def descargar(url, es_valida, motivo):
    """GET con pausa; si la página no es la esperada espera y reintenta una vez."""
    for intento in (1, 2):
        time.sleep(PAUSA)
        try:
            r = SESION.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"    Error de red: {e}")
            r = None
        if r is not None and r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            if es_valida(soup):
                return soup
        if r is not None:
            diagnostico(r, motivo)
        if intento == 1:
            print(f"    Reintento en {PAUSA_BLOQUEO} s...")
            time.sleep(PAUSA_BLOQUEO)
    raise Bloqueado(motivo)


def extraer_resultados_web():
    print("Conectando con la tabla cruzada de la federación...")

    def filas_equipos(soup):
        filas = []
        for tr in soup.find_all("tr"):
            celdas = tr.find_all(["td", "th"], recursive=False)
            if len(celdas) == len(EQUIPOS) + 1:
                eq = nombre_equipo(celdas[0].get_text(" ", strip=True))
                # la página repite la tabla (versión imprimible): nos quedamos con la primera
                if eq in EQUIPOS.values() and eq not in [f[0] for f in filas]:
                    filas.append((eq, celdas[1:]))
        return filas

    try:
        soup = descargar(URL_TABLA_CRUZADA, lambda s: len(filas_equipos(s)) == len(EQUIPOS), "tabla cruzada")
    except Bloqueado:
        print("  No se ha podido leer la tabla cruzada; los resultados no se tocan en esta ejecución.")
        return {}

    filas = filas_equipos(soup)
    orden = [eq for eq, _ in filas]  # las columnas siguen el mismo orden que las filas
    resultados = {}
    for local, celdas in filas:
        for visitante, celda in zip(orden, celdas):
            if local == visitante:
                continue
            t = celda.get_text(" ", strip=True)
            m = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", t)
            if m:
                resultados[(local, visitante)] = ("R", (int(m.group(1)), int(m.group(2))))
            elif re.search(r"J\s*\d{1,2}", t):
                resultados[(local, visitante)] = ("J", 0)
    return resultados


def sin_tildes(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()


def nombre_equipo(texto_web):
    """'AYRON CLUB B' -> 'Ayron', 'S.D. SAN MARTIN DE LA ARENA A' -> 'San Martín'."""
    t = sin_tildes(texto_web)
    for clave, nombre in EQUIPOS.items():
        if re.search(r"\b" + clave + r"\b", t):
            return nombre
    return texto_web.strip()


def limpio(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def extraer_acta_partido(cod_acta):
    soup = descargar(URL_ACTA.format(cod=cod_acta),
                     lambda sp: sp.select_one(".font_widgetL") is not None,
                     f"acta {cod_acta}")
    main = soup.find("main") or soup

    loc = main.select_one(".font_widgetL")
    vis = main.select_one(".font_widgetV")
    if not loc or not vis:
        print(f"  Acta {cod_acta}: no encuentro los equipos, se omite.")
        return None
    local, visitante = nombre_equipo(loc.get_text()), nombre_equipo(vis.get_text())
    m = re.search(r"Jornada\s+(\d+)", main.get_text(" "))

    acta = {
        "version": VERSION_ACTA,
        "jornada": int(m.group(1)) if m else None,
        "local": local,
        "visitante": visitante,
        "arbitro": "",
        "equipos": {local: {"titulares": [], "suplentes": []},
                    visitante: {"titulares": [], "suplentes": []}},
        "goles": [],
    }

    for bloque in main.select("div.dashboard-stat"):
        titulo = limpio(bloque.select_one(".number").get_text() if bloque.select_one(".number") else "")

        # Árbitro
        if titulo.startswith("Árbitro") or titulo.startswith("Arbitro"):
            h5 = bloque.find("h5")
            if h5:
                acta["arbitro"] = limpio(re.sub(r"ARBITRO PRINCIPAL", "", h5.get_text(" "), flags=re.I))

        # Alineaciones: cada equipo tiene su bloque con H5 Titulares / Suplentes + tabla
        elif bloque.select_one(".visual i.fa-users"):
            equipo = nombre_equipo(titulo)
            datos = acta["equipos"].setdefault(equipo, {"titulares": [], "suplentes": []})
            for h5 in bloque.find_all("h5"):
                tipo = limpio(h5.get_text()).lower()
                if tipo not in ("titulares", "suplentes"):
                    continue
                tabla = h5.find_next_sibling("table")
                if not tabla:
                    continue
                for tr in tabla.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) >= 2:
                        datos[tipo].append({"dorsal": limpio(tds[0].get_text()),
                                            "nombre": limpio(tds[1].get_text())})

    # Goles (después de las alineaciones para poder asignar el equipo del goleador)
    jugadores = {e: {j["nombre"] for j in d["titulares"] + d["suplentes"]}
                 for e, d in acta["equipos"].items()}
    bloque_goles = next((b for b in main.select("div.dashboard-stat")
                         if limpio(b.select_one(".number").get_text() if b.select_one(".number") else "") == "Goles"), None)
    if bloque_goles:
        for tr in bloque_goles.select("table tr"):
            celda = tr.select_one("td.font_responsive")
            icono = tr.select_one("a.lgol, a[title]")
            if not celda or not icono:
                continue  # fila de la leyenda
            minuto = celda.select_one(".font-blue")
            min_txt = re.sub(r"\D", "", minuto.get_text()) if minuto else ""
            if minuto:
                minuto.extract()
            jugador = limpio(celda.get_text())
            titulo_gol = sin_tildes(icono.get("title", ""))
            estilo = (icono.find("i") or {}).get("style", "") if icono.find("i") else ""
            if "PROPIA" in titulo_gol or "red" in estilo:
                tipo = "propia"
            elif "PENALTI" in titulo_gol:
                tipo = "penalti"
            else:
                tipo = "normal"
            del_equipo = next((e for e, js in jugadores.items() if jugador in js), None)
            if tipo == "propia" and del_equipo:
                # el gol en propia puerta cuenta para el rival
                del_equipo = visitante if del_equipo == local else local
            acta["goles"].append({"minuto": int(min_txt) if min_txt else None, "jugador": jugador,
                                  "equipo": del_equipo, "tipo": tipo})
    return acta


def cargar_actas():
    if FICHERO_ACTAS.exists():
        try:
            return json.loads(FICHERO_ACTAS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def guardar_actas(actas):
    DIRECTORIO_DATOS.mkdir(exist_ok=True, parents=True)
    FICHERO_ACTAS.write_text(json.dumps(actas, ensure_ascii=False, indent=2), encoding="utf-8")


def actas_de_jornada(numero_jornada):
    soup = descargar(URL_JORNADA.format(j=numero_jornada),
                     lambda sp: re.search(r"Jornada\s+\d+", sp.get_text(" ")) is not None,
                     f"jornada {numero_jornada}")
    m = re.search(r"Jornada\s+(\d+)", soup.get_text(" "))
    if m and int(m.group(1)) != numero_jornada:
        print(f"  AVISO: pedí la jornada {numero_jornada} y la web devolvió la {m.group(1)}")
    codigos = []
    for a in soup.find_all("a", href=re.compile(r"CodActa=\d+", re.I)):
        cod = re.search(r"CodActa=(\d+)", a["href"], re.I).group(1)
        if cod not in codigos:
            codigos.append(cod)
    return codigos


def acta_completa(acta):
    return bool(acta and acta.get("version") == VERSION_ACTA and acta.get("equipos")
                and all(d["titulares"] for d in acta["equipos"].values()))


def sincronizar_actas(jornadas):
    actas = cargar_actas()
    nuevas = 0
    try:
        for j in jornadas:
            codigos = actas_de_jornada(j)
            pendientes = [c for c in codigos if not acta_completa(actas.get(c))]
            print(f"Jornada {j}: {len(codigos)} actas, {len(pendientes)} pendientes")
            for cod in pendientes:
                datos = extraer_acta_partido(cod)
                if datos:
                    actas[cod] = datos
                    nuevas += 1
                    guardar_actas(actas)  # se guarda acta a acta: si la web nos corta, no se pierde nada
                    n_jug = sum(len(d["titulares"]) + len(d["suplentes"]) for d in datos["equipos"].values())
                    print(f"  {cod}: {datos['local']} - {datos['visitante']} · {n_jug} jugadores · {len(datos['goles'])} goles")
    except Bloqueado as e:
        print(f"La federación ha dejado de responder bien ({e}). Se sigue en la próxima ejecución.")
    guardar_actas(actas)
    completas = sum(1 for a in actas.values() if acta_completa(a))
    print(f"Actas nuevas en esta ejecución: {nuevas}. Completas en el fichero: {completas}.")


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

    # Sincronización de actas: solo jornadas con algún resultado
    jugadas = sorted({int(f.split(",")[0]) for f in nuevas if f.split(",")[3] != ""})
    print(f"Comprobando actas de las jornadas {jugadas}...")
    sincronizar_actas(jugadas)

if __name__ == "__main__":
    main()

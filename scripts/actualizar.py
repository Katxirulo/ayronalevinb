import re
import sys
import json
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"
DIRECTORIO_DATOS = RAIZ / "data"
FICHERO_ACTAS = DIRECTORIO_DATOS / "actas.json"
FICHERO_CALENDARIO = DIRECTORIO_DATOS / "calendario.json"

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
PAUSA = 8             # segundos entre peticiones a la federación (si se piden muchas seguidas, corta)
ESPERAS_BLOQUEO = [45, 120]  # esperas antes de cada reintento si la web responde vacío o raro
MADRID = ZoneInfo("Europe/Madrid")
DURACION_PARTIDO = timedelta(minutes=80)  # tras la hora de inicio, se da el partido por terminado
ACTA_SEGURA = timedelta(minutes=150)      # si no se ve el visto bueno de la federación, se espera esto


# html.parser no cierra bien celdas en HTML mal formado; lxml sí. Se prueban los dos.
ANALIZADORES = ["html.parser"]
try:
    import lxml  # noqa: F401
    ANALIZADORES.append("lxml")
except ImportError:
    pass

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
    """GET con pausa. Si la federación responde vacío (corta por exceso de peticiones) o con una
    página inesperada, espera y reintenta (hasta 3 intentos en total)."""
    for intento in range(len(ESPERAS_BLOQUEO) + 1):
        time.sleep(PAUSA)
        try:
            r = SESION.get(url, timeout=30)
        except requests.RequestException as e:
            print(f"    Error de red: {e}")
            r = None
        if r is not None and r.status_code == 200 and r.text.strip():
            for analizador in ANALIZADORES:
                soup = BeautifulSoup(r.text, analizador)
                if es_valida(soup):
                    if intento:
                        print(f"    ({motivo}: correcta al intento {intento + 1})")
                    return soup
        if r is not None:
            diagnostico(r, motivo)
        if intento < len(ESPERAS_BLOQUEO):
            print(f"    Reintento en {ESPERAS_BLOQUEO[intento]} s...")
            time.sleep(ESPERAS_BLOQUEO[intento])
    raise Bloqueado(motivo)


def extraer_resultados_web():
    print("Conectando con la tabla cruzada de la federación...")

    def filas_equipos(soup):
        n = len(EQUIPOS)
        filas = []
        for tr in soup.find_all("tr"):
            celdas = tr.find_all(["td", "th"], recursive=False)
            if not (n + 1 <= len(celdas) <= n + 3):
                continue
            # el nombre puede ir en la 1ª celda o tras una columna de escudo
            cab = " ".join(c.get_text(" ", strip=True) for c in celdas[:len(celdas) - n])
            eq = nombre_equipo(cab)
            # la página repite la tabla (versión imprimible): nos quedamos con la primera
            if eq in EQUIPOS.values() and eq not in [f[0] for f in filas]:
                filas.append((eq, celdas[len(celdas) - n:]))
        return filas

    def resumen_filas(soup):
        from collections import Counter
        c = Counter(len(tr.find_all(["td", "th"], recursive=False)) for tr in soup.find_all("tr"))
        return ", ".join(f"{k} celdas x{v}" for k, v in sorted(c.items()) if k >= 10) or "ninguna fila ancha"

    try:
        soup = descargar(URL_TABLA_CRUZADA, lambda s: len(filas_equipos(s)) == len(EQUIPOS), "tabla cruzada")
    except Bloqueado:
        try:
            r = SESION.get(URL_TABLA_CRUZADA, timeout=30)
            for a in ANALIZADORES:
                sp = BeautifulSoup(r.text, a)
                print(f"    [{a}] filas de equipo reconocidas: {len(filas_equipos(sp))} de {len(EQUIPOS)} · filas: {resumen_filas(sp)}")
        except Exception as e:
            print(f"    (sin diagnóstico extra: {e})")
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
    # Marcador de la cabecera: el bloque más pequeño que contiene a los dos equipos
    marcador = None
    for anc in loc.parents:
        if vis in anc.descendants:
            txt = RE_FECHA.sub(" ", re.sub(r"\d{4}-\d{4}", " ", anc.get_text(" ")))
            mm = re.search(r"(?<![\d(])(\d{1,2})\s*-\s*(\d{1,2})(?![\d'])", txt)
            if mm:
                marcador = [int(mm.group(1)), int(mm.group(2))]
            break

    acta = {
        "version": VERSION_ACTA,
        "jornada": int(m.group(1)) if m else None,
        "local": local,
        "visitante": visitante,
        "arbitro": "",
        "equipos": {local: {"titulares": [], "suplentes": []},
                    visitante: {"titulares": [], "suplentes": []}},
        "goles": [],
        "marcador": marcador,
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


def resultado_desde_acta(acta):
    """[goles local, goles visitante]: el marcador del acta o, si no lo trae, los goles contados."""
    if acta.get("marcador"):
        return list(acta["marcador"])
    if any(not g.get("equipo") for g in acta.get("goles", [])):
        return None  # algún goleador sin equipo: no se puede saber el marcador con seguridad
    return [sum(1 for g in acta["goles"] if g["equipo"] == acta["local"]),
            sum(1 for g in acta["goles"] if g["equipo"] == acta["visitante"])]


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


# ---------------------------------------------------------------------------
# CALENDARIO (fecha, hora y campo) de la jornada en curso y de la siguiente
# ---------------------------------------------------------------------------
_BASE_JORNADA = ("https://www.rfcf.es/pnfg/NPcd/NFG_CmpJornada?cod_primaria=1000120&CodCompeticion=22595821"
                 "&CodGrupo=22595822&CodTemporada=22&CodJornada={j}")
URLS_CALENDARIO = [  # la que se ve en el navegador: trae horarios y resultados
    _BASE_JORNADA + "&Sch_Tipo_Juego=",
]

def pagina_calendario(j):
    ultima = None
    for i, u in enumerate(URLS_CALENDARIO, 1):
        try:
            soup = descargar(u.format(j=j),
                             lambda sp: re.search(r"Jornada\s+\d+", sp.get_text(" ")) is not None,
                             f"calendario jornada {j} (variante {i})")
        except Bloqueado:
            continue
        n = len(soup.select("span.horario"))
        print(f"  Variante {i}: {n} horarios en la página.")
        if n:
            return soup
        ultima = soup
    if ultima is None:
        raise Bloqueado(f"calendario jornada {j}")
    return ultima
RE_FECHA = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b")
RE_HORA = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")

def _fecha(texto):
    m = RE_FECHA.search(texto or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""

def _hora(texto):
    m = RE_HORA.search(texto or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""

def equipos_en(texto):
    """Equipos del grupo que aparecen en un texto, en el orden en que aparecen."""
    t = sin_tildes(texto)
    vistos = {}
    for clave, nombre in EQUIPOS.items():
        m = re.search(r"\b" + clave + r"\b", t)
        if m and (nombre not in vistos or m.start() < vistos[nombre]):
            vistos[nombre] = m.start()
    return [n for n, _ in sorted(vistos.items(), key=lambda x: x[1])]

def partidos_con_horario(soup):
    """Formato de la RFCF: cada partido es una tabla; la 1ª fila lleva local, <span class="horario">fecha</span>
    + hora y visitante; la fila siguiente, el campo, el tipo de césped y el árbitro."""
    encontrados = {}
    for sp in soup.select("span.horario"):
        fila = sp.find_parent("tr")
        if not fila:
            continue
        eqs = equipos_en(fila.get_text(" ", strip=True))
        if len(eqs) != 2 or frozenset(eqs) in encontrados:
            continue
        celda = sp.find_parent("td") or fila
        texto_celda = celda.get_text(" ", strip=True)
        campo = arbitro = ""
        tabla = fila.find_parent("table")
        if tabla:
            resto = []
            for tr in tabla.find_all("tr"):
                if tr is not fila and fila not in tr.parents and tr not in fila.parents:
                    resto += list(tr.stripped_strings)
            if resto and not resto[0].lower().startswith("árbitro"):
                campo = limpio(resto[0])
            for i, t in enumerate(resto):
                if t.lower().startswith("árbitro") and i + 1 < len(resto):
                    arbitro = limpio(resto[i + 1])
        a = fila.find("a", href=re.compile(r"CodActa=\d+", re.I))
        # Estado: la RFCF escribe "En juego" (o "Descanso", "Aplazado"...) mientras no hay acta;
        # cuando el acta está cerrada pone un icono de visto bueno.
        bloque = tabla or fila
        txt_bloque = sin_tildes(bloque.get_text(" ", strip=True))
        if re.search(r"EN JUEGO|DESCANSO|DIRECTO", txt_bloque):
            estado = "en_juego"
        elif re.search(r"APLAZAD|SUSPENDID", txt_bloque):
            estado = "aplazado"
        elif bloque.find(class_=re.compile(r"check|success-icon|finaliz", re.I)) or \
                bloque.find("img", src=re.compile(r"check|ok\.|final|acta", re.I)):
            estado = "final"
        else:
            estado = ""
        marcador = None
        for h in celda.find_all(["h4", "strong"]):
            mm = re.fullmatch(r"\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", h.get_text(" "))
            if mm:
                marcador = [int(mm.group(1)), int(mm.group(2))]
                # orden local-visitante tal como aparecen en la fila
                break
        encontrados[frozenset(eqs)] = {
            "orden": eqs, "marcador": marcador, "estado": estado,
            "fecha": _fecha(sp.get_text()) or _fecha(texto_celda),
            "hora": _hora(texto_celda.replace(sp.get_text(), " ")),
            "campo": campo, "arbitro": arbitro,
            "acta": re.search(r"CodActa=(\d+)", a["href"], re.I).group(1) if a else "",
        }
    return encontrados

def partidos_en_pagina_jornada(soup):
    """Busca en la página de la jornada cada bloque con 2 equipos y una fecha."""
    main = soup.find("main") or soup
    encontrados = partidos_con_horario(main)
    if encontrados:
        return encontrados
    for nodo in main.find_all(string=RE_FECHA):
        el, eqs = nodo.parent, []
        while el is not None and el.name not in ("main", "body", "html"):
            eqs = equipos_en(el.get_text(" ", strip=True))
            if len(eqs) >= 2:
                break
            el = el.parent
        if el is None or len(eqs) != 2:
            continue  # p. ej. la fecha de la cabecera de la jornada
        clave = frozenset(eqs)
        if clave in encontrados:
            continue
        texto = el.get_text(" ", strip=True)
        f = RE_FECHA.search(texto)
        campo = ""
        m = re.search(r"(?:Campo|Estadio|Instalaci[oó]n)\s*:?\s*(.+?)(?:\s{2,}|$)", texto, re.I)
        if m:
            campo = limpio(m.group(1))[:60]
        a = el.find("a", href=re.compile(r"CodActa=\d+", re.I))
        encontrados[clave] = {
            "fecha": _fecha(texto),
            "hora": (_hora(texto[f.end():]) or _hora(texto)) if f else "",
            "campo": campo,
            "acta": re.search(r"CodActa=(\d+)", a["href"], re.I).group(1) if a else "",
        }
    return encontrados

def ficha_partido(cod_acta):
    """Fecha, hora, campo y equipos desde la ficha del partido (sirve también antes de jugarse)."""
    soup = descargar(URL_ACTA.format(cod=cod_acta),
                     lambda sp: sp.select_one(".font_widgetL") is not None,
                     f"ficha {cod_acta}")
    main = soup.find("main") or soup
    texto = main.get_text(" ", strip=True)
    m = re.search(r"Jornada\s+\d+\s+(.{0,40})", texto)
    cab = m.group(1) if m else ""
    estadio = ""
    s = main.find("strong", string=re.compile(r"Estadio", re.I))
    if s and s.parent:
        estadio = limpio(re.sub(r"Estadio\s*:?", "", s.parent.get_text(" "), flags=re.I))
    ciudad = ""
    h4 = main.find(lambda t: t.name in ("h4", "h5") and "Ciudad" in t.get_text())
    if h4:
        ciudad = limpio(re.sub(r"Ciudad\s*:?", "", h4.get_text(" ")))
    return {
        "local": nombre_equipo(main.select_one(".font_widgetL").get_text()),
        "visitante": nombre_equipo(main.select_one(".font_widgetV").get_text()) if main.select_one(".font_widgetV") else "",
        "fecha": _fecha(cab), "hora": _hora(cab), "campo": estadio, "ciudad": ciudad,
    }

def cargar_calendario():
    if FICHERO_CALENDARIO.exists():
        try:
            return json.loads(FICHERO_CALENDARIO.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}

def inicio_partido(d):
    if not d.get("fecha"):
        return None
    hora = d.get("hora") if not d.get("aprox") else ""
    try:
        return datetime.strptime(d["fecha"] + " " + (hora or "23:59"), "%Y-%m-%d %H:%M").replace(tzinfo=MADRID)
    except ValueError:
        return None


def revisar_jornadas(filas, cal, actas):
    """filas: listas [jornada, local, visitante, gl, gv] del CSV (se modifican aquí).
    Revisa las jornadas con partidos pendientes hasta la siguiente a la última jugada:
    calendario, resultados (de la página de la jornada o del acta) y actas."""
    por_jornada = {}
    for f in filas:
        por_jornada.setdefault(int(f[0]), []).append(f)
    jugadas = [j for j, ps in por_jornada.items() if any(f[3] != "" for f in ps)]
    ultima = max(jugadas) if jugadas else 0
    objetivo = sorted(j for j, ps in por_jornada.items()
                      if j <= ultima + 1 and any(f[3] == "" for f in ps))
    if ultima + 2 in por_jornada and all(f[3] != "" for f in por_jornada.get(ultima + 1, [])):
        objetivo.append(ultima + 2)
    ahora = datetime.now(MADRID)
    cambios = nuevas_actas = 0

    for j in objetivo:
        print(f"Jornada {j}...")
        try:
            soup = pagina_calendario(j)
        except Bloqueado:
            soup = None
            print("  La página de la jornada no responde: se usan las fechas y códigos de acta ya guardados.")
        if soup is not None:
            texto = (soup.find("main") or soup).get_text(" ", strip=True)
            m = re.search(r"Jornada\s+\d+\D{0,15}(\d{1,2}[-/]\d{1,2}[-/]\d{4})", texto)
            fecha_jornada = _fecha(m.group(1)) if m else ""
            en_pagina = partidos_en_pagina_jornada(soup)
            print(f"  La página trae {len(soup.select('span.horario'))} horarios; reconocidos {len(en_pagina)} partidos.")
        else:
            fecha_jornada, en_pagina = "", {}
        previo = cal.get(str(j), {})
        nuevo = {}
        for f in por_jornada[j]:
            l, v = f[1], f[2]
            clave = f"{l}|{v}"
            d = dict(previo.get(clave, {}))
            p = en_pagina.get(frozenset((l, v)))
            if p:
                for k in ("fecha", "hora", "campo", "arbitro", "acta"):
                    if p.get(k):
                        d[k] = p[k]
                if p.get("fecha"):
                    d.pop("aprox", None)
            if not d.get("fecha") and fecha_jornada:
                d["fecha"], d["aprox"] = fecha_jornada, True
            nuevo[clave] = d

            # --- Resultado ---
            ini = inicio_partido(d)
            terminado = ini is not None and ahora >= ini + DURACION_PARTIDO
            reciente = ini is not None and ahora - ini <= timedelta(days=1, hours=12)
            estado = (p or {}).get("estado", "")
            d["estado"] = estado
            if estado == "en_juego" or estado == "aplazado":
                # Mientras la federación lo marca así no hay resultado; si había uno puesto, se quita.
                if f[3] != "":
                    cambios += 1
                    print(f"  J{j} {l} - {v}: {estado.replace('_', ' ')} según la federación -> se quita {f[3]}-{f[4]}")
                    f[3], f[4] = "", ""
                continue
            marcador_web = None
            if p and p.get("marcador"):
                gl, gv = p["marcador"]
                marcador_web = [gl, gv] if p["orden"][0] == l else [gv, gl]
            cod = d.get("acta")
            # El acta se descarga si el partido ya debería haber terminado y no la tenemos completa,
            # o si es reciente (la federación a veces corrige el acta en las horas siguientes).
            if cod and terminado and (not acta_completa(actas.get(cod)) or reciente):
                try:
                    a = extraer_acta_partido(cod)
                except Bloqueado:
                    a = None
                    print(f"  Acta {cod}: la federación no responde; se intentará en la próxima ejecución.")
                if a and acta_completa(a) and {a["local"], a["visitante"]} == {l, v}:
                    if actas.get(cod) != a:
                        nuevas_actas += 1
                    actas[cod] = a
                    n_jug = sum(len(x["titulares"]) + len(x["suplentes"]) for x in a["equipos"].values())
                    print(f"  Acta {cod}: {a['local']} - {a['visitante']} · {n_jug} jugadores · {len(a['goles'])} goles")
            a = actas.get(cod) if cod else None
            # Solo hay resultado con acta: la federación lo da por cerrado (visto bueno) o,
            # si no se puede saber, han pasado 2 h 30 desde el inicio y el acta trae alineaciones.
            cerrado = estado == "final" or (ini is not None and ahora >= ini + ACTA_SEGURA)
            marcador = None
            if terminado and a and acta_completa(a) and cerrado:
                marcador = marcador_web
                if marcador is None:
                    r = resultado_desde_acta(a)
                    if r:
                        marcador = r if a["local"] == l else [r[1], r[0]]
            elif terminado and f[3] == "":
                print(f"  J{j} {l} - {v}: terminado pero sin acta cerrada todavía; se queda sin resultado.")
            if marcador:
                d["estado"] = "final"
                ngl, ngv = str(marcador[0]), str(marcador[1])
                if (ngl, ngv) != (f[3], f[4]):
                    cambios += 1
                    print(f"  RESULTADO J{j} {l} - {v}: {f[3] or '·'}-{f[4] or '·'} -> {ngl}-{ngv}")
                    f[3], f[4] = ngl, ngv

        cal[str(j)] = nuevo
        for clave, d in nuevo.items():
            print(f"  {clave.replace('|', ' - ')}: {d.get('fecha') or '¿fecha?'} {d.get('hora', '')} {d.get('campo', '')}")
        print(f"  {sum(1 for d in nuevo.values() if d.get('fecha'))} de {len(nuevo)} partidos con fecha.")
    return cambios, nuevas_actas


def main():
    html = HTML.read_text(encoding="utf-8")
    i = html.index(INICIO) + len(INICIO)
    j = html.index(FIN, i)
    lineas = html[i:j].strip().splitlines()
    cabecera, filas = lineas[0], [l.split(",") for l in lineas[1:]]

    cal = cargar_calendario()
    actas = cargar_actas()
    try:
        cambios, nuevas_actas = revisar_jornadas(filas, cal, actas)
    finally:
        # se guarda siempre lo conseguido, aunque algo falle a mitad
        HTML.write_text(html[:i] + "\n".join([cabecera] + [",".join(f) for f in filas]) + html[j:], encoding="utf-8")
        guardar_actas(actas)
        DIRECTORIO_DATOS.mkdir(exist_ok=True, parents=True)
        FICHERO_CALENDARIO.write_text(json.dumps(cal, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Listo: {cambios} resultado(s) nuevo(s) o corregido(s), {nuevas_actas} acta(s) nueva(s) o actualizada(s).")


if __name__ == "__main__":
    main()

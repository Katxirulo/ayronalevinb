"""Actualiza los resultados de index.html a partir del PDF de la tabla cruzada de la RFCF.

Uso: python scripts/actualizar.py [ruta_del_pdf]
Sin argumento, usa el PDF más reciente de la carpeta pdf/.
"""
import re
import sys
from pathlib import Path

import pdfplumber

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "index.html"

# Palabra clave del PDF -> nombre usado en la web
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


def leer_pdf(ruta):
    with pdfplumber.open(ruta) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    # Orden de equipos: el de su primera aparición (cabecera de columnas)
    posiciones = {}
    for clave in EQUIPOS:
        m = re.search(r"\b" + clave + r"\b", texto)
        if not m:
            sys.exit(f"No encuentro el equipo {clave} en el PDF")
        posiciones[clave] = m.start()
    orden = [EQUIPOS[k] for k in sorted(posiciones, key=posiciones.get)]
    celdas = re.findall(r"\bJ\s?\d{1,2}\b|\b\d{1,2}\s?-\s?\d{1,2}\b", texto)
    n = len(orden)
    if len(celdas) != n * (n - 1):
        sys.exit(f"Esperaba {n * (n - 1)} celdas y he leído {len(celdas)}. Revisa el PDF.")
    resultados, k = {}, 0
    for local in orden:
        for visitante in orden:
            if local == visitante:
                continue
            c = celdas[k].replace(" ", "")
            k += 1
            if c.startswith("J"):
                resultados[(local, visitante)] = ("J", int(c[1:]))
            else:
                gl, gv = c.split("-")
                resultados[(local, visitante)] = ("R", (int(gl), int(gv)))
    return resultados


def main():
    if len(sys.argv) > 1:
        pdf = Path(sys.argv[1])
    else:
        pdfs = sorted((RAIZ / "pdf").glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        if not pdfs:
            sys.exit("No hay ningún PDF en la carpeta pdf/")
        pdf = pdfs[-1]
    print(f"Leyendo {pdf.name}")
    res = leer_pdf(pdf)

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
            sys.exit(f"El partido {local} - {visitante} no está en el PDF")
        if dato[0] == "R":
            ngl, ngv = map(str, dato[1])
        else:
            ngl, ngv = "", ""
        if (ngl, ngv) != (gl, gv):
            cambios += 1
            print(f"  J{jornada} {local} - {visitante}: {gl or '·'}-{gv or '·'} -> {ngl or '·'}-{ngv or '·'}")
        nuevas.append(",".join([jornada, local, visitante, ngl, ngv]))

    HTML.write_text(html[:i] + "\n".join([cabecera] + nuevas) + html[j:], encoding="utf-8")
    print(f"Listo: {cambios} partido(s) actualizado(s).")


if __name__ == "__main__":
    main()

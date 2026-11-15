"""Sale con código 0 si hoy (hora de España) queda algún partido sin resultado; si no, con 1.
Lo usa el workflow para seguir actualizando cada 20 minutos mientras dura la jornada."""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
ahora = datetime.now(ZoneInfo("Europe/Madrid"))
hoy = ahora.strftime("%Y-%m-%d")

html = (RAIZ / "index.html").read_text(encoding="utf-8")
ini = html.index('<script type="text/plain" id="datos">\n')
fin = html.index("\n</script>", ini)
filas = [l.split(",") for l in html[ini:fin].splitlines()[2:] if l.count(",") == 4]
try:
    cal = json.loads((RAIZ / "data" / "calendario.json").read_text(encoding="utf-8"))
except Exception:
    cal = {}

pendientes = []
for j, l, v, gl, gv in filas:
    d = cal.get(j, {}).get(f"{l}|{v}", {})
    if d.get("fecha") == hoy and gl == "":
        pendientes.append(f"J{j} {l} - {v} ({d.get('hora', '¿hora?')})")

if pendientes and ahora.hour < 22:
    print("Partidos de hoy aún sin resultado: " + "; ".join(pendientes))
    sys.exit(0)
print("No quedan partidos de hoy sin resultado.")
sys.exit(1)

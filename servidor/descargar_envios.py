"""Descarga los envíos nuevos del servidor de auto-cdlc a la carpeta 'envios' (uno por archivo .json.gz).

Uso:  python descargar_envios.py --url https://auto-cdlc-envios.TU-SUBDOMINIO.workers.dev --token TU_TOKEN
      (o pon las variables de entorno AUTO_CDLC_ENVIOS_URL y AUTO_CDLC_ENVIOS_TOKEN)
Con --borrar, borra del servidor cada envío ya descargado (para no pasar del espacio gratuito de R2).
Solo usa la biblioteca estándar de Python.
"""
import argparse, json, os, urllib.request, urllib.parse
from pathlib import Path


def pedir(url, token, metodo="GET"):
    r = urllib.request.Request(url, method=metodo, headers={"Authorization": f"Bearer {token}",
                                                             "User-Agent": "auto-cdlc-descargas"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("AUTO_CDLC_ENVIOS_URL"))
    ap.add_argument("--token", default=os.environ.get("AUTO_CDLC_ENVIOS_TOKEN"))
    ap.add_argument("--carpeta", default="envios")
    ap.add_argument("--borrar", action="store_true", help="borrar del servidor lo ya descargado")
    a = ap.parse_args()
    if not a.url or not a.token:
        ap.error("faltan --url y --token")
    base = a.url.rstrip("/")
    destino = Path(a.carpeta); destino.mkdir(parents=True, exist_ok=True)
    lista = json.loads(pedir(base + "/envios", a.token))["envios"]
    nuevos = 0
    for e in lista:
        archivo = destino / e["clave"].replace("envios/", "").replace("/", "_")
        if not archivo.exists():
            archivo.write_bytes(pedir(base + "/" + urllib.parse.quote(e["clave"]), a.token))
            nuevos += 1
        if a.borrar:
            pedir(base + "/" + urllib.parse.quote(e["clave"]), a.token, "DELETE")
    print(f"{len(lista)} envíos en el servidor, {nuevos} descargados ahora en {destino.resolve()}")


if __name__ == "__main__":
    main()

"""Descarga los envíos nuevos del servidor de auto-cdlc a la carpeta 'envios' (uno por archivo .json.gz).

Uso:  python descargar_envios.py
      Pide el token sin mostrarlo (mejor que escribirlo en la línea de comandos, donde caracteres como
      & o % lo rompen). También valen --url / --token o las variables de entorno AUTO_CDLC_ENVIOS_URL y
      AUTO_CDLC_ENVIOS_TOKEN.
Con --borrar, borra del servidor cada envío ya descargado (para no pasar del espacio gratuito de R2).
Solo usa la biblioteca estándar de Python.
"""
import argparse, getpass, json, os, urllib.error, urllib.request, urllib.parse
from pathlib import Path


def pedir(url, token, metodo="GET"):
    r = urllib.request.Request(url, method=metodo, headers={"Authorization": f"Bearer {token}",
                                                             "User-Agent": "auto-cdlc-descargas"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("AUTO_CDLC_ENVIOS_URL", "https://auto-cdlc-envios.auto-cdlc.workers.dev"))
    ap.add_argument("--token", default=os.environ.get("AUTO_CDLC_ENVIOS_TOKEN"))
    ap.add_argument("--carpeta", default=str(Path(__file__).resolve().parent / "envios"))
    ap.add_argument("--borrar", action="store_true", help="borrar del servidor lo ya descargado")
    a = ap.parse_args()
    if not a.token:
        a.token = getpass.getpass("Token de administración (no se ve al escribir; pégalo y pulsa Intro): ").strip()
    if not a.url or not a.token:
        ap.error("faltan la dirección o el token")
    base = a.url.rstrip("/")
    destino = Path(a.carpeta); destino.mkdir(parents=True, exist_ok=True)
    try:
        lista = json.loads(pedir(base + "/envios", a.token))["envios"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise SystemExit("El servidor rechaza el token (401). Comprueba que es el mismo que pusiste con "
                             "'npx wrangler secret put ADMIN_TOKEN'.")
        raise
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

"""System report: what the installer and the batches send (voluntarily) when something goes wrong, or at the
end of an install, so problems on other people's PCs can be seen and fixed.

Standard library only, on purpose: the installer runs it even when installing the libraries failed
(uv run --no-project informe.py ...). What it sends is anonymous: the system, versions, which parts were
found (Wwise, cdlc-pack, ffmpeg), the configuration without folder paths, and the log with the user's
folders replaced by <usuario> / <auto-cdlc>. Never audio, lyrics or file names from the user's music.

Command line (used by install.bat / install.sh):
    informe.py install ok|error [log file] [--yes]
"""
import gzip
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
URL = "https://auto-cdlc-envios.auto-cdlc.workers.dev"
PENDIENTES = AQUI / "pending_uploads"
MAX_REGISTRO = 60_000            # characters of log kept (the end, where errors are)


def version():
    try:
        m = re.search(r'^VERSION = "([^"]+)"', (AQUI / "auto_cdlc.py").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def leer_config():
    conf = {}
    for nombre in ("config.txt", "configuracion.txt"):
        try:
            for linea in (AQUI / nombre).read_text(encoding="utf-8-sig").splitlines():
                if "=" in linea and not linea.lstrip().startswith("#"):
                    k, v = linea.split("=", 1)
                    conf.setdefault(k.strip().lower(), v.strip())
        except Exception:
            pass
    return conf


def idioma(conf=None):
    v = (conf or leer_config()).get("language") or (conf or leer_config()).get("idioma") or ""
    return "es" if v[:2].lower() == "es" else "en" if v else ("es" if os.environ.get("LANG", "").startswith("es") else "en")


def anonimizar(texto):
    for ruta, sustituto in ((str(AQUI), "<auto-cdlc>"), (str(Path.home()), "<usuario>")):
        for variante in {ruta, ruta.replace("\\", "\\\\"), ruta.replace("\\", "/")}:
            texto = texto.replace(variante, sustituto)
    texto = re.sub(r"(?i)([A-Z]:(?:\\\\|\\|/)(?:Users|Usuarios)(?:\\\\|\\|/))[^\\/\"'\s]+", r"\1<usuario>", texto)
    return re.sub(r"(/(?:home|Users)/)[^/\"'\s]+", r"\1<usuario>", texto)


def _cmd(*orden, timeout=15):
    try:
        r = subprocess.run(list(orden), capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return (r.stdout or r.stderr).strip().splitlines()[0][:120] if (r.stdout or r.stderr).strip() else f"code {r.returncode}"
    except Exception as ex:
        return f"no ({type(ex).__name__})"


def sistema():
    """What's useful to know about the machine, without anything personal."""
    conf = leer_config()
    d = {
        "so": platform.system(), "so_version": platform.release(), "so_detalle": platform.platform(),
        "maquina": platform.machine(), "python": platform.python_version(), "cpus": os.cpu_count(),
        "uv": _cmd("uv", "--version") if shutil.which("uv") else "no",
        "ffmpeg": "sí" if shutil.which("ffmpeg") or (AQUI / "bin" / "ffmpeg.exe").exists() else "no",
        "cdlc_pack": [p.name for p in (AQUI / "tools" / "cdlc-pack").glob("cdlc-pack*") if p.is_file()],
        "entorno_python": (AQUI / ".venv").is_dir(),
        "wine": _cmd("wine", "--version") if shutil.which("wine") else "no",
    }
    try:
        libre = shutil.disk_usage(AQUI).free
        d["disco_libre_gb"] = round(libre / 1e9, 1)
    except Exception:
        pass
    # Wwise installs: just the folder names (they carry the version), wherever the usual places are
    sitios = []
    if os.name == "nt":
        sitios = [Path(os.environ.get(v, "")) / "Audiokinetic" for v in ("ProgramFiles(x86)", "ProgramFiles")]
    elif sys.platform == "darwin":
        sitios = [Path("/Applications/Audiokinetic")]
    else:
        sitios = [Path.home() / ".wine" / "drive_c" / "Program Files (x86)" / "Audiokinetic",
                  Path.home() / ".wine" / "drive_c" / "Program Files" / "Audiokinetic"]
    d["wwise"] = sorted({p.name for s in sitios if s.is_dir() for p in s.iterdir() if p.name.lower().startswith("wwise")})
    d["wwise_configurado"] = bool(conf.get("wwise")) or bool(os.environ.get("WWISEROOT"))
    # configuration without paths
    d["configuracion"] = {k: ("<ruta>" if k in ("psarc_folder", "wwise", "carpeta_psarc") and v else v)
                          for k, v in conf.items() if k not in ("upload_server",)}
    return d


def id_instalacion():
    try:
        ruta = AQUI / ".instalacion"
        if ruta.exists():
            return ruta.read_text().strip()[:40]
        import uuid
        v = uuid.uuid4().hex
        ruta.write_text(v)
        return v
    except Exception:
        return "desconocida"


def _guardar_pendiente(cuerpo):
    try:
        PENDIENTES.mkdir(exist_ok=True)
        if len(list(PENDIENTES.glob("*.json.gz"))) < 500:
            (PENDIENTES / f"{time.strftime('%Y%m%d-%H%M%S')}-sys-{os.getpid()}.json.gz").write_bytes(cuerpo)
    except Exception:
        pass


def enviar(etapa, estado, resumen, registro="", extra=None, url=None):
    """Sends a system report. etapa: install / batch / update. estado: ok / error. Returns True if sent;
    if the server can't be reached it's queued in pending_uploads (sent with the next batch)."""
    datos = {"programa": "auto-cdlc", "tipo": "sistema", "version": version(), "idioma": idioma(),
             "instalacion": id_instalacion(), "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "etapa": etapa, "estado": estado, "resumen": resumen[:500], "sistema": sistema(),
             "registro": registro[-MAX_REGISTRO:], **(extra or {})}
    cuerpo = gzip.compress(anonimizar(json.dumps(datos, ensure_ascii=False, default=str)).encode("utf-8"))
    req = urllib.request.Request((url or URL).rstrip("/") + "/envio", data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/gzip",
                                          "User-Agent": f"auto-cdlc/{datos['version']}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        return True
    except Exception:
        _guardar_pendiente(cuerpo)
        return False


def _si_no(pregunta, defecto=True):
    try:
        r = input(pregunta).strip().lower()
    except EOFError:
        return defecto
    return defecto if not r else r[0] in "sy"


def main(argv):
    if len(argv) < 2 or argv[0] != "install":
        print(__doc__)
        return 2
    estado = "ok" if argv[1] == "ok" else "error"
    registro = ""
    if len(argv) > 2 and not argv[2].startswith("--"):
        try:
            registro = Path(argv[2]).read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    conf = leer_config()
    es = idioma(conf) == "es"
    envio = conf.get("send_results", conf.get("enviar_resultados", "ask")).lower()
    if envio in ("no", "n", "false"):
        return 0
    if "--yes" not in argv and envio not in ("yes", "si", "sí", "true"):
        print()
        si = _si_no("¿Envías un informe anónimo de la instalación (sistema y versiones, sin datos personales)?\n"
                    "Sirve para arreglar problemas en otros PCs. (s/n) [s]: " if es else
                    "Send an anonymous installation report (system and versions, nothing personal)?\n"
                    "It helps fix problems on other PCs. (y/n) [y]: ")
        if not si:
            return 0
    resumen = ("instalación correcta" if estado == "ok" else "la instalación ha fallado") if es else \
              ("install finished" if estado == "ok" else "install failed")
    ok = enviar("install", estado, resumen, registro)
    print(("  Informe enviado, gracias." if ok else "  No se ha podido enviar; se mandará en la próxima tanda.") if es
          else ("  Report sent, thank you." if ok else "  Couldn't send it; it'll go with the next batch."))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

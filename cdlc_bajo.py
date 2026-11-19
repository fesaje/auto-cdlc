"""
cdlc_bajo.py - De mp3 a material para Editor on Fire (bajo de 4 cuerdas, afinación estándar).

Uso:
    uv run cdlc_bajo.py                      -> procesa todo lo que haya en la carpeta "entrada"
    uv run cdlc_bajo.py cancion.mp3 otra.flac -> procesa esos archivos
    uv run cdlc_bajo.py carpeta/              -> procesa todos los audios de esa carpeta
Opciones:
    --salida CARPETA   carpeta de resultados (por defecto "salida")
    --forzar           vuelve a procesar canciones que ya tienen resultados

Por cada canción crea salida/<nombre>/ con:
    <nombre>.ogg       audio con silencio inicial (el que se abre en EOF con File > New)
    <nombre>.svl       mapa de beats (EOF: File > Import > Sonic Visualiser)
    <nombre>.gp5       tablatura de bajo (EOF: File > Import > Guitar Pro > PART REAL_BASS)
    <nombre>_AB.mp3    izquierda = bajo real, derecha = tablatura sintetizada (para revisar con cascos)
    <nombre>_clics.mp3 canción con un clic en cada beat (agudo en el tiempo 1)
    <nombre>.mid       la transcripción en MIDI
    informe.txt        datos del proceso
"""
import re
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np

AQUI = Path(__file__).resolve().parent
VERSION = "0.4.0"
REPO = "https://github.com/fesaje/auto-cdlc"
UA = f"auto-cdlc/{VERSION} (+{REPO})"
ENVIOS_URL = "https://auto-cdlc-envios.auto-cdlc.workers.dev"            # servidor de envíos voluntarios (Cloudflare Worker); configuracion.txt: servidor_envios
CONF_ENVIO = "preguntar"
ENVIAR = False             # se decide en cada tanda (enviar_resultados = preguntar / si / no)
SIN_INTERNET = False      # --sin-internet o configuracion.txt
DIAG = {}                 # diagnóstico de la canción en curso (lo rellenan las etapas; va a diagnostico.json)
COMPILAR = True           # compilar .psarc con herramientas/cdlc-pack
CARPETA_PSARC = None
WWISE = None
ATAQUE_POR_PICO = True     # ritmo de cada nota desde el pico del ataque (ver transcribir)
PARTIR_REPETIDAS = True    # cortar notas largas donde el bajo vuelve a pulsar; configuracion.txt: partir_repetidas
UMBRAL_REATAQUE_DB = 3.0   # subida de energía mínima para considerar un nuevo golpe; configuracion.txt: umbral_reataque_db
LETRA = True               # buscar la letra en LRCLIB; configuracion.txt: letra
ARREGLO_SIMPLE = 2         # None = sin segundo arreglo; 0 compás, 1 medio compás, 2 tiempo, 3 corchea
NOMBRES_SIMPLE = {0: "una nota por compás", 1: "una por medio compás", 2: "una por tiempo", 3: "una por corchea"}
NOMBRES_SIMPLE_EN = {0: "one note per bar", 1: "one per half bar", 2: "one per beat", 3: "one per eighth note"}
VELOCIDAD_SCROLL = 1.3     # velocidad de las notas en el juego; configuracion.txt: velocidad_scroll
VELOCIDAD_AUTO = False     # "auto": proporcional al tempo (VELOCIDAD_SCROLL es la de 120 BPM)
VELOCIDAD_LIMITES = (0.9, 2.2)
MADMOM_INESTABLE = 0.03    # % de beats de madmom fuera de sitio a partir del cual se usan los de Beat This!
TONO_MODO = "auto"         # tono del bajo en el juego; configuracion.txt: tono_bajo
TONO_CREPE = True          # tono de cada nota con CREPE (más fiable en graves que pYIN); configuracion.txt: tono_crepe
DD_INICIAL = 0            # % de notas del nivel más fácil; configuracion.txt: dificultad_inicial
DD_MODO = "propia"        # propia | dlcbuilder | ninguna; configuracion.txt: dificultad
UMBRAL_CENTS = 30.0       # desvío mínimo (cents) para cambiar el Tuning Pitch; configuracion.txt: umbral_cents
EXTENSIONES = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma"}

# ---------------- parámetros (los que funcionaron en las pruebas) ----------------
SR = 22050                 # análisis del bajo
HOP = 256
MODELO_BAJO = "kuielab_b_bass.onnx"
PYIN_MIN_PROB = 0.3        # confianza mínima de pYIN; por debajo decide la CQT
ENERGIA_MIN_DB = -40       # notas más flojas que esto (respecto al pico) se ignoran
DUR_MIN = 0.04             # s
TRASTE_MAX = 20
# Afinaciones de bajo de 4 cuerdas: (nombre, cuerdas de grave a aguda en MIDI, penalización a priori)
AFINACIONES = [
    ("E estándar",  [28, 33, 38, 43], 0.00),
    ("Eb estándar", [27, 32, 37, 42], 0.05),
    ("Drop D",      [26, 33, 38, 43], 0.05),
    ("D estándar",  [26, 31, 36, 41], 0.08),
    ("Drop C#",     [25, 32, 37, 42], 0.10),
    ("C# estándar", [25, 30, 35, 40], 0.10),
    ("Drop C",      [24, 31, 36, 41], 0.10),
    ("C estándar",  [24, 29, 34, 39], 0.12),
    ("Drop B",      [23, 30, 35, 40], 0.12),
    ("B estándar",  [23, 28, 33, 38], 0.15),
]
# Índice de púa (contraste agudo ataque/sostenido, dB). Umbral calibrado con canciones conocidas:
# con púa 'Qué puedo hacer' 10.3 y 'Un buen día' 7.1 (Los Planetas); con dedos 'Me agarraste' 6.3 (Quique González).
PUA_UMBRAL_DB = 7.0
PUA_FORZADA = None         # None = detectar; True/False = fijado para el disco en las preguntas
PUA_MARGEN_DB = 1.0       # a menos de 1 dB del umbral se avisa de que conviene comprobarlo de oído
SPM = 16                   # semicorcheas por compás (4/4)
MARGEN_INICIAL = 0.5       # s de silencio antes del compás COUNT
BPM_MIN, BPM_MAX = 60, 180


def log(msg):
    print(msg, flush=True)


IDIOMA = "es"              # idioma de la interfaz: es / en (configuracion.txt: idioma)


def T(es, en):
    """Texto en el idioma de la interfaz."""
    return en if IDIOMA == "en" else es


AFIN_EN = {"E estándar": "E standard", "Eb estándar": "Eb standard", "D estándar": "D standard",
           "C# estándar": "C# standard", "C estándar": "C standard", "B estándar": "B standard"}


def fuente_txt(f):
    return {"etiquetas": T("etiquetas ID3", "ID3 tags"), "nombre del archivo": T("nombre del archivo", "file name")}.get(f, f)


def afin_txt(nombre):
    return AFIN_EN.get(nombre, nombre) if IDIOMA == "en" else nombre


def si_no(r):
    """¿La respuesta es afirmativa? Vale s/si/y/yes."""
    return str(r).strip().lower()[:1] in ("s", "y")


# ---------------- utilidades de audio ----------------
def ffmpeg_bin():
    """ffmpeg del sistema si existe; si no, el que viene dentro de imageio-ffmpeg.
    Se copia como bin/ffmpeg(.exe) y se añade al PATH para que audio-separator también lo encuentre."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    destino_dir = AQUI / "bin"
    destino_dir.mkdir(exist_ok=True)
    destino = destino_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not destino.exists():
        shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), destino)
        destino.chmod(0o755)
    os.environ["PATH"] = str(destino_dir) + os.pathsep + os.environ.get("PATH", "")
    return str(destino)


def ffmpeg(*args):
    r = subprocess.run([ffmpeg_bin(), "-y", "-v", "error", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {r.stderr.strip()[:500]}")


ETIQUETA_BASURA = re.compile(
    r"^(unknown( artist)?|artista desconocido|desconocido|various( artists)?|varios( artistas)?|va|"
    r"track ?\d*|pista ?\d*|untitled|sin t[ií]tulo|audio ?track|new recording.*|\d+)$"
    r"|www\.|https?://|\.(com|net|org|ru|info)\b", re.I)


def leer_etiquetas(ruta):
    """Etiquetas ID3/Vorbis/MP4 del archivo, ya reparadas (vacío si no hay o no se pueden leer)."""
    out = {}
    try:
        import mutagen
        tags = mutagen.File(str(ruta), easy=True)
        if tags and tags.tags:
            for clave in ("artist", "albumartist", "title", "album", "date", "tracknumber", "genre"):
                v = " / ".join(x.strip() for x in (tags.get(clave) or []) if x and x.strip())
                if v:
                    out[clave] = arreglar_texto(v)
    except Exception as ex:
        out["error"] = str(ex)[:200]
    return out


def _etiqueta_valida(texto):
    return bool(texto) and not ETIQUETA_BASURA.search(texto.strip())


def metadatos(ruta):
    """Artista y título. Prioridad: etiquetas del archivo (si traen artista y título que no sean de
    relleno), después el nombre 'Artista - Título', y por último lo que haya.
    Devuelve (artista, titulo, fuente, etiquetas)."""
    et = leer_etiquetas(ruta)
    a_et = et.get("artist") or et.get("albumartist") or ""
    a_et = a_et.split(" / ")[0]  # varios artistas: el primero
    t_et = et.get("title", "")
    stem = ruta.stem.replace("_", " ").strip()
    a_nom, t_nom = "", ""
    if " - " in stem:
        a_nom, t_nom = (x.strip() for x in stem.split(" - ", 1))
        a_nom = re.sub(r"^\d{1,3}[ .-]+", "", a_nom).strip()  # '01 - ...' / '01. Artista - ...'
    a_et, t_et = re.sub(r"\s+", " ", a_et).strip(), re.sub(r"\s+", " ", t_et).strip()
    # etiquetas de descargas de YouTube: "LosPlanetasVEVO" / "Los Planetas - Topic" y "Artista - Título (Videoclip)"
    a_et = re.sub(r"\s*(VEVO|- Topic|Official)$", "", a_et, flags=re.I).strip()
    t_et = re.sub(r"\s*[\(\[](official )?(music )?(video ?clip|videoclip|video oficial|v[ií]deo|lyric video|"
                  r"audio( oficial)?|official (audio|video)|letra|lyrics?)[\)\]]", "", t_et, flags=re.I).strip()
    if " - " in t_et:
        izq, der = (x.strip() for x in t_et.split(" - ", 1))
        if _normalizar(izq).replace(" ", "") in (_normalizar(a_et).replace(" ", ""), _normalizar(a_nom).replace(" ", "")) \
                or not a_et:
            a_et, t_et = izq, der
    if _etiqueta_valida(a_et) and _etiqueta_valida(t_et):
        return a_et, t_et, "etiquetas", et
    if a_nom and t_nom:
        return a_nom, t_nom, "nombre del archivo", et
    artista = a_et if _etiqueta_valida(a_et) else "Desconocido"
    titulo = t_et if _etiqueta_valida(t_et) else stem
    return artista, titulo, "mixta", et


def nombre_carpeta(artista, titulo):
    """'Artista - Título' válido como nombre de carpeta/archivo en Windows."""
    n = f"{artista} - {titulo}"
    n = re.sub(r'[?*"<>\x00-\x1f]', "", n)
    n = re.sub(r"[:/\\|]", "-", n)
    n = re.sub(r"\s+", " ", n).strip().rstrip(". ")
    return n[:120].rstrip(". ") or "Sin nombre"


def destino(ruta, salida):
    """Carpeta de salida de un mp3. Si ya se procesó con el nombre antiguo (el del archivo), se reutiliza
    esa para no repetir el trabajo; si otra canción distinta ocupa el nombre, se añade ' (2)', ' (3)'..."""
    import json
    artista, titulo, fuente, et = metadatos(ruta)
    antiguo = salida / ruta.stem
    if (antiguo / f"{ruta.stem}.gp5").exists():
        return ruta.stem, antiguo, artista, titulo, fuente, et
    base = nombre_carpeta(artista, titulo)
    # nombre con la regla de la 0.2.1.1 ('?' y ':' cambiados por '-'): si ya existe, se reutiliza
    viejo = re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", f"{artista} - {titulo}")).strip().rstrip(". ")[:120].rstrip(". ")
    if viejo != base and (salida / viejo / f"{viejo}.gp5").exists():
        return viejo, salida / viejo, artista, titulo, fuente, et
    for k in range(1, 50):
        nombre = base if k == 1 else f"{base} ({k})"
        d = salida / nombre
        diag = d / "diagnostico.json"
        try:
            ocupada = diag.exists() and json.loads(diag.read_text(encoding="utf-8")).get("archivo") != ruta.name
        except Exception:
            ocupada = False
        if not ocupada:
            return nombre, d, artista, titulo, fuente, et
    return base, salida / base, artista, titulo, fuente, et


def arreglar_texto(texto):
    """Repara textos con la codificación rota (p. ej. 'EdiciÃ³n' -> 'Edición'), típico de etiquetas ID3."""
    if texto and any(m in texto for m in ("Ã", "Â", "â€")):
        try:
            return texto.encode("cp1252", errors="strict").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            try:
                return texto.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
    return texto


def a_ascii(texto):
    """'Luces de neón' -> 'Luces de neon' (para nombres de archivo y orden en el juego)."""
    import unicodedata
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()


def mmss(segundos):
    segundos = max(0, int(round(segundos)))
    return f"{segundos // 60}:{segundos % 60:02d}"


def album_y_anio(ruta):
    """Álbum y año de las etiquetas del archivo (si no hay: álbum vacío y año actual)."""
    album, year, de_etiqueta = "", time.localtime().tm_year, False
    try:
        import mutagen, re
        tags = mutagen.File(str(ruta), easy=True)
        if tags:
            album = arreglar_texto((tags.get("album") or [""])[0].strip())
            m = re.search(r"(19|20)\d\d", (tags.get("date") or [""])[0])
            if m: year, de_etiqueta = int(m.group(0)), True
    except Exception:
        pass
    return {"album": album, "year": year, "year_de_etiqueta": de_etiqueta}


# ---------------- 1. separación del bajo ----------------
def separar_bajo(wav_mezcla, tmp):
    from audio_separator.separator import Separator
    modelos = AQUI / "modelos"
    modelos.mkdir(exist_ok=True)
    sep = Separator(output_dir=str(tmp), model_file_dir=str(modelos), output_format="WAV",
                    log_level=40)
    sep.load_model(model_filename=MODELO_BAJO)
    salidas = sep.separate(str(wav_mezcla))
    for s in salidas:
        p = Path(s) if Path(s).is_absolute() else Path(tmp) / s
        if "(Bass)" in p.name:
            return p
    raise RuntimeError(f"No se generó el stem de bajo: {salidas}")


# ---------------- 2. beats y compases (madmom) ----------------
BEAT_THIS_SHA256 = "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331"
BEAT_THIS_URLS = ["https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt",
                  "https://huggingface.co/rtikw/localmusic-assets/resolve/main/analysis/beat_this-final0.ckpt"]


def modelo_beat_this():
    """Ruta del modelo de Beat This! (se descarga una vez y se comprueba su huella SHA-256)."""
    import hashlib, urllib.request
    ruta = AQUI / "modelos" / "beat_this-final0.ckpt"

    def valido(r):
        if not r.exists() or r.stat().st_size < 50_000_000:
            return False
        h = hashlib.sha256()
        with open(r, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        return h.hexdigest() == BEAT_THIS_SHA256
    if valido(ruta):
        return ruta
    if getattr(modelo_beat_this, "fallo", False):
        return None                                  # ya falló en esta tanda: no reintentar en cada canción
    ruta.parent.mkdir(exist_ok=True)
    for url in BEAT_THIS_URLS:
        try:
            log(T("  Descargando el modelo de Beat This! (una sola vez, 81 MB)...",
              "  Downloading the Beat This! model (only once, 81 MB)..."))
            tmp = ruta.with_suffix(".parcial")
            urllib.request.urlretrieve(url, tmp)
            if valido(tmp):
                tmp.replace(ruta); return ruta
            tmp.unlink(missing_ok=True)
        except Exception as ex:
            DIAG.setdefault("beat_this_descarga", []).append(f"{url.split('/')[2]}: {str(ex)[:120]}")
    modelo_beat_this.fallo = True
    log(T("  Aviso: no he podido descargar el modelo de Beat This!; el tiempo 1 sale solo de madmom.",
          "  Warning: couldn't download the Beat This! model; the downbeat comes from madmom only."))
    return None


def activacion_beat_this(wav_mezcla):
    """Probabilidad de beat y de tiempo 1 de Beat This! (CPJKU, 2024), a 100 tramas/s como madmom."""
    ckpt = modelo_beat_this()
    if ckpt is None:
        return None, None
    from beat_this.inference import Audio2Frames
    from beat_this.model.postprocessor import Postprocessor
    from beat_this.preprocessing import load_audio
    sig, sr = load_audio(str(wav_mezcla))
    b, d = Audio2Frames(checkpoint_path=str(ckpt), device="cpu")(sig, sr)   # una sola pasada de la red
    beats, _ = Postprocessor(type="minimal")(b, d)
    act = np.stack([1 / (1 + np.exp(-b.numpy())), 1 / (1 + np.exp(-d.numpy()))], 1)
    return np.repeat(act, 2, axis=0), np.asarray(beats)


def reparar_beats(beats):
    """Rellena los beats que faltan y quita los que sobran: un hueco de 2 o 3 beats (tramo flojo donde
    el detector se calla) se parte en beats iguales, y un beat metido a mitad (doble) se quita. Sin esto,
    cada hueco se convertía en un compás de 6/4 o en un tempo absurdo."""
    beats = np.asarray(beats, dtype=float)
    if len(beats) < 8:
        return beats, 0, 0
    out, puestos, quitados = [beats[0]], 0, 0
    for k in range(1, len(beats)):
        ibi_loc = np.median(np.diff(beats[max(0, k - 9):k + 8]))
        g = beats[k] - out[-1]
        r = g / ibi_loc
        if r < 0.6 and k + 1 < len(beats):
            quitados += 1                       # beat de más: se salta
            continue
        if 1.6 < r < 4.5:
            n = int(round(r))
            out += list(out[-1] + g * np.arange(1, n) / n); puestos += n - 1
        out.append(beats[k])
    return np.array(out), puestos, quitados


def detectar_beats(wav_mezcla):
    """Beats y activación de 'tiempo 1'. Beats: madmom (DBN, tempo 60-180), o Beat This! cuando madmom
    salta de tempo. Tiempo 1: Beat This! si cuenta el mismo pulso (o la mitad); si no, la red de compases
    de madmom (que solo se calcula entonces: es lenta)."""
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    beats = np.asarray(DBNBeatTrackingProcessor(fps=100, min_bpm=BPM_MIN, max_bpm=BPM_MAX)(
        RNNBeatProcessor()(str(wav_mezcla))))
    info = {"motor_tiempo_1": "madmom"}
    act, act_alt = None, None
    try:
        act_bt, beats_bt = activacion_beat_this(wav_mezcla)
    except Exception as ex:
        act_bt, beats_bt = None, None
        info["beat_this_error"] = str(ex)[:200]
    if act_bt is not None and len(beats_bt) > 8 and len(beats) > 8:
        r = float(np.median(np.diff(beats_bt)) / np.median(np.diff(beats)))
        info["beat_this_relacion_tempo"] = round(r, 2)
        ibi = np.diff(beats)
        inestable = float(np.mean(np.abs(ibi / np.median(ibi) - 1) > 0.3))
        info["madmom_beats_inestables_pct"] = round(100 * inestable, 1)
        if 0.85 < r < 1.15:
            act = act_bt; info["motor_tiempo_1"] = "beat_this"
            if inestable > MADMOM_INESTABLE:
                beats = np.asarray(beats_bt); info["motor_pulso"] = "beat_this (madmom inestable)"
        elif 1.8 < r < 2.2:
            # Beat This! cuenta a la mitad (blancas): sus tiempos 1 siguen cayendo en principios de compás,
            # así que su activación sirve. Si además madmom salta entre tempos, se usan los beats de
            # Beat This! partidos por la mitad, que son más estables
            act = act_bt; info["motor_tiempo_1"] = "beat_this (a mitad de tempo)"
            if inestable > MADMOM_INESTABLE:
                medios = (beats_bt[:-1] + beats_bt[1:]) / 2
                beats = np.sort(np.concatenate([beats_bt, medios]))
                info["motor_pulso"] = "beat_this x2 (madmom inestable)"
        else:
            # Beat This! cuenta el pulso al doble: su "tiempo 1" marca medios compases y confundiría al
            # detector de compases; se usa la red de compases de madmom
            info["motor_tiempo_1"] = "madmom (beat_this a otro tempo)"
            if 0.4 < r < 0.6:
                # Beat This! cuenta al doble. En 4/4 su tiempo 1 no sirve, pero en las canciones ternarias
                # (6/8, zamba...) cuenta corcheas y su tiempo 1 sí cae en el principio de compás: se guarda
                # y construir_grid decide si la canción es ternaria y cuál de las dos activaciones usar
                act_alt = act_bt
    if act is None:
        from madmom.features.downbeats import RNNDownBeatProcessor
        act = np.asarray(RNNDownBeatProcessor()(str(wav_mezcla)))
    beats, puestos, quitados = reparar_beats(beats)
    info["beats_rellenados"], info["beats_quitados"] = puestos, quitados
    DIAG["deteccion_pulso"] = info
    return beats, act, act_alt


# probabilidades de compases irregulares (por compás): bajas para que sólo aparezcan con evidencia clara
P_COMPAS = {2: 0.003, 3: 0.005, 5: 0.005, 6: 0.002}


def compases_viterbi(a, metro=4):
    """Posición de cada beat dentro de su compás (0 = tiempo 1), compás a compás, y la verosimilitud del
    camino. El compás de base es 'metro' (4 = 4/4, 3 = 3/4 o 6/8); admite compases sueltos de 2 a 6 tiempos
    si la red lo indica claramente (en 3/4 no se admite el de 6: son dos de 3)."""
    K = 6
    largos = {n: P_COMPAS.get(n, 0.0) for n in range(2, K + 1) if n != metro}
    if metro == 3:
        largos[6] = 0.0; largos[4] = P_COMPAS[3]
    largos[metro] = 1 - sum(largos.values())
    LT = np.full((K, K), -np.inf)
    resto = 1.0
    for st in range(K):                         # en la posición st, el compás acaba con st+1 tiempos
        pf = largos.get(st + 1, 0.0)
        h = pf / resto if resto > 1e-12 else 1.0
        if h > 0: LT[st, 0] = np.log(min(h, 1.0))
        if h < 1 and st + 1 < K: LT[st, st + 1] = np.log(1 - h)
        resto -= pf
    a = np.clip(a, 1e-3, 1 - 1e-3)
    em = np.stack([np.log(a)] + [np.log(1 - a)] * (K - 1), axis=1)       # (N, K)
    N = len(a)
    d = np.full(K, -np.inf); d[:metro] = np.log(1 / metro); d = d + em[0]
    bp = np.zeros((N, K), dtype=int)
    for i in range(1, N):
        c = d[:, None] + LT                    # desde (fila) -> hacia (columna)
        bp[i] = c.argmax(0); d = c.max(0) + em[i]
    pos = np.zeros(N, dtype=int); pos[-1] = int(d.argmax())
    for i in range(N - 1, 0, -1):
        pos[i - 1] = bp[i, pos[i]]
    return pos, float(d.max())


def construir_grid(beats, act, duracion, act_alt=None):
    """Devuelve grid de beats (cubre desde antes del segundo 0 hasta el final), índices de inicio de compás
    (el último es la marca de fin), tempo, confianza del tiempo 1, compases irregulares y compás de base.
    Se prueba 4/4 y 3/4 (las canciones en 3 o en 6/8 salían como 4/4 con decenas de compases "irregulares").
    act_alt: activación de Beat This! cuando cuenta al doble; solo vale si la canción es ternaria."""
    med = float(np.median(np.diff(beats)))
    fr = np.clip(np.round(beats * 100).astype(int), 0, len(act) - 1)

    def act_en(ac):
        f = np.clip(fr, 0, len(ac) - 1)
        return np.array([ac[max(0, x - 2):x + 3, 1].max() for x in f])

    candidatos = []
    for nombre, ac in (("principal", act), ("beat_this_doble", act_alt)):
        if ac is None:
            continue
        a_ = act_en(ac)
        p4, l4 = compases_viterbi(a_, 4)
        p3, l3 = compases_viterbi(a_, 3)
        # 3/4 si explica claramente mejor el tiempo 1 (margen para no cambiar canciones en 4/4 por ruido)
        metro_, pos_, ll = (3, p3, l3) if l3 > l4 + 6.0 else (4, p4, l4)
        if nombre == "beat_this_doble" and metro_ != 3:
            continue                            # en 4/4 al doble, su "tiempo 1" marca medios compases
        uno = a_[pos_ == 0].mean() if (pos_ == 0).any() else 0.0
        otros = a_[pos_ != 0].mean() if (pos_ != 0).any() else 0.0
        candidatos.append((uno - otros, nombre, metro_, pos_, a_, round(l3 - l4, 1)))
    _, fuente, metro, pos, a, ventaja3 = max(candidatos, key=lambda c: c[0])
    # En el final (ritardando, fundido, nota larga) los beats son poco fiables y salen compases "irregulares"
    # falsos: los últimos 3 compases se fuerzan al compás de base, empezando en el último tiempo 1 anterior.
    corte = len(pos) - 3 * metro
    if corte > metro:
        inicio = max(i for i in range(corte + 1) if pos[i] == 0)
        pos = pos.copy()
        pos[inicio:] = np.arange(len(pos) - inicio) % metro
    # hacia atrás: completar el compás del primer beat y añadir compases enteros hasta cubrir el segundo 0
    n_pre = int(pos[0])
    while beats[0] - n_pre * med > 0:
        n_pre += metro
    grid = list(beats[0] - k * med for k in range(n_pre, 0, -1)) + list(beats)
    posg = [(int(pos[0]) - k) % metro for k in range(n_pre, 0, -1)] + list(pos)
    # hacia delante: seguir en el compás de base hasta pasar el final y cerrar el compás
    while grid[-1] < duracion + med or posg[-1] != 0:
        grid.append(grid[-1] + med)
        posg.append(0 if posg[-1] >= metro - 1 else posg[-1] + 1)
    grid, posg = np.array(grid), np.array(posg)
    barras = np.flatnonzero(posg == 0)
    # confianza: compases (con beats reales) cuyo tiempo 1 tiene la activación más alta del compás
    ag = np.concatenate([np.full(n_pre, np.nan), a, np.full(len(grid) - n_pre - len(a), np.nan)])
    aciertos = total = 0
    irregulares = []
    for i in range(len(barras) - 1):
        seg = ag[barras[i]:barras[i + 1]]
        if np.isnan(seg).any():
            continue
        total += 1; aciertos += int(np.argmax(seg) == 0)
        if len(seg) != metro:
            irregulares.append((i, len(seg)))
    conf = aciertos / total if total else 0.0
    ibi = np.diff(beats)
    tempos_compas = [60 / np.mean(np.diff(grid[barras[i]:barras[i + 1] + 1]))
                     for i in range(len(barras) - 1) if barras[i + 1] - barras[i] >= 2]
    a_uno = [ag[b] for b in barras[:-1] if not np.isnan(ag[b])]
    a_otros = ag[~np.isnan(ag)][posg[~np.isnan(ag)] != 0] if (~np.isnan(ag)).any() else np.array([0.0])
    DIAG["beats"] = {
        "beats_madmom": len(beats), "tempo_mediano": round(60 / med, 1),
        "tempo_compas_min": round(float(min(tempos_compas)), 1) if tempos_compas else None,
        "tempo_compas_max": round(float(max(tempos_compas)), 1) if tempos_compas else None,
        "variacion_entre_beats_ms": round(float(np.std(ibi) * 1000), 1),
        "beats_saltados_o_dobles": int(np.sum((ibi > 1.5 * med) | (ibi < 0.6 * med))),
        "confianza_tiempo_1": round(conf, 3),
        "activacion_media_en_el_1": round(float(np.mean(a_uno)), 3) if a_uno else None,
        "activacion_media_resto": round(float(np.mean(a_otros)), 3),
        "compases_irregulares": [{"compas_grid": i, "tiempos": n} for i, n in irregulares],
        "beats_añadidos_al_principio": int(n_pre),
        "compas_de_base": f"{metro}/4", "ventaja_3_sobre_4": ventaja3, "activacion_tiempo_1": fuente,
    }
    return grid, barras, 60 / med, conf, irregulares, metro


# ---------------- 3. notas ----------------
def partir_reataques(notas, y, desde=3.0, sep=0.06, min_dur=0.12):
    """El detector de ataques no ve bien los golpes repetidos sobre la misma nota (La-La-La-La): la cuerda
    sigue sonando y apenas cambia nada. Aquí se buscan subidas rápidas de energía en la banda del bajo
    (hasta 400 Hz) dentro de cada nota y se corta en ellas."""
    import librosa, scipy.signal as ss
    hop = 64
    b, a = ss.butter(4, 400 / (SR / 2), "low")
    e = librosa.amplitude_to_db(librosa.feature.rms(y=ss.filtfilt(b, a, y), frame_length=512, hop_length=hop)[0] + 1e-9)
    w1, w2 = max(1, int(0.04 * SR / hop)), max(1, int(0.03 * SR / hop))
    sube = np.full(len(e), -99.0)
    for i in range(w1, len(e) - w2):
        sube[i] = e[i:i + w2].max() - e[i - w1:i].min()
    picos, _ = ss.find_peaks(sube, height=desde, distance=max(1, int(sep * SR / hop)))
    t_re = librosa.frames_to_time(picos, sr=SR, hop_length=hop)
    fr = lambda t: int(round(t * SR / hop))
    techo = e.max()
    out = []
    for t0, t1, p in notas:
        pico_nota = e[fr(t0):max(fr(t1), fr(t0) + 1)].max()
        dentro = []
        for t in t_re[(t_re >= t0 + min_dur) & (t_re <= t1 - 0.07)]:
            # tiene que haber habido una caída antes de la subida: si no, es el propio ataque de la nota
            # (en graves la energía tarda en llegar a su máximo) y no un golpe nuevo
            if dentro and t - dentro[-1] < min_dur:
                continue
            ini = fr(dentro[-1] if dentro else t0)
            i = fr(t)
            antes = e[ini:max(ini, i - w1)]          # tramo previo al valle
            # y el golpe nuevo tiene que sonar como una nota: cerca del pico de la nota y por encima del
            # ruido de fondo. Si no, es la cola de la nota apagándose en un silencio (el ruido sube y baja
            # unos dB y parecería un ataque): de ahí salían notas fantasma en los tramos sin bajo
            nuevo = e[i:i + w2].max()
            if nuevo < pico_nota - 12 or nuevo < techo + ENERGIA_MIN_DB + 10:
                continue
            if len(antes) and antes.max() - e[max(ini, i - w1):i].min() >= 1.5:
                dentro.append(float(t))
        bordes = [t0] + dentro + [t1]
        out += [(bordes[k], bordes[k + 1], p) for k in range(len(bordes) - 1)]
    return out


def retonar_crepe(notas, y, cents):
    """Tono de cada nota con CREPE (red neuronal de tono, modelo 'tiny'). CREPE falla en las notas más
    graves del bajo, así que se le pasa el audio una octava más alto (se reproduce al doble de velocidad)
    y luego se baja la octava. Donde CREPE no está seguro se queda el tono de pYIN."""
    try:
        import librosa, torch, torchcrepe
    except Exception as ex:
        return notas, {"error": f"CREPE no disponible: {ex}"[:200]}
    y8 = librosa.resample(y, orig_sr=SR, target_sr=8000)
    with torch.no_grad():
        f, per = torchcrepe.predict(torch.tensor(y8, dtype=torch.float32)[None], 16000, hop_length=80,
                                    fmin=50, fmax=1000, model="tiny", return_periodicity=True,
                                    batch_size=2048, device="cpu")
    midi = librosa.hz_to_midi(f[0].numpy() / 2) - cents / 100
    per = per[0].numpy()
    escala, nombre_ton = tonalidad(notas)
    # las notas "de la canción" se miden en la propia canción: así se respetan los modos (en Re mixolidio
    # el Do natural es tan normal como el Do#, y la plantilla de Re mayor lo daría por extraño)
    peso = np.zeros(12)
    for t0, t1, p in notas:
        peso[int(p) % 12] += max(t1 - t0, 0.05)
    peso /= max(peso.sum(), 1e-9)
    escala = {k for k in range(12) if peso[k] >= 0.04} | ({k for k in escala if peso[k] >= 0.02})
    out, usadas, cambiadas, por_tonalidad = [], 0, 0, 0
    for t0, t1, p in notas:
        a = int(t0 * 100); b = max(a + 1, int((t0 + 0.6 * (t1 - t0)) * 100))
        ok = per[a:b] > 0.3
        if ok.sum() >= 1:
            q = int(round(float(np.median(midi[a:b][ok]))))
            if 20 <= q <= 43 + TRASTE_MAX:
                usadas += 1
                if q != p and abs(q - p) <= 2 and (p % 12) in escala and (q % 12) not in escala:
                    # pYIN y CREPE discrepan un semitono o dos y solo pYIN cae en la tonalidad: suele ser
                    # un deslizamiento o una nota algo desafinada; se queda la de la tonalidad
                    por_tonalidad += 1
                else:
                    cambiadas += q != p; p = q
        out.append((t0, t1, p))
    return out, {"notas_con_tono_crepe": usadas, "distintas_de_pyin": cambiadas,
                 "tonalidad_estimada": nombre_ton, "dudas_resueltas_por_tonalidad": por_tonalidad,
                 "periodicidad_media": round(float(np.mean(per)), 3)}


def tonalidad(notas):
    """Tonalidad aproximada (perfiles de Krumhansl) a partir de las notas pesadas por su duración.
    Devuelve las clases de nota de su escala (en menor, con la sensible) y un nombre."""
    hist = np.zeros(12)
    for t0, t1, p in notas:
        hist[int(p) % 12] += max(t1 - t0, 0.05)
    mayor = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    menor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    mejor = max(((np.corrcoef(hist, np.roll(perfil, k))[0, 1], k, modo)
                 for k in range(12) for modo, perfil in (("mayor", mayor), ("menor", menor))))
    _, k, modo = mejor
    grados = [0, 2, 4, 5, 7, 9, 11] if modo == "mayor" else [0, 2, 3, 5, 7, 8, 10, 11]
    nombres = "Do Do# Re Re# Mi Fa Fa# Sol Sol# La La# Si".split()
    return {(k + g) % 12 for g in grados}, f"{nombres[k]} {modo}"


def transcribir(bajo_wav, semicorchea=None):
    import librosa
    y, _ = librosa.load(str(bajo_wav), sr=SR, mono=True)
    o_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    ataques = librosa.onset.onset_detect(onset_envelope=o_env, sr=SR, hop_length=HOP,
                                         backtrack=True, units="time")
    # Para el RITMO no sirve el inicio "retrocedido" (backtrack): retrocede hasta el mínimo de energía
    # anterior, y cuando la nota previa sigue sonando ese mínimo puede estar muy atrás. La nota acababa
    # una semicorchea antes (en la "a" del tiempo anterior) en vez de en el tiempo. Se usa el pico del
    # ataque menos el retroceso típico de la canción: mismo punto de referencia, sin los casos extremos.
    picos_on = librosa.onset.onset_detect(onset_envelope=o_env, sr=SR, hop_length=HOP,
                                          backtrack=False, units="time")
    if ATAQUE_POR_PICO and len(picos_on) == len(ataques) and len(ataques) > 4:
        retroceso = float(np.median(picos_on - ataques))
        t_ritmo = list(picos_on - retroceso)
    else:
        retroceso, t_ritmo = None, list(ataques)
    f0, _, vp = librosa.pyin(y, fmin=30, fmax=500, sr=SR, hop_length=HOP, frame_length=2048)
    tiempos = librosa.times_like(f0, sr=SR, hop_length=HOP)
    rms_db = librosa.amplitude_to_db(librosa.feature.rms(y=y, hop_length=HOP, frame_length=2048)[0], ref=1.0)
    pico = rms_db.max()

    # desvío de afinación de la grabación respecto a La=440 (cents), con los tramos de pitch fiable
    fiable = (~np.isnan(f0)) & (vp > 0.5)
    if fiable.sum() > 50:
        m = librosa.hz_to_midi(f0[fiable]); z = np.mean(np.exp(2j * np.pi * (m - np.round(m))))
        cents = float(np.angle(z) / (2 * np.pi) * 100)
    else:
        cents = 0.0
    FMIN = 21
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.midi_to_hz(FMIN + cents / 100),
                           n_bins=72, bins_per_octave=12))

    def nota_cqt(idx):
        spec = C[:, idx].mean(axis=1); mejor, nota = -1, None
        for p in range(28, 60):            # respaldo: sólo E1 hacia arriba (por debajo da errores de octava)
            b = p - FMIN
            s = spec[b] + 0.6 * spec[b + 12] + 0.4 * spec[b + 19] + 0.3 * spec[b + 24]
            if s > mejor: mejor, nota = s, p
        return nota

    limites = list(ataques) + [len(y) / SR]
    notas, n_cqt, pitches_pyin = [], 0, []
    descartes = {"segmento_vacio": 0, "silencio": 0, "demasiado_corta": 0, "fuera_de_rango": 0}
    for i in range(len(ataques)):
        t0, t1 = limites[i], limites[i + 1]
        idx = np.where((tiempos >= t0) & (tiempos < t1))[0]
        if len(idx) < 2: descartes["segmento_vacio"] += 1; continue
        seg = rms_db[idx]
        if seg.max() - pico < ENERGIA_MIN_DB: descartes["silencio"] += 1; continue
        bajo = np.where(seg < seg.max() - 30)[0]
        if len(bajo) and bajo[0] > 1:
            idx = idx[:bajo[0]]; t1 = tiempos[idx[-1]]
        if t1 - t0 < DUR_MIN: descartes["demasiado_corta"] += 1; continue
        ok = (~np.isnan(f0[idx])) & (vp[idx] > PYIN_MIN_PROB)
        if ok.sum() >= 2:
            p = int(round(librosa.hz_to_midi(np.median(f0[idx][ok])) - cents / 100))
            pitches_pyin.append(p)
        else:
            p = nota_cqt(idx[:max(4, len(idx) // 2)]); n_cqt += 1
        if 20 <= p <= 43 + TRASTE_MAX:
            notas.append((float(min(t_ritmo[i], t1 - 0.02)), float(t1), p))
        else:
            descartes["fuera_de_rango"] += 1
    n_antes = len(notas)
    if PARTIR_REPETIDAS and notas:
        # tras el ataque de una nota grave hay un pico, un bajón y luego el cuerpo de la nota: en ese tramo
        # no se corta (como mínimo 120 ms, o 3/4 de semicorchea si la canción es lenta)
        guarda = max(0.12, 0.75 * semicorchea) if semicorchea else 0.12
        notas = partir_reataques(notas, y, UMBRAL_REATAQUE_DB, min_dur=guarda)
    info_crepe = {}
    if TONO_CREPE and notas:
        notas, info_crepe = retonar_crepe(notas, y, cents)
    dur = np.array([t1 - t0 for t0, t1, _ in notas]) if notas else np.zeros(1)
    DIAG["transcripcion"] = {
        "retroceso_tipico_ms": round(retroceso * 1000) if retroceso is not None else None,
        "notas_antes_de_partir": n_antes, "cortes_por_reataque": len(notas) - n_antes, "crepe": info_crepe,
        "ataques": len(ataques), "notas": len(notas), "por_pyin": len(pitches_pyin), "por_cqt": n_cqt,
        "descartes": descartes,
        "tramas_con_tono_fiable_pct": round(100 * float(fiable.mean()), 1),
        "cents": round(cents, 1), "cents_concentracion": round(float(abs(z)), 3) if fiable.sum() > 50 else None,
        "duracion_notas_s": {"p10": round(float(np.percentile(dur, 10)), 3), "p50": round(float(np.median(dur)), 3),
                             "p90": round(float(np.percentile(dur, 90)), 3)},
        "rango_dinamico_db": round(float(pico - np.percentile(rms_db, 10)), 1),
    }
    return y, notas, len(ataques), n_cqt, cents, indice_pua(y), pitches_pyin


def es_pua(indice):
    """¿Se marca el arreglo como tocado con púa? Lo fijado para el disco manda sobre la detección."""
    if PUA_FORZADA is not None:
        return bool(PUA_FORZADA)
    return bool(not np.isnan(indice) and indice >= PUA_UMBRAL_DB)


def indice_pua(y):
    """Contraste de energía aguda (2-8 kHz) entre el ataque (0-45 ms) y el sostenido (80-200 ms), en dB.
    La púa produce un 'clic' brillante y corto al pulsar; los dedos, mucho menos."""
    import librosa
    hop = 64; fr = SR / hop                       # ventana de 23 ms: no emborronar el ataque
    S = np.abs(librosa.stft(y, n_fft=512, hop_length=hop)) ** 2
    fq = librosa.fft_frequencies(sr=SR, n_fft=512)
    hf = S[(fq >= 2000) & (fq < 8000)].sum(0)
    # picos de ataque (sin retroceder: el retroceso cae ~60 ms antes del golpe), ventana desde 10 ms antes
    picos = librosa.onset.onset_detect(y=y, sr=SR, hop_length=256, backtrack=False, units="time")
    ini = ((np.asarray(picos) - 0.01) * fr).astype(int)
    ini = ini[ini >= 0]
    wa, s0, s1 = int(0.045 * fr), int(0.08 * fr), int(0.2 * fr)
    vals = []
    for i, o in enumerate(ini):
        fin = ini[i + 1] if i + 1 < len(ini) else len(hf)
        if fin - o < s1: continue
        vals.append(10 * np.log10((hf[o:o + wa].mean() + 1e-12) / (hf[o + s0:o + s1].mean() + 1e-12)))
    if vals:
        DIAG["pua"] = {"n": len(vals), "p25": round(float(np.percentile(vals, 25)), 2),
                       "p50": round(float(np.median(vals)), 2), "p75": round(float(np.percentile(vals, 75)), 2),
                       "umbral": PUA_UMBRAL_DB}
    return float(np.median(vals)) if len(vals) >= 20 else float("nan")


# ---------------- 4. cuantización + digitación ----------------
def cuantizar(notas, grid):
    def pos(t):
        i = int(np.clip(np.searchsorted(grid, t) - 1, 0, len(grid) - 2))
        return i + (t - grid[i]) / (grid[i + 1] - grid[i])
    # Desfase entre los ataques detectados y la rejilla. Medir solo el encaje en semicorcheas es ambiguo:
    # d y d - 1 semicorchea encajan igual de bien, y elegir mal corre TODA la tablatura una casilla
    # (las notas del tiempo y del "y" acaban en la "e" y la "a"). Para desempatar se suma, con menos peso,
    # el encaje en corcheas y en negras: el bajo cae casi siempre en ellas.
    semicorchea = float(np.median(np.diff(grid))) / 4
    inicios = np.array([t0 for t0, _, _ in notas])

    def encaje(d, pesos=(1.0, 0.5, 0.25)):
        ph = np.array([pos(t) for t in inicios + d])
        return sum(w * np.mean(np.cos(2 * np.pi * k * ph)) for w, k in zip(pesos, (4, 2, 1)))

    # margen físico: los ataques detectados van de algo tarde (-40 ms) a bastante pronto (+120 ms);
    # la ventana nunca es más corta que una semicorchea para poder probar todas las fases
    candidatos = np.arange(-0.040, max(0.120, -0.040 + semicorchea), 0.002)
    desfase = float(max(candidatos, key=encaje))
    solo_semicorchea = float(max(np.arange(0, semicorchea, 0.002), key=lambda d: encaje(d, (1.0, 0, 0))))
    q = {}
    choques, choques_otra_nota = 0, 0
    for t0, t1, p in notas:
        s0 = int(round(pos(t0 + desfase) * 4)); s1 = max(s0 + 1, int(round(pos(t1 + desfase) * 4)))
        if s0 in q:
            choques += 1; choques_otra_nota += int(q[s0][2] != p)
        if s0 not in q or (s1 - s0) > (q[s0][1] - q[s0][0]):
            q[s0] = [s0, s1, p]
    antes_del_grid = sum(1 for v in q.values() if v[0] < 0)
    q = sorted(v for v in q.values() if v[0] >= 0)    # seguridad: nada antes del grid
    for i in range(len(q) - 1):
        q[i][1] = min(q[i][1], q[i + 1][0])
    q = [x for x in q if x[1] > x[0]]
    err = np.array([pos(t0 + desfase) * 4 - round(pos(t0 + desfase) * 4) for t0, _, _ in notas])
    ambiguas = float(np.mean(np.abs(err) > 0.35))
    semis = np.array([round(pos(t0 + desfase) * 4) % 4 for t0, _, _ in notas])
    DIAG["cuantizacion"] = {
        "desfase_ms": round(desfase * 1000), "semicorchea_ms": round(semicorchea * 1000),
        "desfase_version_anterior_ms": round(solo_semicorchea * 1000),
        "corrida_una_casilla_respecto_a_antes": abs(round((solo_semicorchea - desfase) / semicorchea)) >= 1,
        "alineacion": round(float(abs(np.mean(np.exp(2j * np.pi * err)))), 3),
        "error_medio_semicorcheas": round(float(np.mean(np.abs(err))), 3), "ambiguas_pct": round(100 * ambiguas, 1),
        "choques_misma_casilla": choques, "choques_con_otra_nota": choques_otra_nota, "antes_del_grid": antes_del_grid,
        "notas_resultantes": len(q),
        "posicion_en_el_tiempo_pct": {k: round(100 * float(np.mean(semis == i)), 1)
                                      for i, k in enumerate(["en_el_tiempo", "e", "y", "a"])},
    }
    return q, desfase, ambiguas


def _nombre_nota(midi):
    nombres = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{nombres[int(midi) % 12]}{int(midi) // 12 - 1}"


def ajustar_a_rango(q, cuerdas):
    """Sube/baja de octava las notas que no caben en el mástil con esta afinación (cuerdas de grave a aguda)."""
    out, movidas = [], 0
    for s0, s1, p in q:
        p2 = p
        while p2 < cuerdas[0]: p2 += 12
        while p2 > cuerdas[-1] + TRASTE_MAX: p2 -= 12
        movidas += p2 != p
        out.append([s0, s1, p2])
    return out, movidas


def elegir_afinacion(q, pitches_pyin):
    """Afinación de 4 cuerdas: E estándar salvo que haya notas graves que lo impidan de forma repetida.
    Si las hay, la nota más grave repetida fija la cuerda grave; entre 'drop' y estándar decide la digitación."""
    # la evidencia de notas graves sale SOLO de pYIN (el respaldo CQT puede equivocarse de octava)
    pitches = np.array(pitches_pyin if len(pitches_pyin) else [p for _, _, p in q])
    umbral = max(4, int(0.01 * len(pitches)))
    cuenta = {p: int((pitches == p).sum()) for p in np.unique(pitches)}
    graves = [p for p in sorted(cuenta) if cuenta[p] >= umbral]
    L = graves[0] if graves else int(pitches.min())
    if L >= 28:
        candidatas = [a for a in AFINACIONES if a[0] == "E estándar"]
    else:
        candidatas = [a for a in AFINACIONES if a[1][0] == L] or [a for a in AFINACIONES if a[1][0] == 23]
    mejor, evaluadas = None, []
    for nombre, cuerdas, prior in candidatas:
        qa, movidas = ajustar_a_rango(q, cuerdas)
        tab, coste = digitar(qa, list(reversed(cuerdas)))
        puntos = coste / max(1, len(qa)) + prior
        evaluadas.append({"afinacion": nombre, "puntos": round(puntos, 3), "notas_movidas_de_octava": movidas})
        if mejor is None or puntos < mejor[0]:
            mejor = (puntos, nombre, cuerdas, tab, movidas)
    _, nombre, cuerdas, tab, movidas = mejor
    graves_vistas = {_nombre_nota(p): cuenta[p] for p in sorted(cuenta)[:5]}
    trastes = [t[4] for t in tab]
    DIAG["afinacion"] = {"elegida": nombre, "nota_grave_repetida": _nombre_nota(L), "umbral_repeticiones": umbral,
                         "notas_mas_graves_pyin": graves_vistas, "candidatas": evaluadas,
                         "traste_max": int(max(trastes)), "traste_medio": round(float(np.mean(trastes)), 1),
                         "cuerdas_uso": {str(c): int(sum(1 for t in tab if t[3] == c)) for c in (1, 2, 3, 4)},
                         "cuerdas_al_aire_pct": round(100 * float(np.mean(np.array(trastes) == 0)), 1)}
    return nombre, cuerdas, tab, movidas, L


def digitar(q, afinacion):
    """afinacion: cuerdas de aguda a grave (cuerda 1 = la más aguda, convención Guitar Pro). Devuelve (tab, coste)."""
    capas, prev = [], None
    for _, _, p in q:
        capa = []
        for s, o in enumerate(afinacion):
            f = p - o
            if not 0 <= f <= TRASTE_MAX: continue
            if prev is None:
                capa.append([f * 0.3, f, s + 1, -1]); continue
            bc, bi = 1e9, -1
            for j, (pc, pf, ps, _) in enumerate(prev):
                c = pc + abs(f - pf) + (0.5 if s + 1 != ps else 0) + f * 0.05
                if c < bc: bc, bi = c, j
            capa.append([bc, f, s + 1, bi])
        capas.append(capa); prev = capa
    j = int(np.argmin([x[0] for x in capas[-1]])); coste = capas[-1][j][0]
    camino = []
    for capa in reversed(capas):
        _, f, s, bp = capa[j]; camino.append((s, f)); j = max(bp, 0)
    camino.reverse()
    return [[q[i][0], q[i][1], q[i][2], camino[i][0], camino[i][1]] for i in range(len(q))], coste


# ---------------- 5. salidas ----------------
def escribir_svl(ruta, beats, etiquetas):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE sonic-visualiser>\n<sv>\n  <data>\n')
        f.write(f'    <model id="1" name="Beats" sampleRate="44100" start="0" end="{int(beats[-1]*44100)}" '
                'type="sparse" dimensions="1" resolution="1" notifyOnAdd="true" dataset="0" />\n')
        f.write('    <dataset id="0" dimensions="1">\n')
        for i, t in enumerate(beats):
            f.write(f'      <point frame="{int(round(t*44100))}" label="{etiquetas[i]}" />\n')
        f.write('    </dataset>\n  </data>\n</sv>\n')


def escribir_gp5(ruta, tab, compases, tempos, artista, titulo, cuerdas):
    """compases: lista de (beat de inicio, nº de tiempos) en coordenadas con el COUNT delante."""
    n_compases = len(compases)
    import guitarpro
    from guitarpro import models as gp
    song = gp.Song(); song.title = titulo; song.artist = artista; song.tempo = tempos[0]
    pista = song.tracks[0]; pista.name = "Bajo"; pista.channel.instrument = 33
    pista.strings = [gp.GuitarString(i + 1, v) for i, v in enumerate(reversed(cuerdas))]; pista.fretCount = 24
    h0 = song.measureHeaders[0]; h0.timeSignature.numerator = compases[0][1]; h0.timeSignature.denominator.value = 4
    while len(song.measureHeaders) < n_compases:
        h = gp.MeasureHeader(); h.number = len(song.measureHeaders) + 1
        h.timeSignature.numerator = compases[len(song.measureHeaders)][1]; h.timeSignature.denominator.value = 4
        song.addMeasureHeader(h); pista.measures.append(gp.Measure(pista, h))
    por_slot = {n[0] + SPM: n for n in tab}; inicios = sorted(por_slot)
    DUR = {16: (1, False), 12: (2, True), 8: (2, False), 6: (4, True), 4: (4, False),
           3: (8, True), 2: (8, False), 1: (16, False)}
    def mejor(s):
        for k in sorted(DUR, reverse=True):
            if k <= s: return k, DUR[k]
    for m in range(n_compases):
        voz = pista.measures[m].voices[0]; voz.beats = []
        sl, fin, primero = compases[m][0] * 4, (compases[m][0] + compases[m][1]) * 4, True
        while sl < fin:
            beat = gp.Beat(voz)
            if sl in por_slot:
                s0, s1, midi, cuerda, traste = por_slot[sl]
                k, (v, pto) = mejor(min(s1 + SPM, fin) - sl)
                n = gp.Note(beat); n.string = cuerda; n.value = traste; n.type = gp.NoteType.normal
                beat.notes.append(n); beat.status = gp.BeatStatus.normal
            else:
                sig = next((s for s in inicios if s > sl), fin)
                k, (v, pto) = mejor(min(sig, fin) - sl); beat.status = gp.BeatStatus.rest
            beat.duration = gp.Duration(value=v, isDotted=pto)
            if primero and m > 0 and tempos[m] != tempos[m - 1]:
                beat.effect.mixTableChange = gp.MixTableChange(tempo=gp.MixTableItem(value=tempos[m], duration=0))
            primero = False; voz.beats.append(beat); sl += k
    guitarpro.write(song, str(ruta))
    comp = guitarpro.parse(str(ruta))
    return sum(1 for mm in comp.tracks[0].measures for vv in mm.voices for bb in vv.beats
               if bb.status == gp.BeatStatus.normal)


# ---------------- 6. proyecto para DLC Builder (sin pasar por EOF) ----------------
TONO_BAJO = {   # tono de bajo limpio (del proyecto de ejemplo de Rocksmith2014.NET, licencia MIT)
    "GearList": {
        "Amp": {"Type": "Amps", "KnobValues": {
            "Bass_Amp_CH350B_15000": -1, "Bass_Amp_CH350B_250": -1, "Bass_Amp_CH350B_2500": 1,
            "Bass_Amp_CH350B_30": 3, "Bass_Amp_CH350B_7500": -1, "Bass_Amp_CH350B_800": 1,
            "Bass_Amp_CH350B_90": 0, "Bass_Amp_CH350B_Bass": 75, "Bass_Amp_CH350B_Gain": 10,
            "Bass_Amp_CH350B_Treble": 46},
            "Key": "Bass_Amp_CH350B", "Skin": "urn:image:dds:gear_bass_amp_ch350b_2", "SkinIndex": 2},
        "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Bass_Cab_CH410BC_57_OffAxis",
                    "Skin": "urn:image:dds:gear_bass_cab_ch410bc_2", "SkinIndex": 2},
        "PostPedal1": {"Type": "Pedals", "KnobValues": {
            "Bass_Pedal_MBComp_Compress": 37, "Bass_Pedal_MBComp_Filter": 240, "Bass_Pedal_MBComp_Rate": 30},
            "Key": "Bass_Pedal_MBComp", "Category": "30781"},
    },
    "ToneDescriptors": ["$[35715]BASS"],
    "NameSeparator": " - ", "IsCustom": True, "Volume": "-21.9", "Key": "bass", "Name": "bass",
}


TONOS_PRESET = {   # tonos de bajo de canciones oficiales (de la base de tonos de DLC Builder)
    "limpio": {"de": "tono limpio de DLC Builder", **{k: TONO_BAJO[k] for k in ("GearList", "ToneDescriptors", "Volume")}},
    "limpio_pua": {"de": "Ramones - Blitzkrieg Bop", "GearList": {"Amp": {"Type": "Amps", "KnobValues": {"Bass_Amp_HT300B_LoShift": 0, "Bass_Amp_HT300B_Mid": 100, "Bass_Amp_HT300B_MidFreq": 3, "Bass_Amp_HT300B_HiShift": 0, "Bass_Amp_HT300B_Bass": 74, "Bass_Amp_HT300B_Gain": 32, "Bass_Amp_HT300B_Treble": 90}, "Key": "Bass_Amp_HT300B"}, "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Bass_Cab_AT810BC_57_Edge"}, "PostPedal1": {"Type": "Pedals", "KnobValues": {"Bass_Pedal_MBComp_Filter": 160, "Bass_Pedal_MBComp_Compress": 41, "Bass_Pedal_MBComp_Rate": 100}, "Key": "Bass_Pedal_MBComp", "Category": "Dynamics"}}, "ToneDescriptors": ["$[35715]BASS"], "Volume": "-20.001999"},
    "saturado": {"de": "Bon Jovi - It's My Life", "GearList": {"Amp": {"Type": "Amps", "KnobValues": {"Bass_Amp_EdenWT550_Bass": 3.5, "Bass_Amp_EdenWT550_Mid": 1.5, "Bass_Amp_EdenWT550_LoFreq": 205, "Bass_Amp_EdenWT550_HiFreq": 2.6, "Bass_Amp_EdenWT550_Lo": -6, "Bass_Amp_EdenWT550_Hi": -3, "Bass_Amp_EdenWT550_MidFreq": 960, "Bass_Amp_EdenWT550_Treble": 8, "Bass_Amp_EdenWT550_Enhance": 25, "Bass_Amp_EdenWT550_Gain": 14}, "Key": "Bass_Amp_EdenWT550"}, "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Bass_Cab_EdenD610XST_Condenser_Edge"}, "PrePedal1": {"Type": "Pedals", "KnobValues": {"Bass_Pedal_BassOverdrive_Blend": 55, "Bass_Pedal_BassOverdrive_Gain": 54, "Bass_Pedal_BassOverdrive_Tone": 46, "Bass_Pedal_BassOverdrive_Filter": 74}, "Key": "Bass_Pedal_BassOverdrive", "Category": "30780"}, "PostPedal1": {"Type": "Pedals", "KnobValues": {"Bass_Pedal_MBComp_Filter": 390, "Bass_Pedal_MBComp_Compress": 48, "Bass_Pedal_MBComp_Rate": 80}, "Key": "Bass_Pedal_MBComp"}}, "ToneDescriptors": ["$[35715]BASS", "$[35716]OVERDRIVE"], "Volume": "-16.000"},
    "distorsion": {"de": "Motörhead - Ace of Spades", "GearList": {"Rack1": {"Type": "Racks", "KnobValues": {"Rack_StudioEQ_BassFreq": 160, "Rack_StudioEQ_HiMidFreq": 3.6, "Rack_StudioEQ_TrebleFreq": 14.2, "Rack_StudioEQ_LoMidFreq": 140, "Rack_StudioEQ_Treble": -4.5, "Rack_StudioEQ_LoMidQ": 1, "Rack_StudioEQ_Bass": 1, "Rack_StudioEQ_HiMid": 2.5, "Rack_StudioEQ_LoMid": -4.5, "Rack_StudioEQ_HiMidQ": 0}, "Key": "Rack_StudioEQ", "Category": "30785"}, "Amp": {"Type": "Amps", "KnobValues": {"Bass_Amp_HT100B_Pres": 36, "Bass_Amp_HT100B_Bass": 80, "Bass_Amp_HT100B_Mid": 86, "Bass_Amp_HT100B_Treble": 100, "Bass_Amp_HT100B_Gain": 92}, "Key": "Bass_Amp_HT100B"}, "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Bass_Cab_GB415BC_57_Edge"}, "PrePedal1": {"Type": "Pedals", "KnobValues": {"Pedal_EQ5_5700": 4, "Pedal_EQ5_2200": 8, "Pedal_EQ5_63": -3, "Pedal_EQ5_250": -6, "Pedal_EQ5_750": 2}, "Key": "Pedal_EQ5", "Category": "30785"}, "PostPedal1": {"Type": "Pedals", "KnobValues": {"Bass_Pedal_MBComp_Filter": 230, "Bass_Pedal_MBComp_Compress": 62, "Bass_Pedal_MBComp_Rate": 24}, "Key": "Bass_Pedal_MBComp", "Category": "30781"}}, "ToneDescriptors": ["$[35715]BASS", "$[35722]DISTORTION"], "Volume": "-20.000"},
    "fuzz": {"de": "Nirvana - Breed", "GearList": {"Amp": {"Type": "Amps", "KnobValues": {"Bass_Amp_HT300B_LoShift": 0, "Bass_Amp_HT300B_Mid": 98, "Bass_Amp_HT300B_MidFreq": 2, "Bass_Amp_HT300B_HiShift": 1, "Bass_Amp_HT300B_Bass": 91, "Bass_Amp_HT300B_Gain": 8, "Bass_Amp_HT300B_Treble": 72}, "Key": "Bass_Amp_HT300B", "Skin": "urn:image:dds:gear_bass_amp_ht300b_1", "SkinIndex": 1}, "Cabinet": {"Type": "Cabinets", "KnobValues": {}, "Key": "Bass_Cab_AT810BC_Tube_Cone"}, "PrePedal1": {"Type": "Pedals", "KnobValues": {"Bass_Pedal_BassFuzz_Tone": 64, "Bass_Pedal_BassFuzz_Gain": 12, "Bass_Pedal_BassFuzz_Filter": 65}, "Key": "Bass_Pedal_BassFuzz", "Category": "Distortion"}}, "ToneDescriptors": ["$[35715]BASS"], "Volume": "-17.779877"},
}
TONOS_DB_URL = "https://github.com/iminashi/tones/raw/main/official.db"


def _norm(t):
    t = a_ascii(str(t)).lower()
    t = re.sub(r"^the\s+|\s*\(.*?\)|\s*\[.*?\]", "", t)
    return re.sub(r"[^a-z0-9]+", "", t)


def base_tonos():
    """Base de tonos oficiales de Rocksmith (la misma que descarga DLC Builder). Se baja una vez (8 MB)."""
    import urllib.request
    ruta = AQUI / "modelos" / "tonos_oficiales.db"
    if ruta.exists():
        return ruta
    memo = ruta.with_suffix(".fallo")
    if SIN_INTERNET or (memo.exists() and time.time() - memo.stat().st_mtime < 86400):
        return None
    try:
        ruta.parent.mkdir(exist_ok=True)
        tmp = ruta.with_suffix(".part")
        urllib.request.urlretrieve(TONOS_DB_URL, tmp)
        if tmp.read_bytes()[:15] != b"SQLite format 3":
            raise RuntimeError("no es una base SQLite")
        tmp.replace(ruta)
        return ruta
    except Exception as ex:
        memo.write_text(str(ex)[:300])
        log(T(f"  Aviso: no se pudo bajar la base de tonos oficiales ({ex}); se usa el tono elegido en la configuración",
              f"  Warning: couldn't download the official tone database ({ex}); using the tone set in the configuration"))
        return None


def tono_oficial(artista=None, titulo=None, nombre=None):
    """Busca un tono de bajo oficial: por nombre exacto, o por canción, o por artista.
    Devuelve (definición, descripción) o (None, None)."""
    import json, sqlite3
    db = base_tonos()
    if db is None:
        return None, None
    con = sqlite3.connect(str(db))
    filas = con.execute("SELECT artist, title, name, description, definition FROM tones WHERE basstone = 1").fetchall()
    con.close()
    if nombre:
        cand = [f for f in filas if f[2].lower() == nombre.lower()]
        tipo = T("por nombre", "by name")
    else:
        a = _norm(artista)
        delart = [f for f in filas if _norm(f[0]) == a] if a else []
        cand = [f for f in delart if _norm(f[1]) == _norm(titulo)]
        tipo = T("de la misma canción", "from the same song")
        if not cand:
            cand, tipo = delart, T("del mismo artista", "from the same artist")
    if not cand:
        return None, None
    # el tono principal: el que solo es "Bass" (sin efecto especial), si lo hay
    cand.sort(key=lambda f: (f[3] != "Bass", "_bass" not in f[2].lower(), f[1], f[2]))
    ar, ti, nom, desc, d = cand[0]
    return json.loads(d), T("oficial", "official") + f" {tipo}: {ar} - {ti} ({nom})"


def rasgos_saturacion(bajo_wav):
    """Medidas del stem de bajo para estimar si va saturado. EXPERIMENTAL: el separador se queda con poco
    de los armónicos de la distorsión, así que solo se apuntan en el diagnóstico (para calibrar)."""
    import librosa
    y, sr = librosa.load(str(bajo_wav), sr=22050, mono=True)
    S = np.abs(librosa.stft(y, n_fft=4096, hop_length=512)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=4096)
    rdb = 10 * np.log10(S.sum(0) + 1e-12)
    act = rdb > rdb.max() - 25
    if act.sum() < 20:
        return {}
    banda = lambda lo, hi: S[(f >= lo) & (f < hi)][:, act].sum(0) + 1e-12
    lo = banda(40, 300)
    blk = int(0.05 * sr); nb = len(y) // blk
    yb = y[:nb * blk].reshape(nb, blk)
    rb = np.sqrt((yb ** 2).mean(1)); pk = np.abs(yb).max(1)
    m = rb > rb.max() * 0.06
    return {"agudos_vs_graves_db": round(float(np.median(10 * np.log10(banda(800, 5000) / lo))), 1),
            "medios_vs_graves_db": round(float(np.median(10 * np.log10(banda(300, 800) / lo))), 1),
            "cresta_db": round(float(np.median(20 * np.log10(pk[m] / rb[m]))), 2)}


def elegir_tono(artista, titulo, pua, bajo_wav):
    """Tono del bajo en el juego. tono_bajo = auto: si la canción o el artista tiene DLC oficial, su tono;
    si no, limpio (con púa: el de los Ramones, más brillante). También se puede fijar un tipo
    (limpio, limpio_pua, saturado, distorsion, fuzz) o el nombre de un tono oficial (p. ej. MotoAce_bass)."""
    info = {"pedido": TONO_MODO}
    try:
        info["rasgos"] = rasgos_saturacion(bajo_wav)
    except Exception as ex:
        info["rasgos_error"] = str(ex)[:200]
    tono, origen = None, None
    modo = TONO_MODO.strip()
    if modo.lower() in TONOS_PRESET:
        p = TONOS_PRESET[modo.lower()]; tono, origen = p, f"{modo.lower()} ({p['de']})"
    elif modo.lower() != "auto":
        tono, origen = tono_oficial(nombre=modo)
        if tono is None:
            log(T(f"  Aviso: no encuentro el tono '{modo}'; uso el automático", f"  Warning: tone '{modo}' not found; using auto"))
    if tono is None:
        tono, origen = tono_oficial(artista, titulo)
    if tono is None:
        clave = "limpio_pua" if pua else "limpio"
        tono, origen = TONOS_PRESET[clave], f"{clave} ({TONOS_PRESET[clave]['de']})"
    if IDIOMA == "en":
        origen = origen.replace("tono limpio de DLC Builder", "DLC Builder's clean tone")
    info["elegido"] = origen
    DIAG["tono"] = info
    gear = {k: v for k, v in tono["GearList"].items() if v}
    return {"GearList": gear, "ToneDescriptors": tono.get("ToneDescriptors") or ["$[35715]BASS"],
            "NameSeparator": " - ", "IsCustom": True, "Volume": str(tono.get("Volume", "-20")),
            "Key": "bass", "Name": "bass"}, origen


def volumen_rocksmith(ruta):
    """Igual que el volumen automático de DLC Builder: -16 - sonoridad integrada (LUFS)."""
    import soundfile as sf, pyloudnorm
    datos, sr = sf.read(str(ruta))
    lufs = pyloudnorm.Meter(sr).integrated_loudness(datos)
    return 0.0 if not np.isfinite(lufs) else round(-16.0 - lufs, 1)


def _normalizar(texto):
    import re, unicodedata
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = re.sub(r"\b(feat|ft|remaster(ed)?|version|videoclip|video|live|en directo)\b.*", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _parecido(a, b):
    import difflib
    a, b = _normalizar(a), _normalizar(b)
    if not a or not b:
        return 0.0
    return 1.0 if (a in b or b in a) else difflib.SequenceMatcher(None, a, b).ratio()


def _http_json(url):
    import json, urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_bytes(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def _es_recopilatorio(album):
    """Recopilatorios, directos y similares (se prefieren los discos originales)."""
    import re
    return bool(re.search(r"grandes|greatest|best of|lo mejor|esencial|essential|imprescindible|colecci|collection|recopila|"
                          r"antolog|anthology|hits|exitos|en directo|en vivo|live|directo|sus canciones|"
                          r"edicion especial|deluxe|remaster|karaoke|tribut", _normalizar(album))
                or re.fullmatch(r"(cd|disc|disco|vol|volumen|volume) ?\d*", _normalizar(album)))


def buscar_album(artista, album, anio_etiqueta=None):
    """Si las etiquetas dicen de qué disco es la canción, se busca ESE disco (artista + álbum) y no la
    canción: así la portada es la del disco que tienes, aunque sea un directo o un recopilatorio."""
    import urllib.parse, unicodedata
    q = urllib.parse.quote(f"{artista} {album}")
    diag = DIAG.setdefault("caratula", {})
    diag["busqueda_disco"] = f"{artista} {album}"
    llano = lambda x: unicodedata.normalize("NFKD", x or "").encode("ascii", "ignore").decode().lower().strip()
    try:
        cands = [r for r in _http_json(f"https://itunes.apple.com/search?term={q}&entity=album&limit=25&country=ES").get("results", [])
                 if _parecido(r.get("artistName"), artista) >= 0.8 and _parecido(r.get("collectionName"), album) >= 0.85
                 and r.get("artworkUrl100")]
        diag["itunes_discos"] = [f'{r.get("collectionName")} ({(r.get("releaseDate") or "")[:4]})' for r in cands]
        if cands:
            # el que se llama exactamente igual, y si hay varias ediciones, la del año de las etiquetas
            r = min(cands, key=lambda r: (llano(r.get("collectionName")) != llano(album),
                                          anio_etiqueta is not None and (r.get("releaseDate") or "")[:4] != str(anio_etiqueta),
                                          r.get("releaseDate") or "9999"))
            anio = (r.get("releaseDate") or "")[:4]
            diag["elegida"] = f"iTunes (disco): {r.get('collectionName')} ({anio})"
            return {"fuente": "iTunes", "url": r["artworkUrl100"].replace("100x100bb", "600x600bb"),
                    # el nombre del disco, el de tus etiquetas (la tienda a veces lo censura: "M****a")
                    "album": album, "year": int(anio) if anio.isdigit() else None}
    except Exception as ex:
        diag["itunes_disco_error"] = str(ex)[:200]
    try:
        for r in _http_json(f"https://api.deezer.com/search/album?q={q}&limit=10").get("data", []):
            if _parecido(r["artist"]["name"], artista) >= 0.8 and _parecido(r["title"], album) >= 0.85 and r.get("cover_xl"):
                anio = None
                try:
                    fecha = _http_json(f"https://api.deezer.com/album/{r['id']}").get("release_date", "")
                    anio = int(fecha[:4]) if fecha[:4].isdigit() else None
                except Exception:
                    pass
                diag["elegida"] = f"Deezer (disco): {r.get('title')} ({anio})"
                return {"fuente": "Deezer", "url": r["cover_xl"], "album": album, "year": anio}
    except Exception as ex:
        diag["deezer_disco_error"] = str(ex)[:200]
    return None


def buscar_caratula(artista, titulo):
    """Busca la canción en iTunes y, si no, en Deezer. Exige que coincidan artista y título.
    Devuelve {fuente, url, album, year} o None (sin conexión o sin coincidencia)."""
    import re, urllib.parse
    q = urllib.parse.quote(f"{artista} {titulo}")
    diag = DIAG.setdefault("caratula", {"busqueda": f"{artista} {titulo}"})
    try:
        candidatos = []
        for r in _http_json(f"https://itunes.apple.com/search?term={q}&entity=song&limit=25&country=ES").get("results", []):
            if _parecido(r.get("artistName"), artista) >= 0.8 and _parecido(r.get("trackName"), titulo) >= 0.7 \
                    and r.get("artworkUrl100"):
                candidatos.append(r)
        diag["itunes_coincidencias"] = [
            {"album": r.get("collectionName"), "fecha": (r.get("releaseDate") or "")[:10], "discos": r.get("discCount"),
             "pistas": r.get("trackCount"), "recopilatorio": _es_recopilatorio(r.get("collectionName", ""))}
            for r in candidatos]
        if candidatos:
            # el disco original: primero los que no son recopilatorios/directos, y de ellos el más antiguo
            # desempate: un solo disco y menos pistas = disco original (las cajas y recopilatorios son más largos)
            r = min(candidatos, key=lambda r: (_es_recopilatorio(r.get("collectionName", ""))
                                                or "various" in _normalizar(r.get("collectionArtistName", "")),
                                                bool(re.search(r"\b(ep|single)\b", _normalizar(r.get("collectionName", "")))),
                                                r.get("releaseDate") or "9999",
                                                (r.get("discCount") or 1) > 1,
                                                r.get("trackCount") or 99))
            anio = (r.get("releaseDate") or "")[:4]
            diag["elegida"] = f"iTunes: {r.get('collectionName')} ({anio})"
            return {"fuente": "iTunes", "url": r["artworkUrl100"].replace("100x100bb", "600x600bb"),
                    "album": r.get("collectionName") or "", "year": int(anio) if anio.isdigit() else None}
    except Exception as ex:
        diag["itunes_error"] = str(ex)[:200]
    try:
        for r in _http_json(f"https://api.deezer.com/search?q={q}&limit=10").get("data", []):
            if _parecido(r["artist"]["name"], artista) >= 0.8 and _parecido(r["title"], titulo) >= 0.7 \
                    and r.get("album", {}).get("cover_xl"):
                anio = None
                try:
                    fecha = _http_json(f"https://api.deezer.com/album/{r['album']['id']}").get("release_date", "")
                    anio = int(fecha[:4]) if fecha[:4].isdigit() else None
                except Exception:
                    pass
                diag["elegida"] = f"Deezer: {r['album'].get('title')} ({anio})"
                return {"fuente": "Deezer", "url": r["album"]["cover_xl"], "album": r["album"].get("title") or "",
                        "year": anio}
    except Exception as ex:
        diag["deezer_error"] = str(ex)[:200]
    diag["elegida"] = None
    return None


def crear_portada(ruta_audio, destino, artista, titulo, caratula=None):
    """Portada 512x512 PNG: la de internet si se encontró, si no la incrustada en el audio
    (recortada a cuadrado), y si tampoco hay, una generada. Devuelve (ruta, origen)."""
    from PIL import Image, ImageDraw, ImageFont
    import io
    img, origen = None, T("generada", "generated")
    if caratula:
        try:
            img = Image.open(io.BytesIO(_http_bytes(caratula["url"]))).convert("RGB")
            origen = f"{T('de', 'from')} {caratula['fuente']}"
        except Exception:
            img = None
    try:
        if img is not None:
            raise StopIteration
        import mutagen
        f = mutagen.File(str(ruta_audio))
        datos = None
        if f is not None and f.tags is not None:
            for k in f.tags.keys():
                if k.startswith("APIC"):
                    datos = f.tags[k].data; break
            if datos is None and hasattr(f, "pictures") and f.pictures:
                datos = f.pictures[0].data
            if datos is None and "covr" in f.tags:
                datos = bytes(f.tags["covr"][0])
        if datos:
            img = Image.open(io.BytesIO(datos)).convert("RGB")
            origen = T("incrustada en el mp3", "embedded in the mp3")
    except StopIteration:
        pass
    except Exception:
        img = None
    if img is not None:
        w, h = img.size; lado = min(w, h)
        img = img.crop(((w - lado) // 2, (h - lado) // 2, (w + lado) // 2, (h + lado) // 2)).resize((512, 512))
    else:
        semilla = sum(map(ord, artista + titulo))
        c1 = np.array([40 + semilla % 80, 30 + (semilla // 7) % 60, 70 + (semilla // 13) % 100])
        c2 = c1[::-1] // 2
        t = np.linspace(0, 1, 512)[:, None, None]
        img = Image.fromarray(np.repeat((c1 * (1 - t) + c2 * t).astype(np.uint8), 512, axis=1))
        d = ImageDraw.Draw(img)
        try:
            fuente_g, fuente_p = ImageFont.load_default(size=44), ImageFont.load_default(size=30)
        except TypeError:
            fuente_g = fuente_p = ImageFont.load_default()
        def centrado(texto, y, fuente):
            texto = texto if len(texto) <= 22 else texto[:21] + "…"
            ancho = d.textlength(texto, font=fuente)
            d.text(((512 - ancho) / 2, y), texto, fill=(240, 240, 240), font=fuente)
        centrado(titulo, 200, fuente_g); centrado(artista, 270, fuente_p)
    img.save(destino, "PNG")
    return destino, origen


def escribir_preview(ogg, destino, duracion):
    """Vista previa de 28 s del tramo con más energía (como la de DLC Builder), con fundidos."""
    import librosa
    y, sr = librosa.load(str(ogg), sr=11025, mono=True)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=1024)[0]
    t = librosa.times_like(rms, sr=sr, hop_length=1024)
    ventana = int(28 * sr / 1024)
    energia = np.convolve(rms, np.ones(ventana), mode="valid")
    validos = (t[:len(energia)] > 10) & (t[:len(energia)] < duracion - 30)
    inicio = float(t[:len(energia)][validos][np.argmax(energia[validos])]) if validos.any() else 0.0
    ffmpeg("-ss", f"{inicio:.2f}", "-t", "28", "-i", str(ogg),
           "-af", "afade=t=in:st=0:d=2.5,afade=t=out:st=25.5:d=2.5", "-c:a", "libvorbis", "-q:a", "5", str(destino))
    return inicio


def tiempo_de_slot(completo, s):
    """Instante (s) de la semicorchea s (coordenadas del grid, sin COUNT) en el audio con silencio."""
    b = s / 4 + 4
    i = int(np.clip(np.floor(b), 0, len(completo) - 2))
    return float(completo[i] + (b - i) * (completo[i + 1] - completo[i]))


def calcular_anclas(eventos):
    """Posiciones de la mano (anchors): traste del dedo índice, ancho 4. eventos: [(tiempo, traste)]."""
    trastes = [f for _, f in eventos if f > 0]
    if not trastes:
        return [(eventos[0][0], 1)] if eventos else []
    actual = max(1, min(trastes[:8]))
    anclas = [(eventos[0][0], actual)]
    for t, f in eventos:
        if f == 0:
            continue
        if f < actual:
            actual = f
        elif f > actual + 3:
            actual = max(1, f - 3)
        else:
            continue
        anclas.append((t, actual))
    return anclas


NIVELES_DD = ["un golpe por compás", "uno por medio compás", "uno por tiempo", "corcheas", "completa"]


def niveles_dd(tab, compases, completo):
    """Dificultad dinámica propia, igual en toda la canción y basada en el pulso:
    nivel 0 = una nota por compás (la del 1, o la primera si el 1 va vacío), 1 = una por medio compás,
    2 = una por tiempo, 3 = una por corchea, 4 = todas. Así lo sencillo sigue el ritmo de la canción.
    Devuelve, para cada nota de tab, el nivel mínimo en el que aparece."""
    inicios = np.array([b for b, _ in compases])
    nivel = np.full(len(tab), 4)
    compas_de = np.zeros(len(tab), dtype=int)
    grupos = {}
    for k, n in enumerate(tab):
        bi = n[0] / 4 + 4                       # posición en beats del audio (con COUNT)
        c = int(np.clip(np.searchsorted(inicios, bi + 1e-6, side="right") - 1, 0, len(compases) - 1))
        b, nb = compases[c]
        compas_de[k] = c
        pos = int(round((bi - b) * 4))          # semicorchea dentro del compás
        unidades = {0: nb * 4, 1: (nb * 2 if nb % 2 == 0 else nb * 4), 2: 4, 3: 2}
        for d, u in unidades.items():
            clave = (d, c, pos // u)
            # importancia: estar al principio de la unidad; si no, la que caiga en el pulso más fuerte
            fuerza = 0 if pos % u == 0 else (1 if pos % 4 == 0 else (2 if pos % 2 == 0 else 3))
            mejor = grupos.get(clave)
            if mejor is None or (fuerza, n[0]) < mejor[0]:
                grupos[clave] = ((fuerza, n[0]), k)
    for (d, _, _), (_, k) in grupos.items():
        nivel[k] = min(nivel[k], d)
    return nivel, compas_de


def escribir_xml_rs(ruta, completo, compases, tab, cuerdas, cents, pua, meta, duracion_audio, principal=True):
    from xml.sax.saxutils import escape
    E = lambda x: escape(str(x), {'"': "&quot;"})
    offsets = [c - base for c, base in zip(cuerdas, [28, 33, 38, 43])]
    estandar = int(all(o == 0 for o in offsets))
    tab = sorted(tab, key=lambda n: n[0])
    notas = []
    for s0, s1, _, cuerda_gp, traste in tab:
        t0, t1 = tiempo_de_slot(completo, s0), tiempo_de_slot(completo, s1)
        cuerda = 4 - cuerda_gp            # XML: 0 = la más grave
        sustain = (t1 - t0) if (s1 - s0) >= 4 else 0.0
        notas.append((t0, cuerda, traste, sustain))
    anclas = calcular_anclas([(t, f) for t, _, f, _ in notas])
    beats = completo
    t_count, t_musica = beats[0], beats[4]
    ultima = max(t + max(sus, 0.05) for t, _, _, sus in notas)
    inicios = [b for b, _ in compases] + [compases[-1][0] + compases[-1][1]]
    t_end = next((beats[b] for b in inicios if beats[b] > ultima + 0.05), beats[-1])
    if t_end >= duracion_audio - 0.01:
        t_end = min(ultima + 0.5, duracion_audio - 0.1)
    medida = {b: i + 1 for i, b in enumerate(inicios)}
    tempo_medio = 60.0 / float(np.median(np.diff(beats)))
    L = []
    w = L.append
    w("<?xml version='1.0' encoding='UTF-8'?>")
    w('<song version="7">')
    w(f"<!-- auto-cdlc {VERSION} -->")
    w(f"  <title>{E(meta['titulo'])}</title>")
    w("  <arrangement>Bass</arrangement>")
    w("  <part>1</part>")
    w("  <offset>0.000</offset>")
    w(f"  <centOffset>{int(round(cents))}</centOffset>")
    w(f"  <songLength>{duracion_audio:.3f}</songLength>")
    w(f"  <lastConversionDateTime>{time.strftime('%m-%d-%y %H:%M')}</lastConversionDateTime>")
    w(f"  <startBeat>{t_count:.3f}</startBeat>")
    w(f"  <averageTempo>{tempo_medio:.3f}</averageTempo>")
    w('  <tuning ' + ' '.join(f'string{i}="{offsets[i] if i < 4 else 0}"' for i in range(6)) + ' />')
    w("  <capo>0</capo>")
    w(f"  <artistName>{E(meta['artista'])}</artistName>")
    w(f"  <artistNameSort>{E(meta['artista'])}</artistNameSort>")
    w(f"  <albumName>{E(meta['album'])}</albumName>")
    w(f"  <albumYear>{meta['year']}</albumYear>")
    w("  <crowdSpeed>1</crowdSpeed>")
    w(f'  <arrangementProperties represent="{int(principal)}" bonusArr="0" standardTuning="{estandar}" nonStandardChords="0" '
      'barreChords="0" powerChords="0" dropDPower="0" openChords="0" fingerPicking="0" pickDirection="0" '
      'doubleStops="0" palmMutes="0" harmonics="0" pinchHarmonics="0" hopo="0" tremolo="0" slides="0" '
      'unpitchedSlides="0" bends="0" tapping="0" vibrato="0" fretHandMutes="0" slapPop="0" twoFingerPicking="0" '
      f'fifthsAndOctaves="0" syncopation="0" bassPick="{int(pua)}" sustain="1" pathLead="0" pathRhythm="0" pathBass="1" />')
    # ---- frases y niveles de dificultad ----
    if DD_MODO == "dlcbuilder":
        # una sola frase musical: DLC Builder crea las frases y la DD a su manera
        frases = [("COUNT", 0), ("riff", 0), ("END", 0)]
        iteraciones = [(t_count, 0), (t_musica, 1), (t_end, 2)]
        secciones = [t_musica]
        niveles = [notas]
        nivel_frase = None
    else:
        # frases de 4 compases (8 si la canción es muy larga; Rocksmith admite 100)
        compases_musica = [b for b, _ in compases[1:] if beats[b] < t_end - 0.05]
        paso = 4 if len(compases_musica) / 4 <= 96 else 8

        def firmas_de(bl):
            lim_ = [beats[x] for x in bl] + [t_end]
            out = []
            for k in range(len(bl)):
                s0 = (bl[k] - 4) * 4
                out.append({(int(n[0] - s0), int(n[2])) for n, nt in zip(tab, notas)
                            if lim_[k] - 1e-4 <= nt[0] < lim_[k + 1] - 1e-4})
            return out

        def distintas(fs):
            reps = []
            for f in fs:
                if not any((not f and not g) or (f and g and sum(1 for a_, b_ in f if any((a_ + d, b_) in g for d in (-1, 0, 1)))
                                                 / max(len(f), len(g)) >= 0.8) for g in reps):
                    reps.append(f)
            return len(reps)

        # Las estrofas no siempre empiezan en el compás 1, 5, 9...: se prueba a desplazar el corte de las
        # frases 0-3 compases y se queda el que más repeticiones encuentra (más progreso compartido)
        opciones = []
        for o in range(paso):
            bl = compases_musica[::paso] if o == 0 else [compases_musica[0]] + compases_musica[o::paso]
            fs = firmas_de(bl)
            opciones.append((distintas(fs) / max(len(fs), 1), o, bl))
        _, desplazamiento, bloques = min(opciones, key=lambda x: (x[0], x[1]))
        if principal:
            DIAG.setdefault("frases", {})["desplazamiento_compases"] = desplazamiento
        cortes = [beats[b] for b in bloques]
        cortes[0] = t_musica
        lim = cortes + [t_end]
        if DD_MODO == "propia":
            nivel_nota, compas_nota = niveles_dd(tab, compases, completo)
        else:
            nivel_nota, compas_nota = np.full(len(notas), 0), np.zeros(len(notas), dtype=int)
        frases, iteraciones, firmas = [("COUNT", 0)], [(t_count, 0)], {}
        conjuntos_por_iter = []
        for k in range(len(cortes)):
            idx = [i for i, n in enumerate(notas) if lim[k] - 1e-4 <= n[0] < lim[k + 1] - 1e-4]
            # Versiones de la frase de más fácil a completa, como en las canciones oficiales: se empieza con
            # muy pocas notas y se van añadiendo poco a poco. Cada paso rítmico (compás, medio compás,
            # tiempo, corchea, semicorchea) se parte en dos: primero entran las notas nuevas de los
            # compases 1 y 3 de la frase y luego las de los compases 2 y 4 (como hace DDC). Hasta 10 niveles.
            versiones = []
            c0 = min((compas_nota[i] for i in idx), default=0)
            pasos = []
            for d in range(len(NIVELES_DD)) if DD_MODO == "propia" else [0]:
                pasos.append(lambda i, d=d: nivel_nota[i] < d or (nivel_nota[i] == d and (compas_nota[i] - c0) % 2 == 0))
                pasos.append(lambda i, d=d: nivel_nota[i] <= d)
            for cond in pasos:
                v = [i for i in idx if cond(i)]
                if v and (not versiones or v != versiones[-1]):
                    versiones.append(v)
            if DD_INICIAL > 0 and versiones:
                # dificultad inicial: se quitan los niveles con menos notas que el % pedido de la frase
                minimo = DD_INICIAL / 100 * len(versiones[-1])
                versiones = [v for v in versiones[:-1] if len(v) >= minimo] + [versiones[-1]]
            if not versiones:
                versiones = [[]]
            # frases que se repiten (estribillo, estrofa...) comparten nombre y Rocksmith suma su progreso.
            # Se comparan con tolerancia: la transcripción nunca sale idéntica en dos repeticiones.
            slot0 = (bloques[k] - 4) * 4
            firma = {(int(tab[i][0] - slot0), int(tab[i][2])) for i in idx}
            pid = None
            for ref, (fid, _) in firmas.items():
                otra = set(ref)
                if not firma and not otra:
                    pid = fid; break
                if firma and otra:
                    # misma nota con una semicorchea de margen: la transcripción de dos repeticiones nunca
                    # sale clavada (una nota que cae en el "y" en una vuelta y en la "a" en la otra)
                    iguales = sum(1 for s_, p_ in firma if any((s_ + d, p_) in otra for d in (-1, 0, 1)))
                    if iguales / max(len(firma), len(otra)) >= 0.8:
                        pid = fid; break
            if pid is None:
                pid = len(frases)
                firmas[frozenset(firma)] = (pid, None)
                frases.append((f"p{len(frases)}", len(versiones) - 1))
            else:
                nombre, maxd = frases[pid]
                frases[pid] = (nombre, max(maxd, len(versiones) - 1))
            iteraciones.append((lim[k], pid))
            conjuntos_por_iter.append(versiones)
        frases.append(("END", 0)); iteraciones.append((t_end, len(frases) - 1))
        n_niveles = max(len(v) for v in conjuntos_por_iter)
        niveles = []
        for d in range(n_niveles):
            sel = sorted(i for v in conjuntos_por_iter for i in v[min(d, len(v) - 1)])
            nivel_notas = []
            for j, i in enumerate(sel):
                t, cu, f, sus = notas[i]
                if d < n_niveles - 1 and len(sel) < 0.45 * len(notas) and j + 1 < len(sel):
                    # en los niveles de pocas notas, la nota se mantiene hasta la siguiente (máx. medio compás)
                    hueco = notas[sel[j + 1]][0] - t
                    medio = 2 * 60.0 / max(tempo_medio_aprox(beats, t), 1)
                    if hueco > 0.4:
                        sus = max(sus, min(hueco - 0.1, medio))
                nivel_notas.append((t, cu, f, sus))
            niveles.append(nivel_notas)
        secciones = [lim[k] for k in range(0, len(cortes), 2)]
        nivel_frase = [len(v) - 1 for v in conjuntos_por_iter]
    w(f'  <phrases count="{len(frases)}">')
    for nombre, maxd in frases:
        w(f'    <phrase name="{nombre}" maxDifficulty="{maxd}" />')
    w("  </phrases>")
    w(f'  <phraseIterations count="{len(iteraciones)}">')
    for t, pid in iteraciones:
        maxd = frases[pid][1]
        if maxd == 0:
            w(f'    <phraseIteration time="{t:.3f}" phraseId="{pid}"/>')
            continue
        # niveles "héroe" (fácil/medio/difícil): el difícil es el máximo de la frase. Sin ellos el juego
        # cree que el nivel 0 ya es el máximo (100 % de dominio al momento y puntuación mal contada)
        facil, medio = (maxd, maxd) if maxd == 1 else (int(maxd / 4 + 0.5), int(maxd / 2 + 0.5))
        w(f'    <phraseIteration time="{t:.3f}" phraseId="{pid}">')
        w('      <heroLevels count="3">')
        for heroe, dif in ((1, facil), (2, medio), (3, maxd)):
            w(f'        <heroLevel hero="{heroe}" difficulty="{dif}"/>')
        w("      </heroLevels>")
        w("    </phraseIteration>")
    w("  </phraseIterations>")
    for etiqueta in ("newLinkedDiffs", "linkedDiffs", "phraseProperties", "chordTemplates", "fretHandMuteTemplates"):
        w(f'  <{etiqueta} count="0"/>')
    w(f'  <ebeats count="{len(beats)}">')
    for i, t in enumerate(beats):
        w(f'    <ebeat time="{t:.3f}" measure="{medida[i]}" />' if i in medida else f'    <ebeat time="{t:.3f}" />')
    w("  </ebeats>")
    w(f'  <sections count="{len(secciones)}">')
    for k, t in enumerate(secciones, 1):
        w(f'    <section name="riff" number="{k}" startTime="{t:.3f}"/>')
    w("  </sections>")
    eventos, previo = [], None
    for b, n in compases:
        if n != previo:
            eventos.append((beats[b], f"TS:{n}/4")); previo = n
    w(f'  <events count="{len(eventos)}">')
    for t, code in eventos:
        w(f'    <event time="{t:.3f}" code="{code}"/>')
    w("  </events>")
    w('  <transcriptionTrack difficulty="-1">')
    for etiqueta in ("notes", "chords", "anchors", "handShapes"):
        w(f'      <{etiqueta} count="0"/>')
    w("  </transcriptionTrack>")
    w(f'  <levels count="{len(niveles)}">')
    for d, nivel_notas in enumerate(niveles):
        anclas_d = calcular_anclas([(t, f) for t, _, f, _ in nivel_notas]) or [(t_musica, 1)]
        w(f'    <level difficulty="{d}">')
        w(f'      <notes count="{len(nivel_notas)}">')
        for t, cuerda, traste, sus in nivel_notas:
            extra = f' sustain="{sus:.3f}"' if sus > 0 else ""
            w(f'        <note time="{t:.3f}" string="{cuerda}" fret="{traste}"{extra} />')
        w("      </notes>")
        w('      <chords count="0"/>')
        w('      <fretHandMutes count="0"/>')
        w(f'      <anchors count="{len(anclas_d)}">')
        for t, f in anclas_d:
            w(f'        <anchor time="{t:.3f}" fret="{f}" width="4.000"/>')
        w("      </anchors>")
        w('      <handShapes count="0"/>')
        w("    </level>")
    w("  </levels>")
    w("</song>")
    Path(ruta).write_text("\n".join(L) + "\n", encoding="utf-8")
    DIAG["dificultad" if principal else "dificultad_arreglo_simple"] = {"modo": DD_MODO, "inicial_pct": DD_INICIAL, "niveles": len(niveles),
                          "notas_por_nivel": [len(n) for n in niveles],
                          "frases_distintas": len(frases) - 2, "repeticiones_de_frase": len(iteraciones) - 2,
                          "secciones": len(secciones),
                          "niveles_por_frase": " ".join(str(x) for x in nivel_frase) if nivel_frase else None}
    return {"notas": notas, "anclas": anclas, "t_count": t_count, "t_musica": t_musica, "t_end": t_end,
            "niveles": [len(n) for n in niveles], "frases": len(iteraciones) - 2}


def tempo_medio_aprox(beats, t):
    i = int(np.clip(np.searchsorted(beats, t), 1, len(beats) - 1))
    return 60.0 / max(beats[i] - beats[i - 1], 1e-3)


# ---------------- letra (arreglo de voz) ----------------
LETRA_CHARSET = set(""" !"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_abcdefghijklmnopqrstuvwxyz{|}~¡¢¥¦§¨ª«°²³´•¸¹º»¼½¾¿ÀÁÂÄÅÆÇÈÉÊËÌÎÏÑÒÓÔÖØÙÚÛÜÞßàáâäåæçèéêëìíîïñòóôöøùúûüŒœŠšž„…€™""")


def _limpiar_letra(palabra):
    """Solo caracteres que tiene la fuente de letras de Rocksmith (la Í, las comillas tipográficas... no)."""
    import unicodedata
    cambios = {"’": "'", "‘": "'", "´": "'", "“": '"', "”": '"', "«": '"', "»": '"', "—": "-", "–": "-"}
    out = ""
    for ch in palabra:
        ch = cambios.get(ch, ch)
        if ch not in LETRA_CHARSET:
            ch = "".join(c for c in unicodedata.normalize("NFD", ch) if c in LETRA_CHARSET)
        out += ch
    while len(out.encode("utf-8")) > 46:
        out = out[:-1]
    return out


def buscar_letra(artista, titulo, album, duracion):
    """Letra sincronizada por líneas (formato LRC) de LRCLIB, una base libre de letras. Solo vale si la
    duración coincide con la del mp3 (+-2 s): cada versión de una canción tiene sus tiempos."""
    import json, urllib.parse, urllib.request
    ua = {"User-Agent": UA}

    def pedir(ruta, **params):
        url = "https://lrclib.net/api/" + ruta + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v})
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=15) as r:
                return json.load(r)
        except Exception:
            return None
        finally:
            time.sleep(0.3)

    titulo_corto = re.sub(r"\s*[\(\[].*?[\)\]]", "", titulo).strip() or titulo
    dur = int(round(duracion))
    intentos = []
    for t in dict.fromkeys([titulo, titulo_corto]):
        for alb in ([album, None] if album else [None]):
            r = pedir("get", track_name=t, artist_name=artista, album_name=alb, duration=dur)
            intentos.append(f"get '{t}'" + (f" / '{alb}'" if alb else ""))
            if r and r.get("syncedLyrics"):
                return r, intentos
    for t in dict.fromkeys([titulo, titulo_corto]):
        res = pedir("search", track_name=t, artist_name=artista) or []
        intentos.append(f"search '{t}'")
        buenos = [x for x in res if x.get("syncedLyrics") and x.get("duration")
                  and abs(float(x["duration"]) - duracion) <= 2.0]
        if buenos:
            return min(buenos, key=lambda x: abs(float(x["duration"]) - duracion)), intentos
    return None, intentos


def escribir_letra(ruta, lrc, desplazamiento, fin_cancion):
    """Arreglo de voz de Rocksmith a partir del LRC. El LRC solo da cuándo empieza cada línea: las palabras
    se reparten dentro de la línea según su largo (cantadas a un ritmo normal, no estiradas hasta la línea
    siguiente). Devuelve el número de líneas."""
    from xml.sax.saxutils import quoteattr
    lineas = []
    for l in lrc.splitlines():
        marcas = re.findall(r"\[(\d+):(\d+(?:\.\d+)?)\]", l)
        texto = re.sub(r"\[[^\]]*\]", "", l).strip()
        for mm, ss in marcas:
            lineas.append((int(mm) * 60 + float(ss) + desplazamiento, texto))
    lineas.sort()
    vocales = []
    lineas = [x for x in lineas if 0 <= x[0] < fin_cancion - 0.5]
    for k, (t, texto) in enumerate(lineas):
        palabras = [w for w in (_limpiar_letra(p) for p in texto.split()) if w]
        if not palabras:
            continue
        fin = lineas[k + 1][0] if k + 1 < len(lineas) else min(t + 6.0, fin_cancion)
        hueco = max(0.2, fin - t - 0.1)
        pesos = np.array([len(w) + 2 for w in palabras], dtype=float)
        largo = min(hueco, pesos.sum() * 0.075 + 0.4)       # ~ 3 sílabas por segundo
        bordes = t + largo * np.concatenate([[0], np.cumsum(pesos) / pesos.sum()])
        for j, w in enumerate(palabras):
            dur = max(0.05, (bordes[j + 1] - bordes[j]) * 0.9)
            vocales.append((float(bordes[j]), dur, w + ("+" if j == len(palabras) - 1 else "")))
    if not vocales:
        return 0
    L = ["<?xml version='1.0' encoding='UTF-8'?>", f'<vocals count="{len(vocales)}">']
    L += [f'  <vocal time="{t:.3f}" note="254" length="{d:.3f}" lyric={quoteattr(w)} />' for t, d, w in vocales]
    L.append("</vocals>")
    Path(ruta).write_text("\n".join(L) + "\n", encoding="utf-8")
    return sum(1 for _, _, w in vocales if w.endswith("+"))


def tab_simplificada(tab, compases, completo, nivel_max):
    """Para el arreglo alternativo: solo las notas de los niveles rítmicos hasta nivel_max (0 = una por
    compás, 1 = medio compás, 2 = una por tiempo, 3 = corcheas). Cada nota se mantiene hasta la siguiente
    (como mucho medio compás) para que el bajo no quede a saltos."""
    nivel, _ = niveles_dd(tab, compases, completo)
    sel = sorted((n for n, d in zip(tab, nivel) if d <= nivel_max), key=lambda n: n[0])
    out = []
    for k, (s0, s1, p, cu, tr) in enumerate(sel):
        sig = sel[k + 1][0] if k + 1 < len(sel) else s1
        if sig - s1 > 1:
            s1 = max(s1, min(sig - 1, s0 + 8))
        out.append((s0, s1, p, cu, tr))
    return out


def escribir_proyecto(ruta, meta, xml, ogg, preview, inicio_preview, portada, cuerdas, cents, pua, tono=None,
                      xml_simple=None, xml_letra=None, velocidad=None):
    import json, uuid, zlib
    clave = "cb" + (StringValidator_dlckey(a_ascii(meta["artista"]))[:5] + StringValidator_dlckey(a_ascii(meta["titulo"]))[:5])
    if len(clave) < 5:
        clave += "xxxxx"[:5 - len(clave)]
    semilla = zlib.crc32(clave.encode())
    offsets = [c - base for c, base in zip(cuerdas, [28, 33, 38, 43])] + [0, 0]
    proyecto = {
        "Version": "1",
        "DLCKey": clave,
        "ArtistName": {"Value": meta["artista"], "SortValue": a_ascii(meta["artista"])},
        "Title": {"Value": meta["titulo"], "SortValue": a_ascii(meta["titulo"])},
        "AlbumName": {"Value": meta["album"], "SortValue": a_ascii(meta["album"])},
        "Year": int(meta["year"]),
        "AlbumArtFile": Path(portada).name,
        "AudioFile": {"Path": Path(ogg).name, "Volume": volumen_rocksmith(ogg)},
        "AudioPreviewFile": {"Path": Path(preview).name, "Volume": volumen_rocksmith(preview)},
        "AudioPreviewStartTime": round(inicio_preview, 3),
        "Arrangements": [{
            "Case": "Instrumental",
            "Fields": [{
                "XML": Path(xml).name,
                "Name": 3, "RouteMask": 4, "Priority": 0, "ScrollSpeed": velocidad or VELOCIDAD_SCROLL,
                "BassPicked": bool(pua),
                "Tuning": offsets,
                "TuningPitch": round(440 * 2 ** (cents / 1200), 2),
                "BaseTone": "bass", "Tones": [],
                "MasterID": int(semilla % 2_000_000_000) + 1,
                "PersistentID": str(uuid.UUID(int=(semilla << 96) | (semilla << 32) | 0xC0FFEE)),
            }],
        }],
        "Tones": [tono or TONO_BAJO],
    }
    bajo = proyecto["Arrangements"][0]["Fields"][0]
    if xml_simple:
        # arreglo alternativo ("Alt. Bass" en el juego): mismos datos, otro XML, otros identificadores
        s2 = zlib.crc32((clave + "simple").encode())
        proyecto["Arrangements"].append({"Case": "Instrumental", "Fields": [{
            **bajo, "XML": Path(xml_simple).name, "Priority": 1,
            "MasterID": int(s2 % 2_000_000_000) + 1,
            "PersistentID": str(uuid.UUID(int=(s2 << 96) | (s2 << 32) | 0xC0FFEE))}]})
    if xml_letra:
        s3 = zlib.crc32((clave + "letra").encode())
        proyecto["Arrangements"].append({"Case": "Vocals", "Fields": [{
            "XML": Path(xml_letra).name, "Japanese": False, "CustomFont": None,
            "MasterID": int(s3 % 2_000_000_000) + 1,
            "PersistentID": str(uuid.UUID(int=(s3 << 96) | (s3 << 32) | 0xC0FFEE))}]})
    Path(ruta).write_text(json.dumps(proyecto, ensure_ascii=False, indent=2), encoding="utf-8")
    return proyecto


def comprobar_dlc_builder(proyecto_path):
    """Repite las comprobaciones de DLC Builder (BuildValidator + InstrumentalChecker) sobre lo generado.
    Devuelve la lista de problemas (vacía si todo pasaría)."""
    import json, xml.etree.ElementTree as ET
    problemas = []
    base = Path(proyecto_path).parent
    pr = json.loads(Path(proyecto_path).read_text(encoding="utf-8"))
    if len(pr.get("DLCKey", "")) < 5: problemas.append("DLCKey demasiado corta")
    if not pr["Title"]["Value"]: problemas.append("título vacío")
    if not pr["ArtistName"]["Value"]: problemas.append("artista vacío")
    for campo in ("AlbumArtFile",):
        if not (base / pr[campo]).exists(): problemas.append(f"falta {pr[campo]}")
    for campo in ("AudioFile", "AudioPreviewFile"):
        if not (base / pr[campo]["Path"]).exists(): problemas.append(f"falta {pr[campo]['Path']}")
    tonos = {t["Key"] for t in pr["Tones"]}
    arr = pr["Arrangements"][0]["Fields"][0]
    if arr["BaseTone"] not in tonos: problemas.append("el tono base no existe")
    if len(arr["Tuning"]) != 6: problemas.append("afinación mal formada")
    raiz = ET.parse(base / arr["XML"]).getroot()
    tiempo = lambda e, a="time": round(float(e.get(a)) * 1000)
    frases = [p.get("name") for p in raiz.find("phrases")]
    iters = [(tiempo(i), int(i.get("phraseId"))) for i in raiz.find("phraseIterations")]
    notas = [(tiempo(n), int(n.get("string")), int(n.get("fret")), float(n.get("sustain", 0)))
             for n in raiz.find("levels")[0].find("notes")]
    anclas = [tiempo(a) for a in raiz.find("levels")[0].find("anchors")]
    beats = [tiempo(b) for b in raiz.find("ebeats")]
    if not notas: problemas.append("no hay notas")
    else:
        if len(iters) >= 2 and notas[0][0] < iters[1][0]: problemas.append("la primera frase contiene notas")
        if "END" not in [f.upper() for f in frases]: problemas.append("falta la frase END")
        fin = next((t for t, pid in iters if frases[pid].upper() == "END"), None)
        if fin is not None and any(t >= fin for t, *_ in notas): problemas.append("hay notas después de END")
        if any(not 0 <= c <= 3 for _, c, _, _ in notas): problemas.append("cuerda fuera del bajo de 4")
        if any(f > 24 for _, _, f, _ in notas): problemas.append("traste mayor que 24")
        if not anclas or anclas[0] > notas[0][0]: problemas.append("falta posición de mano al empezar")
        if notas[-1][0] / 1000 >= float(raiz.findtext("songLength")): problemas.append("notas más allá del final")
    if len(iters) > 100: problemas.append("más de 100 frases")
    if any(b2 <= b1 for b1, b2 in zip(beats, beats[1:])): problemas.append("beats desordenados")
    if any(t2 < t1 for (t1, _), (t2, _) in zip(iters, iters[1:])): problemas.append("frases desordenadas")
    return problemas


def StringValidator_dlckey(texto):
    import re
    return re.sub(r"[^0-9a-zA-Z]", "", texto or "")


def info_audio(ruta):
    """Formato del archivo de entrada (para saber si la calidad de origen limita el resultado)."""
    try:
        import mutagen
        f = mutagen.File(str(ruta))
        i = f.info
        return {"formato": type(f).__name__, "duracion_s": round(float(i.length), 1),
                "kbps": round(getattr(i, "bitrate", 0) / 1000) or None,
                "hz": getattr(i, "sample_rate", None), "canales": getattr(i, "channels", None),
                "tamaño_kb": round(Path(ruta).stat().st_size / 1024)}
    except Exception as ex:
        return {"error": str(ex)[:200]}


def sonoridades(mezcla, bajo):
    """LUFS de la mezcla y del bajo separado: cuanto más bajo el bajo respecto a la mezcla, más difícil."""
    try:
        import soundfile as sf, pyloudnorm
        out = {}
        for nombre, ruta in (("mezcla_lufs", mezcla), ("bajo_lufs", bajo)):
            d, sr = sf.read(str(ruta))
            v = pyloudnorm.Meter(sr).integrated_loudness(d)
            out[nombre] = round(float(v), 1) if np.isfinite(v) else None
        if out["mezcla_lufs"] is not None and out["bajo_lufs"] is not None:
            out["bajo_respecto_mezcla_db"] = round(out["bajo_lufs"] - out["mezcla_lufs"], 1)
        return out
    except Exception as ex:
        return {"error": str(ex)[:200]}


def versiones():
    import importlib.metadata as md, platform
    v = {"auto-cdlc": VERSION, "python": platform.python_version(), "sistema": platform.platform()}
    for paquete in ("numpy", "scipy", "librosa", "madmom", "audio-separator", "onnxruntime", "torch",
                    "PyGuitarPro", "pyloudnorm", "pillow"):
        try:
            v[paquete] = md.version(paquete)
        except Exception:
            v[paquete] = None
    return v


def resumen_tablatura(tab, compases, info_xml):
    """Estadísticas de la tablatura final y mapa de notas por compás (para localizar tramos vacíos)."""
    from collections import Counter
    inicios = [b for b, _ in compases]
    por_compas = np.bincount(np.searchsorted(inicios, np.array([n[0] / 4 + 4 for n in tab]), side="right") - 1,
                             minlength=len(compases))
    duraciones = Counter(int(n[1] - n[0]) for n in tab)
    nombres = Counter(_nombre_nota(n[2]) for n in tab)
    vacios = [i + 1 for i in range(1, len(compases)) if por_compas[i] == 0]
    return {
        "notas": len(tab), "compases": len(compases),
        "notas_por_compas": " ".join(str(int(x)) for x in por_compas),
        "compases_vacios": vacios,
        "duraciones_en_semicorcheas": {str(k): v for k, v in sorted(duraciones.items())},
        "notas_mas_frecuentes": dict(nombres.most_common(8)),
        "notas_con_sustain": sum(1 for n in info_xml["notas"] if n[3] > 0),
        "posiciones_de_mano": len(info_xml["anclas"]),
        "frase_musica_s": round(info_xml["t_musica"], 2), "frase_END_s": round(info_xml["t_end"], 2),
    }


def procesar(ruta, salida, forzar):
    import librosa, pretty_midi, soundfile as sf
    nombre, dest, artista, titulo, fuente, etiquetas = destino(ruta, salida)
    if (dest / f"{nombre}.gp5").exists() and not forzar:
        log(T("  (ya procesada, la salto; usa --forzar para repetir)", "  (already processed, skipping; use --forzar to redo it)"))
        return "saltada", ""
    dest.mkdir(parents=True, exist_ok=True)
    log(f"  {artista} - {titulo}  ({T('de', 'from')} {fuente_txt(fuente)})")
    t_ini = time.time()
    DIAG.clear()
    DIAG.update({"version": VERSION, "archivo": ruta.name, "artista": artista, "titulo": titulo,
                 "metadatos": {"fuente": fuente, "carpeta": nombre, "etiquetas": etiquetas},
                 "fecha": time.strftime("%Y-%m-%d %H:%M"), "tiempos_s": {}})
    reloj = [time.time()]

    def marca(etapa):
        DIAG["tiempos_s"][etapa] = round(time.time() - reloj[0], 1); reloj[0] = time.time()

    DIAG["entrada"] = info_audio(ruta)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        mezcla = tmp / "mezcla.wav"
        ffmpeg("-i", str(ruta), "-vn", "-ac", "2", "-ar", "44100", str(mezcla))
        mezcla_mono = tmp / "mezcla_mono.wav"
        ffmpeg("-i", str(mezcla), "-ac", "1", str(mezcla_mono))
        duracion = sf.info(str(mezcla)).duration
        marca("decodificar")

        log(T("  [1/6] Separando el bajo...", "  [1/6] Separating the bass..."))
        bajo = separar_bajo(mezcla, tmp)
        marca("separar_bajo")
        DIAG["sonoridad"] = sonoridades(mezcla, bajo)
        dif = DIAG["sonoridad"].get("bajo_respecto_mezcla_db")
        if dif is not None and dif < -35:
            # en las canciones normales el bajo separado queda entre 6 y 18 dB por debajo de la mezcla;
            # a -35 dB o menos lo que se ha separado es ruido: la tablatura saldría inventada
            raise RuntimeError(T(f"no parece tener bajo (lo separado está {-dif:.0f} dB por debajo de la mezcla); "
                                 "no genero tablatura",
                                 f"there seems to be no bass (the separated track is {-dif:.0f} dB below the mix); "
                                 "no tab generated"))
        log(T("  [2/6] Detectando beats y compases...", "  [2/6] Detecting beats and bars..."))
        beats, act, act_alt = detectar_beats(mezcla_mono)
        grid, barras, bpm, conf, irregulares, metro = construir_grid(beats, act, duracion, act_alt)
        marca("beats_y_compases")
        log(T("  [3/6] Transcribiendo notas...", "  [3/6] Transcribing notes..."))
        y, notas, n_ataques, n_cqt, cents, pua, pitches_pyin = transcribir(bajo, 60.0 / bpm / 4)
        marca("transcribir")
        if not notas:
            raise RuntimeError(T("no se ha detectado ninguna nota de bajo", "no bass notes detected"))
        log(T("  [4/6] Cuantizando y digitando...", "  [4/6] Quantising and fingering..."))
        q, desfase, ambiguas = cuantizar(notas, grid)
        afin_nombre, cuerdas, tab, movidas, nota_grave = elegir_afinacion(q, pitches_pyin)
        marca("cuantizar_y_digitar")

        # compás COUNT delante + silencio inicial
        med = float(np.median(np.diff(grid)))
        ibi0 = float(np.mean(np.diff(grid[:5])))
        completo = np.concatenate([[grid[0] - k * ibi0 for k in (4, 3, 2, 1)], grid])
        pad = MARGEN_INICIAL - completo[0]
        completo = completo + pad
        inicios_c = [0] + [4 + int(b) for b in barras]          # inicios de compás (el último = fin)
        fin_notas = max(n[1] for n in tab) / 4 + 4                # en beats, con el COUNT delante
        n_compases = max(2, sum(1 for b in inicios_c[:-1] if b < fin_notas))
        compases = [(inicios_c[i], inicios_c[i + 1] - inicios_c[i]) for i in range(n_compases)]
        completo = completo[:inicios_c[n_compases] + 1]
        tempos = [int(round(60 / np.mean(np.diff(completo[b:b + n + 1])))) for b, n in compases]
        etiquetas = np.zeros(len(completo), dtype=int)
        for b, n in compases:
            etiquetas[b:b + n] = np.arange(1, n + 1)
        etiquetas[-1] = 1
        irregulares = [(i + 2, n) for i, n in irregulares if i + 1 < n_compases]   # nº de compás en el .gp5

        log(T("  [5/6] Escribiendo archivos...", "  [5/6] Writing files..."))
        escribir_svl(dest / f"{nombre}.svl", completo, etiquetas)
        n_gp = escribir_gp5(dest / f"{nombre}.gp5", tab, compases, tempos, artista, titulo, cuerdas)
        cola = max(3.0, completo[-1] - (duracion + pad) + 1.0)
        pad_ms = int(round(pad * 1000))
        ffmpeg("-i", str(mezcla), "-af", f"adelay={pad_ms}|{pad_ms},apad=pad_dur={cola:.2f}",
               "-ar", "44100", "-c:a", "libvorbis", "-q:a", "6", str(dest / f"{nombre}.ogg"))

        # proyecto listo para DLC Builder: XML del arreglo, preview, portada y .rs2dlc
        meta = {"artista": artista, "titulo": titulo, **album_y_anio(ruta)}
        caratula = None
        if not SIN_INTERNET:
            if meta.get("album") and _etiqueta_valida(meta["album"]):
                caratula = buscar_album(artista, meta["album"], meta.get("year") if meta.get("year_de_etiqueta") else None)
            if caratula is None:
                caratula = buscar_caratula(artista, titulo)
        if caratula:
            # carátula, álbum y año salen del mismo disco (el original que eligió la búsqueda), para que no
            # aparezca la portada de un disco con el nombre y el año de otro (p. ej. un recopilatorio)
            DIAG.setdefault("caratula", {})["album_de_etiqueta"] = f'{meta["album"]} ({meta["year"]})'
            if caratula["album"]:
                meta["album"] = caratula["album"]
                if caratula["year"]:
                    meta["year"] = caratula["year"]
            elif meta.get("year_de_etiqueta") is False and caratula["year"]:
                meta["year"] = caratula["year"]
        duracion_ogg = sf.info(str(dest / f"{nombre}.ogg")).duration
        xml_path = dest / f"{nombre}_bass_RS2.xml"
        # Tuning Pitch: sólo si el desvío es grande (si no, 440 para no reafinar en cada canción)
        cents_aplicado = cents if abs(cents) >= UMBRAL_CENTS else 0.0
        info_xml = escribir_xml_rs(xml_path, completo, compases, tab, cuerdas, cents_aplicado,
                                   es_pua(pua), meta, duracion_ogg)
        con_pua = es_pua(pua)
        if VELOCIDAD_AUTO:
            # proporcional al tempo: a 120 BPM la base; a 60 la mitad, a 180 vez y media (con límites para
            # que una canción lentísima no se arrastre ni una rapidísima pase volando)
            velocidad = round(float(np.clip(VELOCIDAD_SCROLL * bpm / 120, *VELOCIDAD_LIMITES)), 2)
            txt_vel = T(f"{velocidad} (automática: {VELOCIDAD_SCROLL} a 120 BPM, esta va a {bpm:.0f})",
                        f"{velocidad} (auto: {VELOCIDAD_SCROLL} at 120 BPM, this one is at {bpm:.0f})")
        else:
            velocidad, txt_vel = VELOCIDAD_SCROLL, f"{VELOCIDAD_SCROLL} ({T('fija', 'fixed')})"
        DIAG["velocidad_scroll"] = velocidad
        # segundo arreglo, simplificado ("Alt. Bass" en el juego)
        xml_simple, txt_simple = None, T("no (desactivado en la configuración)", "no (disabled in the configuration)")
        if ARREGLO_SIMPLE is not None:
            tab_s = tab_simplificada(tab, compases, completo, ARREGLO_SIMPLE)
            if len(tab_s) >= 8 and len(tab_s) <= 0.85 * len(tab):
                xml_simple = dest / f"{nombre}_bass2_RS2.xml"
                escribir_xml_rs(xml_simple, completo, compases, tab_s, cuerdas, cents_aplicado, con_pua, meta,
                                duracion_ogg, principal=False)
                txt_simple = T(f"sí, 'Alt. Bass' en el juego: {len(tab_s)} de {len(tab)} notas "
                               f"({NOMBRES_SIMPLE[ARREGLO_SIMPLE]})",
                               f"yes, 'Alt. Bass' in the game: {len(tab_s)} of {len(tab)} notes "
                               f"({NOMBRES_SIMPLE_EN[ARREGLO_SIMPLE]})")
            else:
                txt_simple = T(f"no: simplificado quedaría con {len(tab_s)} de {len(tab)} notas, "
                               "casi igual que el completo (o casi vacío)",
                               f"no: it would have {len(tab_s)} of {len(tab)} notes, "
                               "almost the same as the full one (or almost empty)")
            DIAG["arreglo_simple"] = {"nivel": NOMBRES_SIMPLE[ARREGLO_SIMPLE], "notas": len(tab_s),
                                      "notas_completo": len(tab), "incluido": xml_simple is not None}
        # letra (arreglo de voz) de LRCLIB
        xml_letra, txt_letra = None, T("no (desactivada en la configuración)", "no (disabled in the configuration)")
        if LETRA and SIN_INTERNET:
            txt_letra = T("no (sin internet)", "no (offline)")
        elif LETRA:
            rec, intentos = buscar_letra(meta["artista"], meta["titulo"], meta.get("album"), duracion)
            DIAG["letra"] = {"intentos": intentos}
            if rec:
                xml_letra = dest / f"{nombre}_vocals_RS2.xml"
                n_lineas = escribir_letra(xml_letra, rec["syncedLyrics"], pad, duracion_ogg)
                DIAG["letra"].update({"lrclib_id": rec.get("id"), "album": rec.get("albumName"),
                                      "duracion": rec.get("duration"), "lineas": n_lineas})
                if n_lineas:
                    txt_letra = T(f"sí, {n_lineas} líneas de LRCLIB (disco '{rec.get('albumName')}'). Sincronizada "
                                  "por líneas: dentro de cada línea las palabras van repartidas, no clavadas",
                                  f"yes, {n_lineas} lines from LRCLIB (album '{rec.get('albumName')}'). Synced "
                                  "by line: words within each line are spread out, not exact")
                else:
                    xml_letra, txt_letra = None, T("no: la letra encontrada está vacía", "no: the lyrics found are empty")
            else:
                txt_letra = T("no encontrada en LRCLIB con la misma duración", "not found on LRCLIB with the same length")
        inicio_prev = escribir_preview(dest / f"{nombre}.ogg", dest / f"{nombre}_preview.ogg", duracion_ogg)
        portada, origen_portada = crear_portada(ruta, dest / "portada.png", artista, titulo, caratula)
        tono, origen_tono = elegir_tono(meta["artista"], meta["titulo"],
                                        es_pua(pua), bajo)
        escribir_proyecto(dest / f"{nombre}.rs2dlc", meta, xml_path, dest / f"{nombre}.ogg",
                          dest / f"{nombre}_preview.ogg", inicio_prev, portada, cuerdas, cents_aplicado,
                          es_pua(pua), tono,
                          xml_simple=xml_simple, xml_letra=xml_letra, velocidad=velocidad)
        problemas = comprobar_dlc_builder(dest / f"{nombre}.rs2dlc")
        marca("escribir_archivos")
        psarcs, error_psarc = [], T("desactivada (--sin-psarc)", "disabled (--sin-psarc)")
        if COMPILAR and not problemas:
            log(T("  [6/6] Compilando el .psarc (Wwise + DD)...", "  [6/6] Building the .psarc (Wwise + DD)..."))
            psarcs, error_psarc = compilar_psarc(dest / f"{nombre}.rs2dlc", CARPETA_PSARC, WWISE)
            marca("compilar_psarc")
        elif problemas:
            error_psarc = T("no se compila: el proyecto tiene problemas", "not built: the project has problems")

        # MIDI en tiempo real (notas cuantizadas) + A/B
        def t_slot(s):
            b = s / 4; i = int(np.clip(np.floor(b), 0, len(grid) - 2))
            return grid[i] + (b - i) * (grid[i + 1] - grid[i])
        pm = pretty_midi.PrettyMIDI(); inst = pretty_midi.Instrument(program=33, name="Bajo")
        for s0, s1, p, _, _ in tab:
            inst.notes.append(pretty_midi.Note(velocity=95, pitch=p, start=max(0.0, t_slot(s0) - desfase),
                                               end=max(0.01, t_slot(s1) - desfase)))
        pm.instruments.append(inst); pm.write(str(dest / f"{nombre}.mid"))
        sint = pm.synthesize(fs=SR, wave=lambda x: np.sin(x) + 0.35 * np.sin(2 * x) + 0.15 * np.sin(3 * x))
        sint = sint / (np.abs(sint).max() + 1e-9) * 0.9
        n = min(len(y), len(sint))
        sf.write(str(tmp / "ab.wav"), np.stack([y[:n] / (np.abs(y).max() + 1e-9) * 0.9, sint[:n]], axis=1), SR)
        ffmpeg("-i", str(tmp / "ab.wav"), "-b:a", "192k", str(dest / f"{nombre}_AB.mp3"))

        # pista de clics
        yc, _ = librosa.load(str(dest / f"{nombre}.ogg"), sr=44100, mono=True)
        yc = yc * 0.7; tt = np.arange(int(0.03 * 44100)) / 44100
        for i, b in enumerate(completo):
            c = 0.5 * np.sin(2 * np.pi * (1800 if etiquetas[i] == 1 else 1200) * tt) * np.exp(-tt * 120)
            s = int(b * 44100)
            if s + len(c) < len(yc): yc[s:s + len(c)] += c
        sf.write(str(tmp / "clics.wav"), yc / (np.abs(yc).max() + 1e-9) * 0.95, 44100)
        ffmpeg("-i", str(tmp / "clics.wav"), "-b:a", "192k", str(dest / f"{nombre}_clics.mp3"))

    inicio_notas = np.array([n[0] / 4 + 4 for n in tab])
    per = np.bincount(np.searchsorted([b for b, _ in compases], inicio_notas, side="right") - 1)
    nom = lambda m: pretty_midi.note_number_to_name(int(m)).replace("#", "#")
    # --- afinación ---
    txt_afin = (T("AFINACIÓN", "TUNING") + f": {afin_txt(afin_nombre)}  ({T('cuerdas', 'strings')} {' '.join(nom(c) for c in cuerdas)})\n"
                + T(f"  Nota grave repetida más baja: {nom(nota_grave)}", f"  Lowest repeated low note: {nom(nota_grave)}")
                + (T(f" | {movidas} notas sueltas cambiadas de octava para que quepan",
                     f" | {movidas} stray notes moved an octave to fit") if movidas else "") + "\n")
    if afin_nombre != "E estándar":
        txt_afin += T("  -> Ya va en el proyecto (y en el .gp5). Reafina el bajo antes de tocar;\n"
                      "     el afinador de Rocksmith te la pedirá al empezar la canción.\n",
                      "  -> It's already in the project (and in the .gp5). Retune your bass before playing;\n"
                      "     Rocksmith's tuner will ask for it when the song starts.\n")
    # --- desvío en cents ---
    la = 440 * 2 ** (cents / 1200)
    txt_cents = T("REFERENCIA DE AFINACIÓN DE LA GRABACIÓN", "RECORDING'S TUNING REFERENCE") + \
        f": {cents:+.0f} cents ({T('La', 'A')} = {la:.1f} Hz)\n"
    if cents_aplicado:
        txt_cents += T(f"  -> Desvío grande (>= {UMBRAL_CENTS:.0f} cents): va en el proyecto como Tuning Pitch {la:.2f}.\n"
                       "     El afinador de Rocksmith te pedirá afinar así para empastar con el disco.\n",
                       f"  -> Large deviation (>= {UMBRAL_CENTS:.0f} cents): set in the project as Tuning Pitch {la:.2f}.\n"
                       "     Rocksmith's tuner will ask you to tune like this to match the record.\n")
    elif abs(cents) >= 5:
        txt_cents += T(f"  -> Por debajo del umbral ({UMBRAL_CENTS:.0f} cents): se deja en 440 para no reafinar.\n"
                       "     (Sí se ha tenido en cuenta al reconocer las notas.)\n",
                       f"  -> Below the threshold ({UMBRAL_CENTS:.0f} cents): left at 440 so you don't need to retune.\n"
                       "     (It was taken into account when recognising the notes.)\n")
    else:
        txt_cents += T("  -> Prácticamente a 440 Hz: no hace falta tocar nada.\n",
                       "  -> Practically at 440 Hz: nothing to change.\n")
    # --- púa ---
    if np.isnan(pua):
        veredicto = T("sin datos suficientes", "not enough data")
    elif pua >= PUA_UMBRAL_DB:
        veredicto = T("PROBABLEMENTE CON PÚA", "PROBABLY WITH A PICK")
    else:
        veredicto = T("probablemente con dedos", "probably with fingers")
    if not np.isnan(pua) and abs(pua - PUA_UMBRAL_DB) < PUA_MARGEN_DB:
        veredicto += T(" (cerca del umbral: compruébalo de oído)", " (close to the threshold: check by ear)")
    if PUA_FORZADA is not None:
        veredicto = ((T("CON PÚA", "WITH A PICK") if PUA_FORZADA else T("con dedos", "with fingers"))
                     + T(" (fijado para el disco; la detección decía: ", " (set for the album; detection said: ") + veredicto + ")")
    con_pua = es_pua(pua)
    txt_pua = (T("PÚA O DEDOS", "PICK OR FINGERS") + f": {veredicto}  "
               + T(f"[índice {pua:.1f} dB; púa a partir de {PUA_UMBRAL_DB:.0f}]", f"[index {pua:.1f} dB; pick from {PUA_UMBRAL_DB:.0f}]") + "\n"
               + (T("  -> Ya va marcado 'Picked' en el proyecto.\n", "  -> Already marked 'Picked' in the project.\n") if con_pua else
                  T("  -> Si en realidad es con púa, marca 'Picked' en la ficha del arreglo en DLC Builder.\n",
                    "  -> If it's actually played with a pick, tick 'Picked' in the arrangement in DLC Builder.\n")))
    txt_proyecto = (T("PROYECTO DE DLC BUILDER: ", "DLC BUILDER PROJECT: ")
                    + (T(f"{nombre}.rs2dlc listo (pasa las comprobaciones)\n", f"{nombre}.rs2dlc ready (passes the checks)\n")
                       if not problemas else T("con problemas: ", "with problems: ") + "; ".join(problemas) + "\n")
                    + T("  -> Ábrelo en DLC Builder (Project > Open Project, o arrástralo a la ventana) y pulsa Build.\n",
                        "  -> Open it in DLC Builder (Project > Open Project, or drag it onto the window) and press Build.\n"))
    txt_psarc = ("PSARC: " + (", ".join(Path(x).name for x in psarcs) + f"  ({T('en', 'in')} {CARPETA_PSARC})" if psarcs
                  else T("no generado", "not built") + f" ({error_psarc})") + "\n"
                 + ("" if psarcs else T("  -> Puedes compilarlo a mano abriendo el .rs2dlc en DLC Builder.\n",
                                        "  -> You can build it by hand by opening the .rs2dlc in DLC Builder.\n")))
    txt_portada = (T("PORTADA", "ALBUM ART") + f": {origen_portada}" + (f" | {T('álbum', 'album')}: {meta['album']}" if meta['album'] else "")
                   + f" | {T('año', 'year')}: {meta['year']}\n")
    if irregulares:
        txt_irreg = (T(f"Compases irregulares (cambian el {metro}/4): ", f"Odd bars (changing the {metro}/4): ") + ", ".join(
                         T(f"compás {c} en {n}/4", f"bar {c} in {n}/4") + f" ({mmss(completo[compases[c - 1][0]] - pad)})"
                         for c, n in irregulares)
                     + T("\n  -> El minuto es el de la canción original. Ya van en el proyecto y en el .gp5\n"
                         "     (si montas por EOF, acepta importar los compases / time signatures).\n",
                         "\n  -> The minute is the original song's. They're already in the project and in the .gp5\n"
                         "     (if you use EOF, accept importing the time signatures).\n"))
    else:
        txt_irreg = T(f"Compases irregulares: ninguno (todo {metro}/4)\n", f"Odd bars: none (all {metro}/4)\n")
    informe = (T("Canción", "Song") + f": {artista} - {titulo}  ({T('nombre tomado de', 'name taken from')} {fuente_txt(fuente)})\n"
               + T("Archivo", "File") + f": {ruta.name}\n\n" + txt_psarc + txt_proyecto + txt_portada + "\n"
               + txt_afin + txt_cents + txt_pua + T("TONO DEL BAJO EN EL JUEGO", "IN-GAME BASS TONE") + f": {origen_tono}\n"
               + T("VELOCIDAD DE SCROLL", "SCROLL SPEED") + f": {txt_vel}\n"
               + T("ARREGLO SIMPLIFICADO", "SIMPLIFIED ARRANGEMENT") + f": {txt_simple}\n"
               + T("LETRA", "LYRICS") + f": {txt_letra}\n\n"
               + T("Tempo mediano", "Median tempo") + f": {bpm:.1f} BPM | {T('compás', 'time signature')}: {metro}/4"
               + (T(" (ternario: 3/4 o 6/8)", " (triple: 3/4 or 6/8)") if metro == 3 else "")
               + f" | {T('confianza del tiempo 1', 'downbeat confidence')}: {conf*100:.0f}%\n"
               + T(f"Ataques detectados: {n_ataques} | notas: {len(notas)} (resueltas por CQT: {n_cqt}) | en la tablatura: {n_gp}\n",
                   f"Onsets detected: {n_ataques} | notes: {len(notas)} (resolved by CQT: {n_cqt}) | in the tab: {n_gp}\n")
               + T(f"Desfase de ataques corregido: {desfase*1000:.0f} ms | notas dudosas al cuantizar: {ambiguas*100:.0f}%\n",
                   f"Onset offset corrected: {desfase*1000:.0f} ms | doubtful notes when quantising: {ambiguas*100:.0f}%\n")
               + T(f"Notas por compás (mediana): {np.median(per):.0f}\n", f"Notes per bar (median): {np.median(per):.0f}\n")
               + T(f"Silencio inicial añadido: {pad:.3f} s | compases: {n_compases} (el 1 es el COUNT, vacío)\n",
                   f"Lead-in silence added: {pad:.3f} s | bars: {n_compases} (bar 1 is the empty COUNT bar)\n")
               + txt_irreg
               + T(f"Tiempo de proceso: {time.time()-t_ini:.0f} s\n", f"Processing time: {time.time()-t_ini:.0f} s\n"))
    (dest / "informe.txt").write_text(informe, encoding="utf-8")
    # diagnóstico completo (para depurar): diagnostico.json en la carpeta y en el registro general
    DIAG["tablatura"] = resumen_tablatura(tab, compases, info_xml)
    DIAG["resultado"] = {"afinacion": afin_nombre, "cents_aplicados": round(cents_aplicado, 1),
                         "pua": es_pua(pua), "pua_fijada": PUA_FORZADA, "indice_pua": round(float(pua), 2),
                         "tempo": round(bpm, 1), "silencio_inicial_s": round(pad, 3), "portada": origen_portada,
                         "album": meta["album"], "año": meta["year"], "problemas_proyecto": problemas,
                         "psarc": [Path(x).name for x in psarcs], "error_psarc": None if psarcs else error_psarc,
                         "compases_irregulares": [f"{c}:{n}/4" for c, n in irregulares]}
    DIAG["tiempos_s"]["total"] = round(time.time() - t_ini, 1)
    import json
    (dest / "diagnostico.json").write_text(json.dumps(DIAG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    aviso = T("  ¡OJO! tiempo 1 dudoso, revisa con el archivo de clics",
              "  CAREFUL! doubtful downbeat, check it with the clicks file") if conf < 0.6 else ""
    extra = f" | {afin_txt(afin_nombre)}" + (T(" | compás 3/4", " | 3/4 time") if metro == 3 else "") + \
            (f" | Tuning Pitch {cents_aplicado:+.0f} cents" if cents_aplicado else "") + \
            (T(" | púa", " | pick") if es_pua(pua) else "") + \
            (T(f" | {len(irregulares)} compases irregulares", f" | {len(irregulares)} odd bars") if irregulares else "")
    if problemas:
        aviso += T("  ¡OJO! el proyecto tiene problemas, mira el informe", "  CAREFUL! the project has problems, see the report")
    extra += " | psarc OK" if psarcs else (T(" | sin psarc: ", " | no psarc: ") + f"{error_psarc}" if COMPILAR else "")
    resumen = T(f"{n_gp} notas, {bpm:.0f} BPM, dudosas {ambiguas*100:.0f}%", f"{n_gp} notes, {bpm:.0f} BPM, doubtful {ambiguas*100:.0f}%") + f"{extra}{aviso}"
    log(f"  OK: {resumen}")
    return "ok", resumen


# ---------------- 7. compilación a .psarc (cdlc-pack, librerías de DLC Builder) ----------------
def leer_configuracion():
    """configuracion.txt junto al script: líneas 'clave = valor' (# para comentarios)."""
    conf = {}
    ruta = AQUI / "configuracion.txt"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.split("#", 1)[0].strip()
            if "=" in linea:
                k, v = linea.split("=", 1)
                if v.strip().strip('"'):
                    conf[k.strip().lower()] = v.strip().strip('"')
    return conf


def ruta_cdlc_pack():
    if os.environ.get("CDLC_PACK"):
        return Path(os.environ["CDLC_PACK"])
    return AQUI / "herramientas" / "cdlc-pack" / ("cdlc-pack.exe" if os.name == "nt" else "cdlc-pack")


def compilar_psarc(proyecto, carpeta, wwise=None):
    """Convierte el audio con Wwise, genera la DD y empaqueta. Devuelve (rutas_psarc, error)."""
    exe = ruta_cdlc_pack()
    if not exe.exists():
        return [], T(f"no encuentro {exe}", f"{exe} not found")
    args = [str(exe), str(proyecto), "--salida", str(carpeta)]
    if wwise:
        args += ["--wwise", wwise]
    if DD_MODO == "ninguna":
        args += ["--sin-dd"]
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    rutas = [l.split("PSARC:", 1)[1].strip() for l in r.stdout.splitlines() if l.startswith("PSARC:")]
    DIAG["psarc"] = {"codigo_salida": r.returncode, "segundos": round(time.time() - t0, 1),
                     "salida": r.stdout.strip().splitlines()[-15:], "errores": r.stderr.strip().splitlines()[-15:],
                     "tamaño_kb": [round(Path(x).stat().st_size / 1024) for x in rutas if Path(x).exists()]}
    verif = [l[6:].strip() for l in r.stdout.splitlines() if l.startswith("VERIF ")]
    if verif:  # lo que de verdad hay dentro del psarc (niveles DD, frases, notas al máximo nivel)
        DIAG["psarc"]["verificacion"] = verif
        for l in verif:
            if "notas_max=" in l and "niveles=" in l:
                niveles = int(l.split("niveles=")[1].split()[0])
                if niveles < 2:
                    log(T("  AVISO: el psarc solo tiene un nivel de dificultad (sin DD no habrá porcentaje)",
                          "  WARNING: the psarc has only one difficulty level (without DD there's no percentage)"))
                if "notas_puntuables=" in l:
                    puntuables = float(l.split("notas_puntuables=")[1].split()[0])
                    maximas = int(l.split("notas_max=")[1].split()[0])
                    if abs(puntuables - maximas) > 0.5:
                        log(T(f"  AVISO: el juego puntuará sobre {puntuables:.0f} notas y la canción tiene {maximas}",
                              f"  WARNING: the game will score {puntuables:.0f} notes and the song has {maximas}"))
    if r.returncode != 0 or not rutas:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        return [], (detalle[-1] if detalle else f"código {r.returncode}")
    return rutas, None


class Registro:
    """Registro general de una tanda: resumen por canción + informes completos + errores detallados.
    Se reescribe tras cada canción, así que vale aunque el proceso se corte a medias."""
    def __init__(self, ruta, total, forzar):
        import platform
        self.ruta, self.total, self.inicio = Path(ruta), total, time.time()
        self.cabecera = (f"{T('REGISTRO', 'LOG')} auto-cdlc {VERSION} | {time.strftime('%Y-%m-%d %H:%M')} | {T('idioma', 'language')} {IDIOMA}\n"
                         f"{T('Sistema', 'System')}: {platform.platform()} | Python {platform.python_version()}\n"
                         f"{T('Canciones en la tanda', 'Songs in the batch')}: {total}" + (" | --forzar" if forzar else "") + "\n")
        self.lineas, self.informes, self.errores, self.final = [], [], [], T("(tanda en curso)\n", "(batch in progress)\n")
        self.diagnosticos = []
        try:
            import json
            self.cabecera += "Versiones: " + json.dumps(versiones(), ensure_ascii=False) + "\n"
            self.cabecera += (f"Configuración: psarc={'si' if COMPILAR else 'no'} | carpeta={CARPETA_PSARC} | "
                              f"carátulas={'no' if SIN_INTERNET else 'si'} | umbral_cents={UMBRAL_CENTS} | dificultad={DD_MODO} (inicial {DD_INICIAL:.0f} %) | "
                              f"wwise={WWISE or 'automático'} | partir_repetidas={'si' if PARTIR_REPETIDAS else 'no'} "
                              f"({UMBRAL_REATAQUE_DB} dB) | tono_crepe={'si' if TONO_CREPE else 'no'} | tono_bajo={TONO_MODO} | velocidad_scroll={('auto ' if VELOCIDAD_AUTO else '') + str(VELOCIDAD_SCROLL)} | letra={'si' if LETRA else 'no'} | arreglo_simple={NOMBRES_SIMPLE.get(ARREGLO_SIMPLE, 'no')}\n")
        except Exception:
            pass
        self._guardar()

    def cancion(self, i, ruta, estado, resumen, segundos, informe, traza=None):
        etiqueta = {"ok": "OK", "saltada": T("SALTADA (ya procesada)", "SKIPPED (already processed)"), "error": "ERROR"}[estado]
        resumen = (resumen or "").strip().splitlines()[0][:200] if resumen else ""
        self.lineas.append(f"[{i}/{self.total}] {ruta.name} | {etiqueta} | {segundos:.0f} s"
                           + (f" | {resumen}" if resumen else ""))
        if informe is not None and estado == "ok" and Path(informe).exists():
            self.informes.append(Path(informe).read_text(encoding="utf-8"))
            diag = Path(informe).with_name("diagnostico.json")
            if diag.exists():
                import json
                self.diagnosticos.append(json.dumps(json.loads(diag.read_text(encoding="utf-8")),
                                                    ensure_ascii=False, separators=(",", ":")))
        if traza:
            self.errores.append(f"--- {ruta.name} ---\n{traza}")
        self._guardar()

    def cerrar(self, ok, errores):
        self.final = T(f"Terminado: {ok} bien, {errores} con error, en {(time.time() - self.inicio) / 60:.1f} min\n",
                       f"Finished: {ok} OK, {errores} with errors, in {(time.time() - self.inicio) / 60:.1f} min\n")
        self._guardar()

    def _guardar(self):
        sep = "\n" + "=" * 78 + "\n"
        texto = (self.cabecera + "\n" + "\n".join(self.lineas) + "\n\n" + self.final
                 + (sep + T("ERRORES DETALLADOS", "DETAILED ERRORS") + sep + "\n".join(self.errores) if self.errores else "")
                 + (sep + T("INFORMES", "REPORTS") + sep + ("\n" + "-" * 78 + "\n").join(self.informes) if self.informes else "")
                 + (sep + T("DIAGNÓSTICO (una línea JSON por canción, para depurar)", "DIAGNOSTICS (one JSON line per song, for debugging)") + sep
                    + "\n".join(self.diagnosticos) + "\n" if self.diagnosticos else ""))
        self.ruta.write_text(texto, encoding="utf-8")


# ---------------- preparación de la tanda: pendientes, discos y preguntas ----------------
def leer_con_espera(segundos):
    """Lee una línea del teclado; None si nadie escribe nada en 'segundos' (o no hay teclado)."""
    import sys
    if not sys.stdin or not sys.stdin.isatty():
        return None
    if os.name == "nt":
        import msvcrt
        fin, texto = time.time() + segundos, ""
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getwche()
                if ch in ("\r", "\n"):
                    print(); return texto
                if ch == "\b":
                    texto = texto[:-1]; print(" \b", end="", flush=True)
                elif ch in ("\x00", "\xe0"):
                    msvcrt.getwch()             # tecla especial (flechas...): se ignora
                else:
                    texto += ch
                fin = time.time() + segundos     # mientras escribes no corre el reloj
            elif time.time() > fin:
                return texto if texto else None
            else:
                time.sleep(0.05)
    import select
    r, _, _ = select.select([sys.stdin], [], [], segundos)
    return sys.stdin.readline().rstrip("\n") if r else None


class Preguntas:
    """Preguntas antes de la tanda. Intro = el valor por defecto. Si nadie contesta en 'espera' segundos
    (lanzada por la noche y te has ido), se usan los valores por defecto en esta y en todas las demás."""
    def __init__(self, espera=60, activas=True):
        import sys
        self.espera, self.desatendido = espera, not activas
        if activas and not (sys.stdin and sys.stdin.isatty()):
            log(T("(sin teclado: no pregunto, uso los valores por defecto)", "(no keyboard: not asking, using the defaults)"))
            self.desatendido = True

    def __call__(self, texto, defecto, valido=lambda v: True):
        if self.desatendido:
            log(f"{texto} [{defecto}]: {defecto}")
            return defecto
        for _ in range(3):
            print(f"{texto} [{defecto}]: ", end="", flush=True)
            r = leer_con_espera(self.espera)
            if r is None:
                print(T(f"\n  (nadie contesta en {self.espera} s: uso los valores por defecto para todo)",
                        f"\n  (no answer in {self.espera} s: using the defaults for everything)"))
                self.desatendido = True
                return defecto
            r = r.strip() or str(defecto)
            if valido(r):
                return r
            print(T("  No entiendo esa respuesta, prueba otra vez.", "  I don't understand that answer, try again."))
        return defecto


def _num_pista(t):
    m = re.match(r"\s*(\d+)", str(t or ""))
    return int(m.group(1)) if m else 999


def disco_de(ruta):
    """(artista del disco, disco, de dónde sale) para agrupar. Etiquetas si las hay; si no, se pregunta a
    iTunes/Deezer por la canción; si tampoco, '(sin disco)'."""
    et = leer_etiquetas(ruta)
    artista, titulo, _, _ = metadatos(ruta)
    art = et.get("albumartist") if _etiqueta_valida(et.get("albumartist", "")) else artista
    album = et.get("album") if _etiqueta_valida(et.get("album", "")) else None
    if album:
        return art, album, "etiquetas", _num_pista(et.get("tracknumber"))
    if not SIN_INTERNET:
        try:
            c = buscar_caratula(artista, titulo)
            if c and c.get("album"):
                return art, c["album"], "consulta en internet", 999
        except Exception:
            pass
    return art, T("(sin disco)", "(no album)"), "sin datos", 999


def historial(salida):
    """De los registros anteriores: segundos medios por canción y archivos que dieron error."""
    tiempos, fallidas = [], set()
    for reg in sorted(Path(salida).glob("registro_*.txt")):
        try:
            for l in reg.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"\[\d+/\d+\] (.+?) \| (OK|ERROR) \| (\d+) s", l)
                if m:
                    if m.group(2) == "OK":
                        tiempos.append(int(m.group(3))); fallidas.discard(m.group(1))
                    else:
                        fallidas.add(m.group(1))
        except Exception:
            pass
    medio = float(np.median(tiempos[-200:])) if len(tiempos) >= 5 else None
    return medio, fallidas


def alias_tono(v):
    """Nombres en inglés de los tonos de referencia."""
    return TONO_ALIAS.get(v.strip().lower(), v.strip())


TONO_ALIAS = {"clean": "limpio", "clean_pick": "limpio_pua", "overdrive": "saturado", "distortion": "distorsion"}


def tono_valido(v):
    v = alias_tono(v)
    return v.lower() in TONOS_PRESET or v.lower() == "auto" or tono_oficial(nombre=v)[0] is not None \
        or base_tonos() is None


def planificar(archivos, salida, forzar, preguntar):
    """Pendientes agrupados por artista > disco, preguntas de la tanda y de cada disco, y resumen.
    Devuelve la lista [(archivo, ajustes del disco)] en orden, o None si se cancela."""
    import json
    global DD_INICIAL, ARREGLO_SIMPLE
    pendientes, hechas = [], 0
    for r in archivos:
        nombre, dest = destino(r, salida)[:2]
        if (dest / f"{nombre}.gp5").exists() and not forzar:
            hechas += 1
        else:
            pendientes.append(r)
    seg_cancion, fallidas = historial(salida)
    log(T(f"\nEn la entrada hay {len(archivos)} canciones: {hechas} ya procesadas, {len(pendientes)} pendientes.",
          f"\nThe input has {len(archivos)} songs: {hechas} already processed, {len(pendientes)} pending."))
    if not pendientes:
        return []
    log(T("Agrupando por disco...", "Grouping by album..."))
    discos = {}
    for r in pendientes:
        art, alb, origen, pista = disco_de(r)
        discos.setdefault((art, alb), {"origen": origen, "canciones": []})["canciones"].append((pista, r.name, r))
    orden = sorted(discos, key=lambda k: (a_ascii(k[0]).lower(), k[1] in ("(sin disco)", "(no album)"), a_ascii(k[1]).lower()))
    for k in orden:
        discos[k]["canciones"].sort(key=lambda x: (x[0], x[1].lower()))
    log("")
    for art, alb in orden:
        d = discos[(art, alb)]
        nota = "" if d["origen"] in ("etiquetas", "sin datos") else T(f"  (disco sacado de: {d['origen']})",
                                                        "  (album from: " + {"consulta en internet": "online lookup"}.get(d["origen"], "no data") + ")")
        n = len(d['canciones'])
        log(f"  {art} > {alb}: {n} " + (T('canción', 'song') if n == 1 else T('canciones', 'songs')) + nota)

    reintentar = True
    fallaron = [r for r in pendientes if r.name in fallidas]
    if fallaron:
        log(T(f"\n{len(fallaron)} de las pendientes dieron error en tandas anteriores (p. ej. sin bajo):",
              f"\n{len(fallaron)} of the pending songs failed in earlier batches (e.g. no bass):"))
        for r in fallaron[:8]:
            log(f"   - {r.name}")
        if len(fallaron) > 8:
            log(T(f"   ... y {len(fallaron) - 8} más", f"   ... and {len(fallaron) - 8} more"))
        reintentar = si_no(preguntar(T("¿Reintentarlas? (s/n)", "Retry them? (y/n)"), "n", lambda x: x.lower()[:1] in "syn"))

    if not reintentar:
        # lo que no se va a procesar no entra en las preguntas ni en el resumen
        for d in discos.values():
            d["canciones"] = [c for c in d["canciones"] if c[2].name not in fallidas]
        orden = [k for k in orden if discos[k]["canciones"]]
        if not orden:
            log(T("No queda nada que procesar.", "Nothing left to process."))
            return []

    # ---- preguntas de la tanda ----
    log(T("\nPulsa Intro para dejar lo que hay entre corchetes (lo de configuracion.txt).",
          "\nPress Enter to keep the value in brackets (the one in configuracion.txt)."))
    v = preguntar(T("Dificultad inicial para toda la tanda (% de notas con que empieza cada frase, 0-95)",
                    "Starting difficulty for the whole batch (% of notes each phrase starts with, 0-95)"),
                  f"{DD_INICIAL:.0f}", lambda x: x.replace("%", "").strip().replace(",", ".").replace(".", "", 1).isdigit()
                  and 0 <= float(x.replace("%", "").replace(",", ".")) <= 95)
    DD_INICIAL = float(str(v).replace("%", "").replace(",", ".").strip())
    claves_simple = {"tiempo": 2, "medio": 1, "compas": 0, "compás": 0, "corchea": 3, "no": None,
                     "beat": 2, "half": 1, "bar": 0, "eighth": 3}
    if IDIOMA == "en":
        actual = {2: "beat", 1: "half", 0: "bar", 3: "eighth", None: "no"}[ARREGLO_SIMPLE]
    else:
        actual = {2: "tiempo", 1: "medio", 0: "compas", 3: "corchea", None: "no"}[ARREGLO_SIMPLE]
    v = preguntar(T("Arreglo simplificado (tiempo / medio / compas / corchea / no)",
                    "Simplified arrangement (beat / half / bar / eighth / no)"), actual,
                  lambda x: x.lower() in claves_simple)
    ARREGLO_SIMPLE = claves_simple[str(v).lower()]
    global ENVIAR
    modo_envio = CONF_ENVIO
    if ENVIOS_URL and not SIN_INTERNET and modo_envio == "preguntar":
        log(T("\nPuedes enviar los resultados de esta tanda para ayudar a mejorar auto-cdlc. Se envían solo datos\n"
              "(diagnóstico, informe y tablatura de cada canción), nunca el audio ni la letra, y sin rutas personales.",
              "\nYou can send this batch's results to help improve auto-cdlc. Only data is sent (diagnostics,\n"
              "report and tab of each song), never the audio or the lyrics, and without personal paths."))
        ENVIAR = si_no(preguntar(T("¿Enviar los resultados? (s/n)", "Send the results? (y/n)"), "n",
                                 lambda x: x.lower()[:1] in "syn"))
    else:
        ENVIAR = bool(ENVIOS_URL) and not SIN_INTERNET and modo_envio == "si"
    # ---- preguntas de cada disco ----
    ruta_aj = Path(salida) / "ajustes_discos.json"
    try:
        guardados = json.loads(ruta_aj.read_text(encoding="utf-8"))
    except Exception:
        guardados = {}
    log(T("\nSonido del bajo de cada disco: auto, limpio, limpio_pua, saturado, distorsion, fuzz "
          "o el nombre de un tono oficial.  Púa: auto (detectar), pua o dedos.",
          "\nBass tone for each album: auto, limpio (clean), limpio_pua (bright clean), saturado (overdrive), "
          "distorsion, fuzz or an official tone name.  Pick: auto (detect), pick or fingers."))
    ajustes = {}
    for art, alb in orden:
        clave = f"{art} ||| {alb}"
        previo = guardados.get(clave, {})
        log(f"\n  {art} > {alb}" + (T("  (ajustes recordados de la última vez)", "  (settings remembered from last time)") if previo else ""))
        tono = preguntar(T("    tono_bajo", "    bass tone"), previo.get("tono", TONO_MODO), tono_valido)
        alias_pua = {"auto": "auto", "pua": "pua", "pick": "pua", "dedos": "dedos", "fingers": "dedos", "finger": "dedos"}
        defecto_pua = previo.get("pua", "auto")
        if IDIOMA == "en":
            defecto_pua = {"pua": "pick", "dedos": "fingers"}.get(defecto_pua, defecto_pua)
        pua = preguntar(T("    púa", "    pick"), defecto_pua, lambda x: a_ascii(x).lower() in alias_pua)
        ajustes[(art, alb)] = {"tono": alias_tono(tono), "pua": alias_pua[a_ascii(pua).lower()]}
        guardados[clave] = ajustes[(art, alb)]
    try:
        ruta_aj.write_text(json.dumps(guardados, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass

    # ---- cola y resumen ----
    cola = [(r, k, ajustes[k]) for k in orden for _, _, r in discos[k]["canciones"]]
    saltadas = [] if reintentar else fallaron
    estimado = seg_cancion is None
    seg_cancion = seg_cancion or 270.0
    horas = len(cola) * seg_cancion / 3600
    log("\n" + "=" * 70 + "\n" + T("RESUMEN DE LA TANDA", "BATCH SUMMARY") + "\n" + "=" * 70)
    log(T(f"Dificultad inicial: {DD_INICIAL:.0f} % | arreglo simplificado: {NOMBRES_SIMPLE.get(ARREGLO_SIMPLE, 'no')} | "
          f"letra: {'si' if LETRA else 'no'} | velocidad de scroll: {('auto ' if VELOCIDAD_AUTO else '') + str(VELOCIDAD_SCROLL)}",
          f"Starting difficulty: {DD_INICIAL:.0f} % | simplified arrangement: {NOMBRES_SIMPLE_EN.get(ARREGLO_SIMPLE, 'no')} | "
          f"lyrics: {'yes' if LETRA else 'no'} | scroll speed: {('auto ' if VELOCIDAD_AUTO else '') + str(VELOCIDAD_SCROLL)}"))
    if ENVIOS_URL:
        log(T("Envío de resultados: ", "Sending results: ") + (T("sí", "yes") if ENVIAR else "no"))
    for k in orden:
        n = sum(1 for x in cola if x[1] == k)
        if n:
            pua_txt = {"pua": T("púa", "pick"), "dedos": T("dedos", "fingers")}.get(ajustes[k]["pua"], "auto")
            log(f"  {k[0]} > {k[1]}: {n} " + (T('canción', 'song') if n == 1 else T('canciones', 'songs'))
                + f" | {T('tono', 'tone')} {ajustes[k]['tono']} | {T('púa', 'pick')} {pua_txt}")
    if saltadas:
        log(T(f"Se saltan {len(saltadas)} que fallaron antes; {hechas} ya estaban hechas.",
              f"Skipping {len(saltadas)} that failed before; {hechas} were already done."))
    log(T(f"A procesar: {len(cola)} {'canción' if len(cola) == 1 else 'canciones'}, unas {horas:.1f} h ({seg_cancion / 60:.1f} min por canción"
          + (", aproximado)." if estimado else " en tus tandas anteriores)."),
          f"To process: {len(cola)} {'song' if len(cola) == 1 else 'songs'}, about {horas:.1f} h ({seg_cancion / 60:.1f} min per song"
          + (", approximate)." if estimado else " in your earlier batches).")))
    if not cola:
        return []
    if not si_no(preguntar(T("¿Empezar? (s/n)", "Start? (y/n)"), T("s", "y"), lambda x: x.lower()[:1] in "syn")):
        return None
    return cola


# ---------------- envío voluntario de resultados ----------------
def _anonimizar(texto):
    """Quita rutas personales (la carpeta del usuario y la del programa)."""
    for ruta, sustituto in ((str(AQUI), "<auto-cdlc>"), (str(Path.home()), "<usuario>")):
        for variante in {ruta, ruta.replace("\\", "\\\\"), ruta.replace("\\", "/")}:
            texto = texto.replace(variante, sustituto)
    return re.sub(r"(?i)([A-Z]:(?:\\\\|\\|/)(?:Users|Usuarios)(?:\\\\|\\|/))[^\\/\"']+", r"\1<usuario>", texto)


def id_instalacion():
    """Identificador anónimo de esta instalación (para agrupar envíos; no identifica a la persona)."""
    import uuid
    ruta = AQUI / ".instalacion"
    try:
        if ruta.exists():
            return ruta.read_text().strip()[:40]
        v = uuid.uuid4().hex
        ruta.write_text(v)
        return v
    except Exception:
        return "desconocida"


_ENVIO_FALLIDO = [False]


def enviar_cancion(ruta, estado, resumen, carpeta, traza=None):
    """Sube los resultados de una canción (nunca el audio ni la letra) al servidor de envíos."""
    if not (ENVIAR and ENVIOS_URL) or _ENVIO_FALLIDO[0]:
        return
    import json, gzip, platform, urllib.request
    datos = {"programa": "auto-cdlc", "version": VERSION, "idioma": IDIOMA, "instalacion": id_instalacion(),
             "sistema": platform.platform(), "fecha": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "configuracion": {"dificultad": DD_MODO, "dificultad_inicial": DD_INICIAL, "tono_bajo": TONO_MODO,
                               "pua_fijada": PUA_FORZADA, "arreglo_simple": ARREGLO_SIMPLE,
                               "partir_repetidas": PARTIR_REPETIDAS, "tono_crepe": TONO_CREPE},
             "cancion": {"archivo": ruta.name, "estado": estado, "resumen": resumen or "", "error": traza}}
    try:
        if carpeta and Path(carpeta).is_dir():
            c = Path(carpeta)
            for clave, archivo in (("informe", "informe.txt"), ("diagnostico", "diagnostico.json")):
                if (c / archivo).exists():
                    datos["cancion"][clave] = (c / archivo).read_text(encoding="utf-8")
            datos["cancion"]["xml"] = {x.name: x.read_text(encoding="utf-8")
                                       for x in sorted(c.glob("*_bass*_RS2.xml"))}   # sin la letra
        cuerpo = gzip.compress(_anonimizar(json.dumps(datos, ensure_ascii=False, default=str)).encode("utf-8"))
        req = urllib.request.Request(ENVIOS_URL.rstrip("/") + "/envio", data=cuerpo, method="POST",
                                     headers={"Content-Type": "application/gzip", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        log(T("  (resultados enviados, gracias)", "  (results sent, thank you)"))
    except Exception as ex:
        _ENVIO_FALLIDO[0] = True
        log(T(f"  Aviso: no se han podido enviar los resultados ({ex}); no lo intento más en esta tanda.",
              f"  Warning: couldn't send the results ({ex}); not trying again in this batch."))


# ---------------- actualizaciones ----------------
def _num_version(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4])


def _bajar(url, destino):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)


def fusionar_configuracion(actual, plantilla):
    """Añade al configuracion.txt del usuario las claves nuevas de la plantilla (con sus comentarios),
    sin tocar las que ya tiene. Devuelve las claves añadidas."""
    texto = actual.read_text(encoding="utf-8-sig")
    tiene = {l.split("=", 1)[0].strip().lower() for l in texto.splitlines()
             if "=" in l and not l.lstrip().startswith("#")}
    bloques, comentarios = [], []
    for l in plantilla.read_text(encoding="utf-8-sig").splitlines():
        if l.lstrip().startswith("#"):
            comentarios.append(l)
        elif "=" in l:
            bloques.append((l.split("=", 1)[0].strip().lower(), comentarios + [l])); comentarios = []
        else:
            comentarios = []
    nuevas = [(k, b) for k, b in bloques if k not in tiene and k != "idioma"]
    if nuevas:
        extra = "\r\n\r\n" + "\r\n\r\n".join("\r\n".join(b) for _, b in nuevas) + "\r\n"
        actual.write_text(texto.rstrip("\r\n") + extra, encoding="utf-8")
    return [k for k, _ in nuevas]


def comprobar_actualizacion(preguntar):
    """Mira si hay una versión nueva publicada y, si quieres, la instala sin tocar tu configuración, tus
    canciones ni los modelos. Devuelve True si se ha actualizado (hay que volver a lanzar)."""
    import json, urllib.request, zipfile, tempfile
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO.split('github.com/')[1]}/releases/latest",
                                     headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            rel = json.load(r)
    except Exception:
        return False                      # sin conexión o GitHub caído: se sigue sin más
    nueva = str(rel.get("tag_name", "")).lstrip("v")
    if not nueva or _num_version(nueva) <= _num_version(VERSION):
        return False
    log("\n" + "=" * 70)
    log(T(f"Hay una versión nueva de auto-cdlc: {nueva} (tienes la {VERSION})",
          f"A new version of auto-cdlc is available: {nueva} (you have {VERSION})"))
    cuerpo = str(rel.get("body") or "")
    partes = re.split(r"(?m)^## Español\s*$", cuerpo)
    cuerpo = (partes[1] if len(partes) > 1 else partes[0]) if IDIOMA == "es" else partes[0]
    novedades = re.split(r"(?m)^### (?:What's in|Novedades)[^\n]*$", cuerpo)
    texto = novedades[1] if len(novedades) > 1 else cuerpo
    notas = [l for l in texto.splitlines() if l.strip().startswith(("-", "*", "1", "2", "3")) and "**English**" not in l]
    for l in notas[:12]:
        log("  " + l.strip()[:110])
    log(f"  {rel.get('html_url', REPO + '/releases')}")
    log("=" * 70)
    if (AQUI / ".git").exists():
        log(T("Esta copia es un repositorio git: actualízala con 'git pull'.",
              "This copy is a git repository: update it with 'git pull'."))
        return False
    if preguntar.desatendido:
        log(T("(tanda desatendida: no actualizo ahora)", "(unattended batch: not updating now)"))
        return False
    if not si_no(preguntar(T("¿Actualizar ahora? (s/n)", "Update now? (y/n)"), T("s", "y"),
                           lambda x: x.lower()[:1] in "syn")) or preguntar.desatendido:
        return False
    log(T("Descargando la versión nueva...", "Downloading the new version..."))
    tmp = Path(tempfile.mkdtemp(prefix="auto-cdlc-act-"))
    try:
        _bajar(rel["zipball_url"], tmp / "codigo.zip")
        with zipfile.ZipFile(tmp / "codigo.zip") as z:
            z.extractall(tmp / "codigo")
        raiz = next((tmp / "codigo").iterdir())
        conservar = {"configuracion.txt", "entrada", "salida", "modelos", "psarc", ".venv", ".git"}
        for org in raiz.rglob("*"):
            rel_path = org.relative_to(raiz)
            if not org.is_file() or rel_path.parts[0] in conservar or rel_path.parts[0].startswith(".git"):
                continue
            if rel_path.parts[:2] == ("herramientas", "cdlc-pack") and rel_path.parts[2:3] != ("codigo",):
                continue
            dst = AQUI / rel_path
            if rel_path.as_posix() == "procesar.bat":
                dst = AQUI / "procesar.bat.nuevo"   # el .bat está en marcha: lo cambia él mismo al acabar
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(org, dst)
        plantilla = AQUI / ("configuracion.en.txt" if IDIOMA == "en" else "configuracion.txt")
        if IDIOMA != "en":
            plantilla = raiz / "configuracion.txt"
        if (AQUI / "configuracion.txt").exists() and plantilla.exists():
            nuevas = fusionar_configuracion(AQUI / "configuracion.txt", plantilla)
            if nuevas:
                log(T("Opciones nuevas añadidas a configuracion.txt: ", "New options added to configuracion.txt: ")
                    + ", ".join(nuevas))
        # el compilador solo se baja si la release trae uno distinto del que tienes
        if os.name == "nt":
            asset = next((a for a in rel.get("assets", []) if a.get("name") == "cdlc-pack-win-x64.zip"), None)
            marca = AQUI / "herramientas" / "cdlc-pack" / ".release"
            if asset and (not marca.exists() or marca.read_text().strip() != str(asset.get("updated_at"))):
                log(T("Actualizando cdlc-pack...", "Updating cdlc-pack..."))
                _bajar(asset["browser_download_url"], tmp / "pack.zip")
                with zipfile.ZipFile(tmp / "pack.zip") as z:
                    z.extractall(AQUI / "herramientas" / "cdlc-pack")
                marca.write_text(str(asset.get("updated_at")))
    except Exception as ex:
        log(T(f"No se ha podido actualizar ({ex}). Sigue la versión {VERSION}; puedes bajar la nueva de {REPO}/releases",
              f"Couldn't update ({ex}). Staying on {VERSION}; you can download the new one from {REPO}/releases"))
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log(T(f"Actualizado a la {nueva}.", f"Updated to {nueva}."))
    return True


def main():
    ap = argparse.ArgumentParser(description="mp3 -> tablatura de bajo + mapa de beats para EOF")
    ap.add_argument("entradas", nargs="*", help="archivos o carpetas (por defecto: carpeta 'entrada')")
    ap.add_argument("--salida", default=str(AQUI / "salida"))
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--psarc", help="carpeta de destino de los .psarc (por defecto: carpeta 'psarc')")
    ap.add_argument("--wwise", help="ruta a WwiseConsole.exe (normalmente se encuentra sola)")
    ap.add_argument("--sin-psarc", action="store_true", help="no compilar: deja sólo el proyecto .rs2dlc")
    ap.add_argument("--sin-internet", action="store_true", help="no buscar carátulas en internet")
    ap.add_argument("--sin-actualizar", action="store_true", help="no buscar versiones nuevas")
    ap.add_argument("--sin-preguntas", action="store_true",
                    help="no preguntar nada: usar lo de configuracion.txt (y lo recordado de cada disco)")
    a = ap.parse_args()
    global COMPILAR, CARPETA_PSARC, WWISE, SIN_INTERNET, UMBRAL_CENTS, DD_MODO, DD_INICIAL
    global PARTIR_REPETIDAS, UMBRAL_REATAQUE_DB, TONO_CREPE, TONO_MODO, VELOCIDAD_SCROLL, LETRA, ARREGLO_SIMPLE
    global VELOCIDAD_AUTO, IDIOMA
    conf = leer_configuracion()
    IDIOMA = "en" if conf.get("idioma", "es").strip().lower()[:2] == "en" else "es"
    global ENVIOS_URL, CONF_ENVIO
    ENVIOS_URL = conf.get("servidor_envios", ENVIOS_URL).strip()
    CONF_ENVIO = {"si": "si", "yes": "si", "no": "no"}.get(conf.get("enviar_resultados", "preguntar").strip().lower(),
                                                          "preguntar")
    no = ("no", "false", "0")
    PARTIR_REPETIDAS = conf.get("partir_repetidas", "si").lower() not in no
    TONO_CREPE = conf.get("tono_crepe", "si").lower() not in no
    TONO_MODO = alias_tono(conf.get("tono_bajo", "auto").strip() or "auto")
    LETRA = conf.get("letra", "si").lower() not in no
    ARREGLO_SIMPLE = {"no": None, "ninguno": None, "compas": 0, "compás": 0, "medio": 1, "medio compas": 1,
                      "medio compás": 1, "tiempo": 2, "corchea": 3, "none": None, "bar": 0, "half": 1,
                      "beat": 2, "eighth": 3}.get(
        conf.get("arreglo_simple", "tiempo").strip().lower(), 2)
    v = conf.get("velocidad_scroll", "1.3").strip().lower()
    VELOCIDAD_AUTO = v.startswith("auto")
    try:
        v = v[4:].strip() if VELOCIDAD_AUTO else v
        VELOCIDAD_SCROLL = min(5.0, max(0.5, float(v.replace(",", ".")))) if v else 1.3
    except ValueError:
        pass
    try:
        UMBRAL_REATAQUE_DB = float(conf.get("umbral_reataque_db", UMBRAL_REATAQUE_DB))
    except ValueError:
        log(T("Aviso: umbral_reataque_db no es un número en configuracion.txt; uso 3",
              "Warning: umbral_reataque_db is not a number in configuracion.txt; using 3"))
    try:
        UMBRAL_CENTS = float(conf.get("umbral_cents", UMBRAL_CENTS))
        dd = conf.get("dificultad", DD_MODO).strip().lower()
        DD_MODO = {"propia": "propia", "dlcbuilder": "dlcbuilder", "dlc builder": "dlcbuilder",
                   "ninguna": "ninguna", "no": "ninguna"}.get(dd, "propia")
        DD_INICIAL = min(95.0, max(0.0, float(str(conf.get("dificultad_inicial", DD_INICIAL)).replace("%", "").strip())))
    except ValueError:
        log(T("Aviso: umbral_cents o dificultad_inicial no es un número en configuracion.txt; reviso los valores por defecto",
              "Warning: umbral_cents or dificultad_inicial is not a number in configuracion.txt; using the defaults"))
    CARPETA_PSARC = Path(a.psarc or conf.get("carpeta_psarc") or (AQUI / "psarc"))
    WWISE = a.wwise or conf.get("wwise") or None
    COMPILAR = not (a.sin_psarc or conf.get("compilar_psarc", "si").lower() in ("no", "false", "0"))
    SIN_INTERNET = a.sin_internet or conf.get("buscar_caratulas", "si").lower() in ("no", "false", "0")
    if COMPILAR and not ruta_cdlc_pack().exists():
        log(T(f"Aviso: no encuentro {ruta_cdlc_pack()}; sólo se generarán los proyectos .rs2dlc",
              f"Warning: {ruta_cdlc_pack()} not found; only the .rs2dlc projects will be created"))
        COMPILAR = False
    if COMPILAR:
        CARPETA_PSARC.mkdir(parents=True, exist_ok=True)
    espera = 60
    try:
        espera = int(conf.get("espera_preguntas", 60))
    except ValueError:
        pass
    preguntas = Preguntas(espera, activas=not a.sin_preguntas)
    if not (a.sin_actualizar or SIN_INTERNET or conf.get("buscar_actualizaciones", "si").lower() in no):
        if comprobar_actualizacion(preguntas):
            if os.environ.get("AUTO_CDLC_BAT"):
                raise SystemExit(10)        # procesar.bat prepara las librerías nuevas y vuelve a lanzar
            log(T("Vuelve a lanzar el programa para usar la versión nueva (antes: uv sync --frozen).",
                  "Launch the program again to use the new version (first: uv sync --frozen)."))
            return
    entradas = [Path(e) for e in a.entradas] or [AQUI / "entrada"]
    archivos = []
    for e in entradas:
        if e.is_dir():
            archivos += sorted(p for p in e.iterdir() if p.suffix.lower() in EXTENSIONES)
        elif e.suffix.lower() in EXTENSIONES and e.exists():
            archivos.append(e)
        else:
            log(T(f"Ignoro {e} (no existe o no es audio)", f"Ignoring {e} (doesn't exist or isn't audio)"))
    if not archivos:
        log(T("No hay canciones que procesar. Mete los mp3 en la carpeta 'entrada'.",
              "No songs to process. Put your mp3s in the 'entrada' folder."))
        return
    salida = Path(a.salida); salida.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin()
    global PUA_FORZADA
    cola = planificar(archivos, salida, a.forzar, preguntas)
    if cola is None:
        log(T("Cancelado: no se procesa nada.", "Cancelled: nothing is processed."))
        return
    if not cola:
        log(T("No hay nada pendiente. (Para repetir canciones ya hechas, usa --forzar.)",
              "Nothing pending. (To redo songs already processed, use --forzar.)"))
        return
    registro = Registro(salida / time.strftime("registro_%Y-%m-%d_%H-%M.txt"), len(cola), a.forzar)
    registro.cabecera += T("Discos: ", "Albums: ") + " || ".join(
        f"{k[0]} > {k[1]} (tono {aj['tono']}, púa {aj['pua']})"
        for k, aj in dict((k, aj) for _, k, aj in cola).items()) + "\n"
    ok, fallos = 0, []
    for i, (r, disco, aj) in enumerate(cola, 1):
        TONO_MODO = aj["tono"]
        PUA_FORZADA = {"pua": True, "dedos": False}.get(aj["pua"])
        log(f"\n[{i}/{len(cola)}] {r.name}  ({disco[0]} > {disco[1]})")
        t0 = time.time()
        try:
            estado, resumen = procesar(r, salida, True)
            ok += estado == "ok"
            registro.cancion(i, r, estado, resumen, time.time() - t0, destino(r, salida)[1] / "informe.txt")
            if estado == "ok":
                enviar_cancion(r, estado, resumen, destino(r, salida)[1])
        except Exception as ex:
            import traceback
            primera = str(ex).strip().splitlines()[0] if str(ex).strip() else type(ex).__name__
            fallos.append((r.name, primera)); log(f"  ERROR: {primera}")
            try:
                carpeta = destino(r, salida)[1]
            except Exception:
                carpeta = salida / r.stem
            if carpeta.is_dir() and not any(carpeta.iterdir()):
                carpeta.rmdir()
            import json
            traza = traceback.format_exc() + "\nDiagnóstico hasta el fallo: " + json.dumps(
                DIAG, ensure_ascii=False, separators=(",", ":"), default=str)
            registro.cancion(i, r, "error", str(ex), time.time() - t0, None, traza)
            enviar_cancion(r, "error", str(ex), carpeta if carpeta.is_dir() else None, traza)
    registro.cerrar(ok, len(fallos))
    log(T(f"\nTerminado: {ok} bien, {len(fallos)} con error. Resultados en: {salida}",
          f"\nFinished: {ok} OK, {len(fallos)} with errors. Results in: {salida}"))
    for n, e in fallos:
        log(f"  - {n}: {e}")
    log(T(f"Registro de esta tanda (el que me puedes pasar): {registro.ruta.name}",
          f"Log of this batch (attach it if something goes wrong): {registro.ruta.name}"))
    if COMPILAR:
        log(T(f"Los .psarc están en: {CARPETA_PSARC}", f"The .psarc files are in: {CARPETA_PSARC}"))


if __name__ == "__main__":
    main()

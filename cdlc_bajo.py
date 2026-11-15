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
VERSION = "2.4"
SIN_INTERNET = False      # --sin-internet o configuracion.txt
DIAG = {}                 # diagnóstico de la canción en curso (lo rellenan las etapas; va a diagnostico.json)
COMPILAR = True           # compilar .psarc con herramientas/cdlc-pack
CARPETA_PSARC = None
WWISE = None
PARTIR_REPETIDAS = True    # cortar notas largas donde el bajo vuelve a pulsar; configuracion.txt: partir_repetidas
UMBRAL_REATAQUE_DB = 3.0   # subida de energía mínima para considerar un nuevo golpe; configuracion.txt: umbral_reataque_db
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
PUA_MARGEN_DB = 1.0       # a menos de 1 dB del umbral se avisa de que conviene comprobarlo de oído
SPM = 16                   # semicorcheas por compás (4/4)
MARGEN_INICIAL = 0.5       # s de silencio antes del compás COUNT
BPM_MIN, BPM_MAX = 60, 180


def log(msg):
    print(msg, flush=True)


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
    # nombre con la regla de la 2.1.1 ('?' y ':' cambiados por '-'): si ya existe, se reutiliza
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
            log(f"  Descargando el modelo de Beat This! (una sola vez, 81 MB)...")
            tmp = ruta.with_suffix(".parcial")
            urllib.request.urlretrieve(url, tmp)
            if valido(tmp):
                tmp.replace(ruta); return ruta
            tmp.unlink(missing_ok=True)
        except Exception as ex:
            DIAG.setdefault("beat_this_descarga", []).append(f"{url.split('/')[2]}: {str(ex)[:120]}")
    modelo_beat_this.fallo = True
    log("  Aviso: no he podido descargar el modelo de Beat This!; el tiempo 1 sale solo de madmom.")
    return None


def activacion_beat_this(wav_mezcla):
    """Probabilidad de beat y de tiempo 1 de Beat This! (CPJKU, 2024), a 100 tramas/s como madmom."""
    ckpt = modelo_beat_this()
    if ckpt is None:
        return None, None
    from beat_this.inference import Audio2Frames, File2Beats
    from beat_this.preprocessing import load_audio
    sig, sr = load_audio(str(wav_mezcla))
    b, d = Audio2Frames(checkpoint_path=str(ckpt), device="cpu")(sig, sr)
    act = np.stack([1 / (1 + np.exp(-b.numpy())), 1 / (1 + np.exp(-d.numpy()))], 1)
    beats, _ = File2Beats(checkpoint_path=str(ckpt), device="cpu", dbn=False)(str(wav_mezcla))
    return np.repeat(act, 2, axis=0), np.asarray(beats)


def detectar_beats(wav_mezcla):
    """Beats con madmom (DBN, tempo limitado a 60-180) y activación de 'tiempo 1'.
    El tiempo 1 sale de Beat This! cuando cuenta los mismos beats que madmom; si cuenta al doble o a la
    mitad (pasa en canciones rápidas) o no está disponible, de la red de compases de madmom."""
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    from madmom.features.downbeats import RNNDownBeatProcessor
    beats = np.asarray(DBNBeatTrackingProcessor(fps=100, min_bpm=BPM_MIN, max_bpm=BPM_MAX)(
        RNNBeatProcessor()(str(wav_mezcla))))
    act = np.asarray(RNNDownBeatProcessor()(str(wav_mezcla)))
    info = {"motor_tiempo_1": "madmom"}
    try:
        act_bt, beats_bt = activacion_beat_this(wav_mezcla)
    except Exception as ex:
        act_bt, beats_bt = None, None
        info["beat_this_error"] = str(ex)[:200]
    if act_bt is not None and len(beats_bt) > 8 and len(beats) > 8:
        r = float(np.median(np.diff(beats_bt)) / np.median(np.diff(beats)))
        n = min(len(act), len(act_bt))
        info["beat_this_relacion_tempo"] = round(r, 2)
        if 0.85 < r < 1.15:
            act = act_bt[:n].copy(); info["motor_tiempo_1"] = "beat_this"
        else:
            # Beat This! cuenta el pulso al doble o a la mitad: su "tiempo 1" marca medios compases (o dos
            # compases) y confundiría al detector de compases; se queda solo madmom
            info["motor_tiempo_1"] = "madmom (beat_this a otro tempo)"
    DIAG["deteccion_pulso"] = info
    return beats, act


# probabilidades de compases irregulares (por compás): bajas para que sólo aparezcan con evidencia clara
P_COMPAS = {2: 0.003, 3: 0.005, 5: 0.005, 6: 0.002}


def compases_viterbi(a):
    """Posición de cada beat dentro de su compás (0 = tiempo 1), compás a compás.
    Por defecto 4/4; admite compases sueltos de 2, 3, 5 o 6 tiempos si la red lo indica claramente."""
    K = 6
    LT = np.full((K, K), -np.inf)
    LT[0, 1] = 0.0
    LT[1, 2], LT[1, 0] = np.log(1 - P_COMPAS[2]), np.log(P_COMPAS[2])
    LT[2, 3], LT[2, 0] = np.log(1 - P_COMPAS[3]), np.log(P_COMPAS[3])
    LT[3, 0], LT[3, 4] = np.log(1 - P_COMPAS[5] - P_COMPAS[6]), np.log(P_COMPAS[5] + P_COMPAS[6])
    p6 = P_COMPAS[6] / (P_COMPAS[5] + P_COMPAS[6])
    LT[4, 0], LT[4, 5] = np.log(1 - p6), np.log(p6)
    LT[5, 0] = 0.0
    a = np.clip(a, 1e-3, 1 - 1e-3)
    em = np.stack([np.log(a)] + [np.log(1 - a)] * (K - 1), axis=1)       # (N, K)
    N = len(a)
    d = np.full(K, -np.inf); d[:4] = np.log(0.25); d = d + em[0]
    bp = np.zeros((N, K), dtype=int)
    for i in range(1, N):
        c = d[:, None] + LT                    # desde (fila) -> hacia (columna)
        bp[i] = c.argmax(0); d = c.max(0) + em[i]
    pos = np.zeros(N, dtype=int); pos[-1] = int(d.argmax())
    for i in range(N - 1, 0, -1):
        pos[i - 1] = bp[i, pos[i]]
    return pos


def construir_grid(beats, act, duracion):
    """Devuelve grid de beats (cubre desde antes del segundo 0 hasta el final), índices de inicio de compás
    (el último es la marca de fin), tempo, confianza del tiempo 1 y compases irregulares."""
    med = float(np.median(np.diff(beats)))
    fr = np.clip(np.round(beats * 100).astype(int), 0, len(act) - 1)
    a = np.array([act[max(0, f - 2):f + 3, 1].max() for f in fr])
    pos = compases_viterbi(a)
    # En el final (ritardando, fundido, nota larga) los beats son poco fiables y salen compases "irregulares"
    # falsos: los últimos 3 compases se fuerzan a 4/4, empezando en el último tiempo 1 anterior.
    corte = len(pos) - 12
    if corte > 4:
        inicio = max(i for i in range(corte + 1) if pos[i] == 0)
        pos = pos.copy()
        pos[inicio:] = np.arange(len(pos) - inicio) % 4
    # hacia atrás: completar el compás del primer beat y añadir compases de 4 hasta cubrir el segundo 0
    n_pre = int(pos[0])
    while beats[0] - n_pre * med > 0:
        n_pre += 4
    grid = list(beats[0] - k * med for k in range(n_pre, 0, -1)) + list(beats)
    posg = [(int(pos[0]) - k) % 4 for k in range(n_pre, 0, -1)] + list(pos)
    # hacia delante: seguir en 4/4 hasta pasar el final y cerrar el compás (el último beat es tiempo 1 = fin)
    while grid[-1] < duracion + med or posg[-1] != 0:
        grid.append(grid[-1] + med)
        posg.append(0 if posg[-1] >= 3 else posg[-1] + 1)
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
        if len(seg) != 4:
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
    }
    return grid, barras, 60 / med, conf, irregulares


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
    out = []
    for t0, t1, p in notas:
        dentro = []
        for t in t_re[(t_re >= t0 + min_dur) & (t_re <= t1 - 0.07)]:
            # tiene que haber habido una caída antes de la subida: si no, es el propio ataque de la nota
            # (en graves la energía tarda en llegar a su máximo) y no un golpe nuevo
            if dentro and t - dentro[-1] < min_dur:
                continue
            ini = fr(dentro[-1] if dentro else t0)
            i = fr(t)
            antes = e[ini:max(ini, i - w1)]          # tramo previo al valle
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
    out, usadas, cambiadas = [], 0, 0
    for t0, t1, p in notas:
        a = int(t0 * 100); b = max(a + 1, int((t0 + 0.6 * (t1 - t0)) * 100))
        ok = per[a:b] > 0.3
        if ok.sum() >= 1:
            q = int(round(float(np.median(midi[a:b][ok]))))
            if 20 <= q <= 43 + TRASTE_MAX:
                usadas += 1; cambiadas += q != p; p = q
        out.append((t0, t1, p))
    return out, {"notas_con_tono_crepe": usadas, "distintas_de_pyin": cambiadas,
                 "periodicidad_media": round(float(np.mean(per)), 3)}


def transcribir(bajo_wav, semicorchea=None):
    import librosa
    y, _ = librosa.load(str(bajo_wav), sr=SR, mono=True)
    o_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    ataques = librosa.onset.onset_detect(onset_envelope=o_env, sr=SR, hop_length=HOP,
                                         backtrack=True, units="time")
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
            notas.append((float(t0), float(t1), p))
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
    req = urllib.request.Request(url, headers={"User-Agent": f"cdlc-bajo/{VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_bytes(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": f"cdlc-bajo/{VERSION}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def _es_recopilatorio(album):
    """Recopilatorios, directos y similares (se prefieren los discos originales)."""
    import re
    return bool(re.search(r"grandes|greatest|best of|lo mejor|esencial|essential|imprescindible|colecci|collection|recopila|"
                          r"antolog|anthology|hits|exitos|en directo|en vivo|live|directo|sus canciones|"
                          r"edicion especial|deluxe|remaster|karaoke|tribut", _normalizar(album))
                or re.fullmatch(r"(cd|disc|disco|vol|volumen|volume) ?\d*", _normalizar(album)))


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
    img, origen = None, "generada"
    if caratula:
        try:
            img = Image.open(io.BytesIO(_http_bytes(caratula["url"]))).convert("RGB")
            origen = f"de {caratula['fuente']}"
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
            origen = "incrustada en el mp3"
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
    grupos = {}
    for k, n in enumerate(tab):
        bi = n[0] / 4 + 4                       # posición en beats del audio (con COUNT)
        c = int(np.clip(np.searchsorted(inicios, bi + 1e-6, side="right") - 1, 0, len(compases) - 1))
        b, nb = compases[c]
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
    return nivel


def escribir_xml_rs(ruta, completo, compases, tab, cuerdas, cents, pua, meta, duracion_audio):
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
    w("<!-- cdlc-bajo -->")
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
    w(f'  <arrangementProperties represent="1" bonusArr="0" standardTuning="{estandar}" nonStandardChords="0" '
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
        bloques = compases_musica[::paso]
        cortes = [beats[b] for b in bloques]
        cortes[0] = t_musica
        lim = cortes + [t_end]
        nivel_nota = niveles_dd(tab, compases, completo) if DD_MODO == "propia" else np.full(len(notas), 0)
        frases, iteraciones, firmas = [("COUNT", 0)], [(t_count, 0)], {}
        conjuntos_por_iter = []
        for k in range(len(cortes)):
            idx = [i for i, n in enumerate(notas) if lim[k] - 1e-4 <= n[0] < lim[k + 1] - 1e-4]
            # versiones distintas de la frase, de más fácil a completa (se quitan las repetidas)
            versiones = []
            for d in range(len(NIVELES_DD)) if DD_MODO == "propia" else [0]:
                v = [i for i in idx if nivel_nota[i] <= d]
                if v and (not versiones or v != versiones[-1]):
                    versiones.append(v)
            if DD_INICIAL > 0 and idx:
                # dificultad inicial: cinco escalones desde el % pedido hasta la frase completa. Las notas
                # entran por importancia rítmica (compás, medio compás, tiempo, corchea) y, a igualdad,
                # las más largas primero
                orden = sorted(idx, key=lambda i: (nivel_nota[i], -(tab[i][1] - tab[i][0]), i))
                versiones = []
                for f in np.linspace(DD_INICIAL / 100, 1.0, len(NIVELES_DD)):
                    v = sorted(orden[:max(1, int(np.ceil(f * len(idx))))])
                    if not versiones or v != versiones[-1]:
                        versiones.append(v)
            if not versiones:
                versiones = [[]]
            # frases que se repiten (estribillo, estrofa...) comparten nombre y Rocksmith suma su progreso.
            # Se comparan con tolerancia: la transcripción nunca sale idéntica en dos repeticiones.
            slot0 = (bloques[k] - 4) * 4
            firma = {(int(tab[i][0] - slot0), int(tab[i][2])) for i in idx}
            pid = None
            for ref, (fid, _) in firmas.items():
                otra = set(ref)
                if (not firma and not otra) or (firma and otra and
                                                len(firma & otra) / max(len(firma), len(otra)) >= 0.75):
                    pid = fid
                    break
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
    DIAG["dificultad"] = {"modo": DD_MODO, "inicial_pct": DD_INICIAL, "niveles": len(niveles),
                          "notas_por_nivel": [len(n) for n in niveles],
                          "frases_distintas": len(frases) - 2, "repeticiones_de_frase": len(iteraciones) - 2,
                          "secciones": len(secciones),
                          "niveles_por_frase": " ".join(str(x) for x in nivel_frase) if nivel_frase else None}
    return {"notas": notas, "anclas": anclas, "t_count": t_count, "t_musica": t_musica, "t_end": t_end,
            "niveles": [len(n) for n in niveles], "frases": len(iteraciones) - 2}


def tempo_medio_aprox(beats, t):
    i = int(np.clip(np.searchsorted(beats, t), 1, len(beats) - 1))
    return 60.0 / max(beats[i] - beats[i - 1], 1e-3)


def escribir_proyecto(ruta, meta, xml, ogg, preview, inicio_preview, portada, cuerdas, cents, pua):
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
                "Name": 3, "RouteMask": 4, "Priority": 0, "ScrollSpeed": 1.3,
                "BassPicked": bool(pua),
                "Tuning": offsets,
                "TuningPitch": round(440 * 2 ** (cents / 1200), 2),
                "BaseTone": "bass", "Tones": [],
                "MasterID": int(semilla % 2_000_000_000) + 1,
                "PersistentID": str(uuid.UUID(int=(semilla << 96) | (semilla << 32) | 0xC0FFEE)),
            }],
        }],
        "Tones": [TONO_BAJO],
    }
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
    v = {"cdlc-bajo": VERSION, "python": platform.python_version(), "sistema": platform.platform()}
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
        log(f"  (ya procesada, la salto; usa --forzar para repetir)")
        return "saltada", ""
    dest.mkdir(parents=True, exist_ok=True)
    log(f"  {artista} - {titulo}  (de {fuente})")
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

        log("  [1/6] Separando el bajo...")
        bajo = separar_bajo(mezcla, tmp)
        marca("separar_bajo")
        DIAG["sonoridad"] = sonoridades(mezcla, bajo)
        log("  [2/6] Detectando beats y compases...")
        beats, act = detectar_beats(mezcla_mono)
        grid, barras, bpm, conf, irregulares = construir_grid(beats, act, duracion)
        marca("beats_y_compases")
        log("  [3/6] Transcribiendo notas...")
        y, notas, n_ataques, n_cqt, cents, pua, pitches_pyin = transcribir(bajo, 60.0 / bpm / 4)
        marca("transcribir")
        if not notas:
            raise RuntimeError("no se ha detectado ninguna nota de bajo")
        log("  [4/6] Cuantizando y digitando...")
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

        log("  [5/6] Escribiendo archivos...")
        escribir_svl(dest / f"{nombre}.svl", completo, etiquetas)
        n_gp = escribir_gp5(dest / f"{nombre}.gp5", tab, compases, tempos, artista, titulo, cuerdas)
        cola = max(3.0, completo[-1] - (duracion + pad) + 1.0)
        pad_ms = int(round(pad * 1000))
        ffmpeg("-i", str(mezcla), "-af", f"adelay={pad_ms}|{pad_ms},apad=pad_dur={cola:.2f}",
               "-ar", "44100", "-c:a", "libvorbis", "-q:a", "6", str(dest / f"{nombre}.ogg"))

        # proyecto listo para DLC Builder: XML del arreglo, preview, portada y .rs2dlc
        meta = {"artista": artista, "titulo": titulo, **album_y_anio(ruta)}
        caratula = None if SIN_INTERNET else buscar_caratula(artista, titulo)
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
                                   pua >= PUA_UMBRAL_DB if not np.isnan(pua) else False, meta, duracion_ogg)
        inicio_prev = escribir_preview(dest / f"{nombre}.ogg", dest / f"{nombre}_preview.ogg", duracion_ogg)
        portada, origen_portada = crear_portada(ruta, dest / "portada.png", artista, titulo, caratula)
        escribir_proyecto(dest / f"{nombre}.rs2dlc", meta, xml_path, dest / f"{nombre}.ogg",
                          dest / f"{nombre}_preview.ogg", inicio_prev, portada, cuerdas, cents_aplicado,
                          pua >= PUA_UMBRAL_DB if not np.isnan(pua) else False)
        problemas = comprobar_dlc_builder(dest / f"{nombre}.rs2dlc")
        marca("escribir_archivos")
        psarcs, error_psarc = [], "desactivada (--sin-psarc)"
        if COMPILAR and not problemas:
            log("  [6/6] Compilando el .psarc (Wwise + DD)...")
            psarcs, error_psarc = compilar_psarc(dest / f"{nombre}.rs2dlc", CARPETA_PSARC, WWISE)
            marca("compilar_psarc")
        elif problemas:
            error_psarc = "no se compila: el proyecto tiene problemas"

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
    txt_afin = (f"AFINACIÓN: {afin_nombre}  (cuerdas {' '.join(nom(c) for c in cuerdas)})\n"
                f"  Nota grave repetida más baja: {nom(nota_grave)}"
                + (f" | {movidas} notas sueltas cambiadas de octava para que quepan" if movidas else "") + "\n")
    if afin_nombre != "E estándar":
        txt_afin += ("  -> Ya va en el proyecto (y en el .gp5). Reafina el bajo antes de tocar;\n"
                     "     el afinador de Rocksmith te la pedirá al empezar la canción.\n")
    # --- desvío en cents ---
    la = 440 * 2 ** (cents / 1200)
    txt_cents = f"REFERENCIA DE AFINACIÓN DE LA GRABACIÓN: {cents:+.0f} cents (La = {la:.1f} Hz)\n"
    if cents_aplicado:
        txt_cents += (f"  -> Desvío grande (>= {UMBRAL_CENTS:.0f} cents): va en el proyecto como Tuning Pitch {la:.2f}.\n"
                      "     El afinador de Rocksmith te pedirá afinar así para empastar con el disco.\n")
    elif abs(cents) >= 5:
        txt_cents += (f"  -> Por debajo del umbral ({UMBRAL_CENTS:.0f} cents): se deja en 440 para no reafinar.\n"
                      "     (Sí se ha tenido en cuenta al reconocer las notas.)\n")
    else:
        txt_cents += "  -> Prácticamente a 440 Hz: no hace falta tocar nada.\n"
    # --- púa ---
    if np.isnan(pua):
        veredicto = "sin datos suficientes"
    elif pua >= PUA_UMBRAL_DB:
        veredicto = "PROBABLEMENTE CON PÚA"
    else:
        veredicto = "probablemente con dedos"
    if not np.isnan(pua) and abs(pua - PUA_UMBRAL_DB) < PUA_MARGEN_DB:
        veredicto += " (cerca del umbral: compruébalo de oído)"
    con_pua = veredicto.startswith("PROB")
    txt_pua = (f"PÚA O DEDOS: {veredicto}  [índice {pua:.1f} dB; púa a partir de {PUA_UMBRAL_DB:.0f}]\n"
               + ("  -> Ya va marcado 'Picked' en el proyecto.\n" if con_pua else
                  "  -> Si en realidad es con púa, marca 'Picked' en la ficha del arreglo en DLC Builder.\n"))
    txt_proyecto = ("PROYECTO DE DLC BUILDER: " + (f"{nombre}.rs2dlc listo (pasa las comprobaciones)\n"
                    if not problemas else "con problemas: " + "; ".join(problemas) + "\n")
                    + "  -> Ábrelo en DLC Builder (Project > Open Project, o arrástralo a la ventana) y pulsa Build.\n")
    txt_psarc = ("PSARC: " + (", ".join(Path(x).name for x in psarcs) + f"  (en {CARPETA_PSARC})" if psarcs
                  else f"no generado ({error_psarc})") + "\n"
                 + ("" if psarcs else "  -> Puedes compilarlo a mano abriendo el .rs2dlc en DLC Builder.\n"))
    txt_portada = (f"PORTADA: {origen_portada}" + (f" | álbum: {meta['album']}" if meta['album'] else "")
                   + f" | año: {meta['year']}\n")
    informe = (f"Canción: {artista} - {titulo}  (nombre tomado de {fuente})\nArchivo: {ruta.name}\n\n" + txt_psarc + txt_proyecto + txt_portada + "\n"
               + txt_afin + txt_cents + txt_pua + "\n"
               f"Tempo mediano: {bpm:.1f} BPM | confianza del tiempo 1: {conf*100:.0f}%\n"
               f"Ataques detectados: {n_ataques} | notas: {len(notas)} (resueltas por CQT: {n_cqt}) | "
               f"en la tablatura: {n_gp}\n"
               f"Desfase de ataques corregido: {desfase*1000:.0f} ms | notas dudosas al cuantizar: {ambiguas*100:.0f}%\n"
               f"Notas por compás (mediana): {np.median(per):.0f}\n"
               f"Silencio inicial añadido: {pad:.3f} s | compases: {n_compases} (el 1 es el COUNT, vacío)\n"
               + (f"Compases irregulares (cambian el 4/4): " + ", ".join(
                      f"compás {c} en {n}/4 ({mmss(completo[compases[c - 1][0]] - pad)})" for c, n in irregulares)
                  + "\n  -> El minuto es el de la canción original. Ya van en el proyecto y en el .gp5\n"
                  + "     (si montas por EOF, acepta importar los compases / time signatures).\n"
                  if irregulares else "Compases irregulares: ninguno (todo 4/4)\n")
               + f"Tiempo de proceso: {time.time()-t_ini:.0f} s\n")
    (dest / "informe.txt").write_text(informe, encoding="utf-8")
    # diagnóstico completo (para depurar): diagnostico.json en la carpeta y en el registro general
    DIAG["tablatura"] = resumen_tablatura(tab, compases, info_xml)
    DIAG["resultado"] = {"afinacion": afin_nombre, "cents_aplicados": round(cents_aplicado, 1),
                         "pua": bool(not np.isnan(pua) and pua >= PUA_UMBRAL_DB), "indice_pua": round(float(pua), 2),
                         "tempo": round(bpm, 1), "silencio_inicial_s": round(pad, 3), "portada": origen_portada,
                         "album": meta["album"], "año": meta["year"], "problemas_proyecto": problemas,
                         "psarc": [Path(x).name for x in psarcs], "error_psarc": None if psarcs else error_psarc,
                         "compases_irregulares": [f"{c}:{n}/4" for c, n in irregulares]}
    DIAG["tiempos_s"]["total"] = round(time.time() - t_ini, 1)
    import json
    (dest / "diagnostico.json").write_text(json.dumps(DIAG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    aviso = "  ¡OJO! tiempo 1 dudoso, revisa con el archivo de clics" if conf < 0.6 else ""
    extra = f" | {afin_nombre}" + (f" | Tuning Pitch {cents_aplicado:+.0f} cents" if cents_aplicado else "") + \
            (" | púa" if veredicto.startswith("PROB") else "") + \
            (f" | {len(irregulares)} compases irregulares" if irregulares else "")
    if problemas:
        aviso += "  ¡OJO! el proyecto tiene problemas, mira el informe"
    extra += " | psarc OK" if psarcs else (f" | sin psarc: {error_psarc}" if COMPILAR else "")
    resumen = f"{n_gp} notas, {bpm:.0f} BPM, dudosas {ambiguas*100:.0f}%{extra}{aviso}"
    log(f"  OK: {resumen}")
    return "ok", resumen


# ---------------- 7. compilación a .psarc (cdlc-pack, librerías de DLC Builder) ----------------
def leer_configuracion():
    """configuracion.txt junto al script: líneas 'clave = valor' (# para comentarios)."""
    conf = {}
    ruta = AQUI / "configuracion.txt"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
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
        return [], f"no encuentro {exe}"
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
                    log("  AVISO: el psarc solo tiene un nivel de dificultad (sin DD no habrá porcentaje)")
                if "notas_puntuables=" in l:
                    puntuables = float(l.split("notas_puntuables=")[1].split()[0])
                    maximas = int(l.split("notas_max=")[1].split()[0])
                    if abs(puntuables - maximas) > 0.5:
                        log(f"  AVISO: el juego puntuará sobre {puntuables:.0f} notas y la canción tiene {maximas}")
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
        self.cabecera = (f"REGISTRO cdlc-bajo {VERSION} | {time.strftime('%Y-%m-%d %H:%M')}\n"
                         f"Sistema: {platform.platform()} | Python {platform.python_version()}\n"
                         f"Canciones en la tanda: {total}" + (" | --forzar" if forzar else "") + "\n")
        self.lineas, self.informes, self.errores, self.final = [], [], [], "(tanda en curso)\n"
        self.diagnosticos = []
        try:
            import json
            self.cabecera += "Versiones: " + json.dumps(versiones(), ensure_ascii=False) + "\n"
            self.cabecera += (f"Configuración: psarc={'si' if COMPILAR else 'no'} | carpeta={CARPETA_PSARC} | "
                              f"carátulas={'no' if SIN_INTERNET else 'si'} | umbral_cents={UMBRAL_CENTS} | dificultad={DD_MODO} (inicial {DD_INICIAL:.0f} %) | "
                              f"wwise={WWISE or 'automático'} | partir_repetidas={'si' if PARTIR_REPETIDAS else 'no'} "
                              f"({UMBRAL_REATAQUE_DB} dB) | tono_crepe={'si' if TONO_CREPE else 'no'}\n")
        except Exception:
            pass
        self._guardar()

    def cancion(self, i, ruta, estado, resumen, segundos, informe, traza=None):
        etiqueta = {"ok": "OK", "saltada": "SALTADA (ya procesada)", "error": "ERROR"}[estado]
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
        self.final = f"Terminado: {ok} bien, {errores} con error, en {(time.time() - self.inicio) / 60:.1f} min\n"
        self._guardar()

    def _guardar(self):
        sep = "\n" + "=" * 78 + "\n"
        texto = (self.cabecera + "\n" + "\n".join(self.lineas) + "\n\n" + self.final
                 + (sep + "ERRORES DETALLADOS" + sep + "\n".join(self.errores) if self.errores else "")
                 + (sep + "INFORMES" + sep + ("\n" + "-" * 78 + "\n").join(self.informes) if self.informes else "")
                 + (sep + "DIAGNÓSTICO (una línea JSON por canción, para depurar)" + sep
                    + "\n".join(self.diagnosticos) + "\n" if self.diagnosticos else ""))
        self.ruta.write_text(texto, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="mp3 -> tablatura de bajo + mapa de beats para EOF")
    ap.add_argument("entradas", nargs="*", help="archivos o carpetas (por defecto: carpeta 'entrada')")
    ap.add_argument("--salida", default=str(AQUI / "salida"))
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--psarc", help="carpeta de destino de los .psarc (por defecto: carpeta 'psarc')")
    ap.add_argument("--wwise", help="ruta a WwiseConsole.exe (normalmente se encuentra sola)")
    ap.add_argument("--sin-psarc", action="store_true", help="no compilar: deja sólo el proyecto .rs2dlc")
    ap.add_argument("--sin-internet", action="store_true", help="no buscar carátulas en internet")
    a = ap.parse_args()
    global COMPILAR, CARPETA_PSARC, WWISE, SIN_INTERNET, UMBRAL_CENTS, DD_MODO, DD_INICIAL
    global PARTIR_REPETIDAS, UMBRAL_REATAQUE_DB, TONO_CREPE
    conf = leer_configuracion()
    no = ("no", "false", "0")
    PARTIR_REPETIDAS = conf.get("partir_repetidas", "si").lower() not in no
    TONO_CREPE = conf.get("tono_crepe", "si").lower() not in no
    try:
        UMBRAL_REATAQUE_DB = float(conf.get("umbral_reataque_db", UMBRAL_REATAQUE_DB))
    except ValueError:
        log("Aviso: umbral_reataque_db no es un número en configuracion.txt; uso 3")
    try:
        UMBRAL_CENTS = float(conf.get("umbral_cents", UMBRAL_CENTS))
        dd = conf.get("dificultad", DD_MODO).strip().lower()
        DD_MODO = {"propia": "propia", "dlcbuilder": "dlcbuilder", "dlc builder": "dlcbuilder",
                   "ninguna": "ninguna", "no": "ninguna"}.get(dd, "propia")
        DD_INICIAL = min(95.0, max(0.0, float(str(conf.get("dificultad_inicial", DD_INICIAL)).replace("%", "").strip())))
    except ValueError:
        log("Aviso: umbral_cents o dificultad_inicial no es un número en configuracion.txt; reviso los valores por defecto")
    CARPETA_PSARC = Path(a.psarc or conf.get("carpeta_psarc") or (AQUI / "psarc"))
    WWISE = a.wwise or conf.get("wwise") or None
    COMPILAR = not (a.sin_psarc or conf.get("compilar_psarc", "si").lower() in ("no", "false", "0"))
    SIN_INTERNET = a.sin_internet or conf.get("buscar_caratulas", "si").lower() in ("no", "false", "0")
    if COMPILAR and not ruta_cdlc_pack().exists():
        log(f"Aviso: no encuentro {ruta_cdlc_pack()}; sólo se generarán los proyectos .rs2dlc")
        COMPILAR = False
    if COMPILAR:
        CARPETA_PSARC.mkdir(parents=True, exist_ok=True)
    entradas = [Path(e) for e in a.entradas] or [AQUI / "entrada"]
    archivos = []
    for e in entradas:
        if e.is_dir():
            archivos += sorted(p for p in e.iterdir() if p.suffix.lower() in EXTENSIONES)
        elif e.suffix.lower() in EXTENSIONES and e.exists():
            archivos.append(e)
        else:
            log(f"Ignoro {e} (no existe o no es audio)")
    if not archivos:
        log("No hay canciones que procesar. Mete los mp3 en la carpeta 'entrada'.")
        return
    salida = Path(a.salida); salida.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin()
    registro = Registro(salida / time.strftime("registro_%Y-%m-%d_%H-%M.txt"), len(archivos), a.forzar)
    ok, fallos = 0, []
    for i, r in enumerate(archivos, 1):
        log(f"\n[{i}/{len(archivos)}] {r.name}")
        t0 = time.time()
        try:
            estado, resumen = procesar(r, salida, a.forzar)
            ok += estado == "ok"
            registro.cancion(i, r, estado, resumen, time.time() - t0, destino(r, salida)[1] / "informe.txt")
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
    registro.cerrar(ok, len(fallos))
    log(f"\nTerminado: {ok} bien, {len(fallos)} con error. Resultados en: {salida}")
    for n, e in fallos:
        log(f"  - {n}: {e}")
    log(f"Registro de esta tanda (el que me puedes pasar): {registro.ruta.name}")
    if COMPILAR:
        log(f"Los .psarc están en: {CARPETA_PSARC}")


if __name__ == "__main__":
    main()

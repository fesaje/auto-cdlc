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


def metadatos(ruta):
    """Artista y título: del nombre 'Artista - Título' si lo tiene; si no, de las etiquetas del archivo."""
    stem = ruta.stem.replace("_", " ")
    if " - " in stem:
        a, t = stem.split(" - ", 1)
        return a.strip(), t.strip()
    artista, titulo = "", ""
    try:
        import mutagen
        tags = mutagen.File(str(ruta), easy=True)
        if tags:
            artista = (tags.get("artist") or [""])[0].strip()
            titulo = (tags.get("title") or [""])[0].strip()
    except Exception:
        pass
    return artista or "Desconocido", titulo or stem


def mmss(segundos):
    segundos = max(0, int(round(segundos)))
    return f"{segundos // 60}:{segundos % 60:02d}"


def album_y_anio(ruta):
    """Álbum y año de las etiquetas del archivo (si no hay: álbum vacío y año actual)."""
    album, year = "", time.localtime().tm_year
    try:
        import mutagen, re
        tags = mutagen.File(str(ruta), easy=True)
        if tags:
            album = (tags.get("album") or [""])[0].strip()
            m = re.search(r"(19|20)\d\d", (tags.get("date") or [""])[0])
            if m: year = int(m.group(0))
    except Exception:
        pass
    return {"album": album, "year": year}


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
def detectar_beats(wav_mezcla):
    """Beats (madmom DBN) y activación de 'tiempo 1' de la red de compases de madmom (100 fps)."""
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    from madmom.features.downbeats import RNNDownBeatProcessor
    beats = DBNBeatTrackingProcessor(fps=100, min_bpm=BPM_MIN, max_bpm=BPM_MAX)(
        RNNBeatProcessor()(str(wav_mezcla)))
    act = RNNDownBeatProcessor()(str(wav_mezcla))
    return np.asarray(beats), np.asarray(act)


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
    return grid, barras, 60 / med, conf, irregulares


# ---------------- 3. notas ----------------
def transcribir(bajo_wav):
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
    for i in range(len(ataques)):
        t0, t1 = limites[i], limites[i + 1]
        idx = np.where((tiempos >= t0) & (tiempos < t1))[0]
        if len(idx) < 2: continue
        seg = rms_db[idx]
        if seg.max() - pico < ENERGIA_MIN_DB: continue
        bajo = np.where(seg < seg.max() - 30)[0]
        if len(bajo) and bajo[0] > 1:
            idx = idx[:bajo[0]]; t1 = tiempos[idx[-1]]
        if t1 - t0 < DUR_MIN: continue
        ok = (~np.isnan(f0[idx])) & (vp[idx] > PYIN_MIN_PROB)
        if ok.sum() >= 2:
            p = int(round(librosa.hz_to_midi(np.median(f0[idx][ok])) - cents / 100))
            pitches_pyin.append(p)
        else:
            p = nota_cqt(idx[:max(4, len(idx) // 2)]); n_cqt += 1
        if 20 <= p <= 43 + TRASTE_MAX:
            notas.append((float(t0), float(t1), p))
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
    return float(np.median(vals)) if len(vals) >= 20 else float("nan")


# ---------------- 4. cuantización + digitación ----------------
def cuantizar(notas, grid):
    def pos(t):
        i = int(np.clip(np.searchsorted(grid, t) - 1, 0, len(grid) - 2))
        return i + (t - grid[i]) / (grid[i + 1] - grid[i])
    # la búsqueda NO puede pasar de una semicorchea: el patrón se repite cada semicorchea y, en tempos rápidos,
    # un desfase mayor desplazaría toda la tablatura una casilla entera
    semicorchea = float(np.median(np.diff(grid))) / 4
    desfase = max(np.arange(0, semicorchea, 0.002),
                  key=lambda d: np.mean(np.cos(2 * np.pi * 4 * np.array([pos(t0 + d) for t0, _, _ in notas]))))
    q = {}
    for t0, t1, p in notas:
        s0 = int(round(pos(t0 + desfase) * 4)); s1 = max(s0 + 1, int(round(pos(t1 + desfase) * 4)))
        if s0 not in q or (s1 - s0) > (q[s0][1] - q[s0][0]):
            q[s0] = [s0, s1, p]
    q = sorted(v for v in q.values() if v[0] >= 0)    # seguridad: nada antes del grid
    for i in range(len(q) - 1):
        q[i][1] = min(q[i][1], q[i + 1][0])
    q = [x for x in q if x[1] > x[0]]
    ambiguas = np.mean([abs(pos(t0 + desfase) * 4 - round(pos(t0 + desfase) * 4)) > 0.35 for t0, _, _ in notas])
    return q, desfase, ambiguas


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
    mejor = None
    for nombre, cuerdas, prior in candidatas:
        qa, movidas = ajustar_a_rango(q, cuerdas)
        tab, coste = digitar(qa, list(reversed(cuerdas)))
        puntos = coste / max(1, len(qa)) + prior
        if mejor is None or puntos < mejor[0]:
            mejor = (puntos, nombre, cuerdas, tab, movidas)
    _, nombre, cuerdas, tab, movidas = mejor
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


def crear_portada(ruta_audio, destino, artista, titulo):
    """Portada 512x512 PNG: la incrustada en el audio (recortada a cuadrado) o una generada."""
    from PIL import Image, ImageDraw, ImageFont
    import io
    img = None
    try:
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
    return destino


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


def escribir_xml_rs(ruta, completo, compases, tab, cuerdas, cents, pua, meta, duracion_audio):
    from xml.sax.saxutils import escape
    E = lambda x: escape(str(x), {'"': "&quot;"})
    offsets = [c - base for c, base in zip(cuerdas, [28, 33, 38, 43])]
    estandar = int(all(o == 0 for o in offsets))
    notas = []
    for s0, s1, _, cuerda_gp, traste in tab:
        t0, t1 = tiempo_de_slot(completo, s0), tiempo_de_slot(completo, s1)
        cuerda = 4 - cuerda_gp            # XML: 0 = la más grave
        sustain = (t1 - t0) if (s1 - s0) >= 4 else 0.0
        notas.append((t0, cuerda, traste, sustain))
    notas.sort()
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
    w('  <phrases count="3">')
    for nombre in ("COUNT", "riff", "END"):
        w(f'    <phrase name="{nombre}" maxDifficulty="0" />')
    w("  </phrases>")
    w('  <phraseIterations count="3">')
    for t, pid in ((t_count, 0), (t_musica, 1), (t_end, 2)):
        w(f'    <phraseIteration time="{t:.3f}" phraseId="{pid}"/>')
    w("  </phraseIterations>")
    for etiqueta in ("newLinkedDiffs", "linkedDiffs", "phraseProperties", "chordTemplates", "fretHandMuteTemplates"):
        w(f'  <{etiqueta} count="0"/>')
    w(f'  <ebeats count="{len(beats)}">')
    for i, t in enumerate(beats):
        w(f'    <ebeat time="{t:.3f}" measure="{medida[i]}" />' if i in medida else f'    <ebeat time="{t:.3f}" />')
    w("  </ebeats>")
    w('  <sections count="1">')
    w(f'    <section name="riff" number="1" startTime="{t_musica:.3f}"/>')
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
    w('  <levels count="1">')
    w('    <level difficulty="0">')
    w(f'      <notes count="{len(notas)}">')
    for t, cuerda, traste, sus in notas:
        extra = f' sustain="{sus:.3f}"' if sus > 0 else ""
        w(f'        <note time="{t:.3f}" string="{cuerda}" fret="{traste}"{extra} />')
    w("      </notes>")
    w('      <chords count="0"/>')
    w('      <fretHandMutes count="0"/>')
    w(f'      <anchors count="{len(anclas)}">')
    for t, f in anclas:
        w(f'        <anchor time="{t:.3f}" fret="{f}" width="4.000"/>')
    w("      </anchors>")
    w('      <handShapes count="0"/>')
    w("    </level>")
    w("  </levels>")
    w("</song>")
    Path(ruta).write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"notas": notas, "anclas": anclas, "t_count": t_count, "t_musica": t_musica, "t_end": t_end}


def escribir_proyecto(ruta, meta, xml, ogg, preview, inicio_preview, portada, cuerdas, cents, pua):
    import json, uuid, zlib
    clave = "cb" + (StringValidator_dlckey(meta["artista"])[:5] + StringValidator_dlckey(meta["titulo"])[:5])
    if len(clave) < 5:
        clave += "xxxxx"[:5 - len(clave)]
    semilla = zlib.crc32(clave.encode())
    offsets = [c - base for c, base in zip(cuerdas, [28, 33, 38, 43])] + [0, 0]
    proyecto = {
        "Version": "1",
        "DLCKey": clave,
        "ArtistName": {"Value": meta["artista"], "SortValue": meta["artista"]},
        "Title": {"Value": meta["titulo"], "SortValue": meta["titulo"]},
        "AlbumName": {"Value": meta["album"], "SortValue": meta["album"]},
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


def procesar(ruta, salida, forzar):
    import librosa, pretty_midi, soundfile as sf
    nombre = ruta.stem
    dest = salida / nombre
    if (dest / f"{nombre}.gp5").exists() and not forzar:
        log(f"  (ya procesada, la salto; usa --forzar para repetir)")
        return True
    dest.mkdir(parents=True, exist_ok=True)
    artista, titulo = metadatos(ruta)
    t_ini = time.time()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        mezcla = tmp / "mezcla.wav"
        ffmpeg("-i", str(ruta), "-vn", "-ac", "2", "-ar", "44100", str(mezcla))
        mezcla_mono = tmp / "mezcla_mono.wav"
        ffmpeg("-i", str(mezcla), "-ac", "1", str(mezcla_mono))
        duracion = sf.info(str(mezcla)).duration

        log("  [1/5] Separando el bajo...")
        bajo = separar_bajo(mezcla, tmp)
        log("  [2/5] Detectando beats y compases...")
        beats, act = detectar_beats(mezcla_mono)
        grid, barras, bpm, conf, irregulares = construir_grid(beats, act, duracion)
        log("  [3/5] Transcribiendo notas...")
        y, notas, n_ataques, n_cqt, cents, pua, pitches_pyin = transcribir(bajo)
        if not notas:
            raise RuntimeError("no se ha detectado ninguna nota de bajo")
        log("  [4/5] Cuantizando y digitando...")
        q, desfase, ambiguas = cuantizar(notas, grid)
        afin_nombre, cuerdas, tab, movidas, nota_grave = elegir_afinacion(q, pitches_pyin)

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

        log("  [5/5] Escribiendo archivos...")
        escribir_svl(dest / f"{nombre}.svl", completo, etiquetas)
        n_gp = escribir_gp5(dest / f"{nombre}.gp5", tab, compases, tempos, artista, titulo, cuerdas)
        cola = max(3.0, completo[-1] - (duracion + pad) + 1.0)
        pad_ms = int(round(pad * 1000))
        ffmpeg("-i", str(mezcla), "-af", f"adelay={pad_ms}|{pad_ms},apad=pad_dur={cola:.2f}",
               "-ar", "44100", "-c:a", "libvorbis", "-q:a", "6", str(dest / f"{nombre}.ogg"))

        # proyecto listo para DLC Builder: XML del arreglo, preview, portada y .rs2dlc
        meta = {"artista": artista, "titulo": titulo, **album_y_anio(ruta)}
        duracion_ogg = sf.info(str(dest / f"{nombre}.ogg")).duration
        xml_path = dest / f"{nombre}_bass_RS2.xml"
        info_xml = escribir_xml_rs(xml_path, completo, compases, tab, cuerdas, cents,
                                   pua >= PUA_UMBRAL_DB if not np.isnan(pua) else False, meta, duracion_ogg)
        inicio_prev = escribir_preview(dest / f"{nombre}.ogg", dest / f"{nombre}_preview.ogg", duracion_ogg)
        portada = crear_portada(ruta, dest / "portada.png", artista, titulo)
        escribir_proyecto(dest / f"{nombre}.rs2dlc", meta, xml_path, dest / f"{nombre}.ogg",
                          dest / f"{nombre}_preview.ogg", inicio_prev, portada, cuerdas, cents,
                          pua >= PUA_UMBRAL_DB if not np.isnan(pua) else False)
        problemas = comprobar_dlc_builder(dest / f"{nombre}.rs2dlc")

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
    if abs(cents) >= 5:
        txt_cents += (f"  -> Ya va en el proyecto: Tuning Pitch {la:.2f}. El afinador de Rocksmith te dejará\n"
                      "     empastado con el disco. (Si montas por EOF, ponlo a mano en DLC Builder.)\n")
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
    informe = (f"Canción: {artista} - {titulo}\nArchivo: {ruta.name}\n\n" + txt_proyecto + "\n"
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
    aviso = "  ¡OJO! tiempo 1 dudoso, revisa con el archivo de clics" if conf < 0.6 else ""
    extra = f" | {afin_nombre}" + (f" | {cents:+.0f} cents" if abs(cents) >= 5 else "") + \
            (" | púa" if veredicto.startswith("PROB") else "") + \
            (f" | {len(irregulares)} compases irregulares" if irregulares else "")
    if problemas:
        aviso += "  ¡OJO! el proyecto tiene problemas, mira el informe"
    log(f"  OK: {n_gp} notas, {bpm:.0f} BPM, dudosas {ambiguas*100:.0f}%{extra}{aviso}")
    return True


def main():
    ap = argparse.ArgumentParser(description="mp3 -> tablatura de bajo + mapa de beats para EOF")
    ap.add_argument("entradas", nargs="*", help="archivos o carpetas (por defecto: carpeta 'entrada')")
    ap.add_argument("--salida", default=str(AQUI / "salida"))
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
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
    ok, fallos = 0, []
    for i, r in enumerate(archivos, 1):
        log(f"\n[{i}/{len(archivos)}] {r.name}")
        try:
            procesar(r, salida, a.forzar); ok += 1
        except Exception as ex:
            fallos.append((r.name, str(ex))); log(f"  ERROR: {ex}")
    log(f"\nTerminado: {ok} bien, {len(fallos)} con error. Resultados en: {salida}")
    for n, e in fallos:
        log(f"  - {n}: {e}")


if __name__ == "__main__":
    main()

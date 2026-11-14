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
AFINACION = [43, 38, 33, 28]   # G2 D2 A1 E1 (cuerda 1 = la más aguda, convención Guitar Pro)
TRASTE_MAX = 20
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
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    from madmom.features.downbeats import RNNDownBeatProcessor, DBNDownBeatTrackingProcessor
    beats = DBNBeatTrackingProcessor(fps=100, min_bpm=BPM_MIN, max_bpm=BPM_MAX)(
        RNNBeatProcessor()(str(wav_mezcla)))
    db = DBNDownBeatTrackingProcessor(beats_per_bar=[4], fps=100, min_bpm=BPM_MIN, max_bpm=BPM_MAX)(
        RNNDownBeatProcessor()(str(wav_mezcla)))
    return np.asarray(beats), np.asarray(db)


def construir_grid(beats, db, duracion):
    med = float(np.median(np.diff(beats)))
    unos = db[db[:, 1] == 1, 0] if len(db) else np.array([])
    if len(unos):
        k = np.array([np.argmin(np.abs(beats - t)) for t in unos])
        votos = np.bincount(k % 4, minlength=4)
        fase = int(votos.argmax()); confianza = votos.max() / votos.sum()
    else:
        fase, confianza = 0, 0.0
    primero = fase % 4
    grid = beats[primero:]
    pre, t = [], grid[0] - med
    while t > 0.05:
        pre.insert(0, t); t -= med
    n_pre = len(pre) - (len(pre) % 4)
    if n_pre:
        grid = np.concatenate([pre[len(pre) - n_pre:], grid])
    while grid[-1] < duracion + med:
        grid = np.append(grid, grid[-1] + med)
    return grid, 60 / med, confianza


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
    FMIN = 24
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=HOP, fmin=librosa.midi_to_hz(FMIN), n_bins=72, bins_per_octave=12))
    pico = rms_db.max()

    def nota_cqt(idx):
        spec = C[:, idx].mean(axis=1); mejor, nota = -1, None
        for p in range(28, 60):
            b = p - FMIN
            s = spec[b] + 0.6 * spec[b + 12] + 0.4 * spec[b + 19] + 0.3 * spec[b + 24]
            if s > mejor: mejor, nota = s, p
        return nota

    limites = list(ataques) + [len(y) / SR]
    notas, n_cqt = [], 0
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
            p = int(round(librosa.hz_to_midi(np.median(f0[idx][ok]))))
        else:
            p = nota_cqt(idx[:max(4, len(idx) // 2)]); n_cqt += 1
        while p < AFINACION[-1]: p += 12                 # por debajo del Mi grave: octava arriba
        if p <= AFINACION[0] + TRASTE_MAX:
            notas.append((float(t0), float(t1), p))
    return y, notas, len(ataques), n_cqt


# ---------------- 4. cuantización + digitación ----------------
def cuantizar(notas, grid):
    def pos(t):
        i = int(np.clip(np.searchsorted(grid, t) - 1, 0, len(grid) - 2))
        return i + (t - grid[i]) / (grid[i + 1] - grid[i])
    desfase = max(np.arange(0, 0.15, 0.002),
                  key=lambda d: np.mean(np.cos(2 * np.pi * 4 * np.array([pos(t0 + d) for t0, _, _ in notas]))))
    q = {}
    for t0, t1, p in notas:
        s0 = int(round(pos(t0 + desfase) * 4)); s1 = max(s0 + 1, int(round(pos(t1 + desfase) * 4)))
        if s0 not in q or (s1 - s0) > (q[s0][1] - q[s0][0]):
            q[s0] = [s0, s1, p]
    q = sorted(q.values())
    for i in range(len(q) - 1):
        q[i][1] = min(q[i][1], q[i + 1][0])
    q = [x for x in q if x[1] > x[0]]
    ambiguas = np.mean([abs(pos(t0 + desfase) * 4 - round(pos(t0 + desfase) * 4)) > 0.35 for t0, _, _ in notas])
    return q, desfase, ambiguas


def digitar(q):
    capas, prev = [], None
    for _, _, p in q:
        capa = []
        for s, o in enumerate(AFINACION):
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
    camino, j = [], int(np.argmin([x[0] for x in capas[-1]]))
    for capa in reversed(capas):
        _, f, s, bp = capa[j]; camino.append((s, f)); j = max(bp, 0)
    camino.reverse()
    return [[q[i][0], q[i][1], q[i][2], camino[i][0], camino[i][1]] for i in range(len(q))]


# ---------------- 5. salidas ----------------
def escribir_svl(ruta, beats):
    with open(ruta, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE sonic-visualiser>\n<sv>\n  <data>\n')
        f.write(f'    <model id="1" name="Beats" sampleRate="44100" start="0" end="{int(beats[-1]*44100)}" '
                'type="sparse" dimensions="1" resolution="1" notifyOnAdd="true" dataset="0" />\n')
        f.write('    <dataset id="0" dimensions="1">\n')
        for i, t in enumerate(beats):
            f.write(f'      <point frame="{int(round(t*44100))}" label="{i % 4 + 1}" />\n')
        f.write('    </dataset>\n  </data>\n</sv>\n')


def escribir_gp5(ruta, tab, n_compases, tempos, artista, titulo):
    import guitarpro
    from guitarpro import models as gp
    song = gp.Song(); song.title = titulo; song.artist = artista; song.tempo = tempos[0]
    pista = song.tracks[0]; pista.name = "Bajo"; pista.channel.instrument = 33
    pista.strings = [gp.GuitarString(i + 1, v) for i, v in enumerate(AFINACION)]; pista.fretCount = 24
    h0 = song.measureHeaders[0]; h0.timeSignature.numerator = 4; h0.timeSignature.denominator.value = 4
    while len(song.measureHeaders) < n_compases:
        h = gp.MeasureHeader(); h.number = len(song.measureHeaders) + 1
        h.timeSignature.numerator = 4; h.timeSignature.denominator.value = 4
        song.addMeasureHeader(h); pista.measures.append(gp.Measure(pista, h))
    por_slot = {n[0] + SPM: n for n in tab}; inicios = sorted(por_slot)
    DUR = {16: (1, False), 12: (2, True), 8: (2, False), 6: (4, True), 4: (4, False),
           3: (8, True), 2: (8, False), 1: (16, False)}
    def mejor(s):
        for k in sorted(DUR, reverse=True):
            if k <= s: return k, DUR[k]
    for m in range(n_compases):
        voz = pista.measures[m].voices[0]; voz.beats = []
        sl, fin, primero = m * SPM, (m + 1) * SPM, True
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
        beats, db = detectar_beats(mezcla_mono)
        grid, bpm, conf = construir_grid(beats, db, duracion)
        log("  [3/5] Transcribiendo notas...")
        y, notas, n_ataques, n_cqt = transcribir(bajo)
        if not notas:
            raise RuntimeError("no se ha detectado ninguna nota de bajo")
        log("  [4/5] Cuantizando y digitando...")
        q, desfase, ambiguas = cuantizar(notas, grid)
        tab = digitar(q)

        # compás COUNT delante + silencio inicial
        med = float(np.median(np.diff(grid)))
        ibi0 = float(np.mean(np.diff(grid[:5])))
        completo = np.concatenate([[grid[0] - k * ibi0 for k in (4, 3, 2, 1)], grid])
        pad = MARGEN_INICIAL - completo[0]
        completo = completo + pad
        n_compases = int(np.ceil(max(n[1] for n in tab) / SPM)) + 1
        while len(completo) < 4 * n_compases + 1:
            completo = np.append(completo, completo[-1] + med)
        completo = completo[:4 * n_compases + 1]
        tempos = [int(round(60 / np.mean(np.diff(completo[4 * m:4 * m + 5])))) for m in range(n_compases)]

        log("  [5/5] Escribiendo archivos...")
        escribir_svl(dest / f"{nombre}.svl", completo)
        n_gp = escribir_gp5(dest / f"{nombre}.gp5", tab, n_compases, tempos, artista, titulo)
        cola = max(3.0, completo[-1] - (duracion + pad) + 1.0)
        pad_ms = int(round(pad * 1000))
        ffmpeg("-i", str(mezcla), "-af", f"adelay={pad_ms}|{pad_ms},apad=pad_dur={cola:.2f}",
               "-ar", "44100", "-c:a", "libvorbis", "-q:a", "6", str(dest / f"{nombre}.ogg"))

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
            c = 0.5 * np.sin(2 * np.pi * (1800 if i % 4 == 0 else 1200) * tt) * np.exp(-tt * 120)
            s = int(b * 44100)
            if s + len(c) < len(yc): yc[s:s + len(c)] += c
        sf.write(str(tmp / "clics.wav"), yc / (np.abs(yc).max() + 1e-9) * 0.95, 44100)
        ffmpeg("-i", str(tmp / "clics.wav"), "-b:a", "192k", str(dest / f"{nombre}_clics.mp3"))

    per = np.bincount(np.array([n[0] for n in tab]) // SPM)
    informe = (f"Canción: {artista} - {titulo}\nArchivo: {ruta.name}\n"
               f"Tempo mediano: {bpm:.1f} BPM | confianza del tiempo 1: {conf*100:.0f}%\n"
               f"Ataques detectados: {n_ataques} | notas: {len(notas)} (resueltas por CQT: {n_cqt}) | "
               f"en la tablatura: {n_gp}\n"
               f"Desfase de ataques corregido: {desfase*1000:.0f} ms | notas dudosas al cuantizar: {ambiguas*100:.0f}%\n"
               f"Notas por compás (mediana): {np.median(per):.0f}\n"
               f"Silencio inicial añadido: {pad:.3f} s | compases: {n_compases} (el 1 es el COUNT, vacío)\n"
               f"Tiempo de proceso: {time.time()-t_ini:.0f} s\n")
    (dest / "informe.txt").write_text(informe, encoding="utf-8")
    aviso = "  ¡OJO! tiempo 1 dudoso, revisa con el archivo de clics" if conf < 0.6 else ""
    log(f"  OK: {n_gp} notas, {bpm:.0f} BPM, dudosas {ambiguas*100:.0f}%{aviso}")
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

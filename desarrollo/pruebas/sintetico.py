"""Banco de pruebas con verdad conocida: bajo (Karplus-Strong) + batería + pad, con notas repetidas,
síncopas y compases irregulares. Genera mezcla.wav, bajo.wav (bajo + un poco de batería, como un stem
separado) y verdad.json (beats, downbeats, notas)."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100


def ks(f0, dur, vel, rng, brillo=0.5):
    """Cuerda pulsada (Karplus-Strong) con filtro de pérdidas."""
    n = int(dur * SR)
    N = max(2, int(round(SR / f0)))
    buf = rng.uniform(-1, 1, N)
    # excitación más o menos brillante (dedo vs púa)
    for _ in range(int(3 * (1 - brillo)) + 1):
        buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.empty(n)
    decay = 0.996
    for i in range(n):
        j = i % N
        out[i] = buf[j]
        buf[j] = decay * 0.5 * (buf[j] + buf[(j + 1) % N])
    return vel * out / (np.abs(out[:N * 4]).max() + 1e-9)


def bombo(rng):
    t = np.arange(int(0.25 * SR)) / SR
    f = 120 * np.exp(-t * 18) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)


def caja(rng):
    t = np.arange(int(0.2 * SR)) / SR
    return (rng.normal(0, 1, len(t)) * 0.6 + np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 22)


def charles(rng):
    t = np.arange(int(0.05 * SR)) / SR
    x = rng.normal(0, 1, len(t))
    x = np.diff(np.concatenate([[0], x]))  # agudo
    return 0.3 * x * np.exp(-t * 80)


def generar(dest, semilla=0, bpm=118, compases=None, pulsar="dedos", efecto=None):
    rng = np.random.default_rng(semilla)
    dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    if compases is None:
        compases = [4] * 6 + [2] + [4] * 7 + [6] + [4] * 9 + [3] + [4] * 6
    beat = 60.0 / bpm
    t = 1.0
    beats, downbeats = [], []
    for nb in compases:
        for k in range(nb):
            if k == 0:
                downbeats.append(t)
            beats.append(t)
            t += beat * (1 + rng.normal(0, 0.004))   # pequeño "swing" humano
    fin = t + 2.0
    total = int(fin * SR)
    bajo = np.zeros(total); bat = np.zeros(total); pad = np.zeros(total)

    def poner(dst, x, t0):
        i = int(t0 * SR); x = x[:max(0, total - i)]; dst[i:i + len(x)] += x

    # batería
    bi = 0
    for nb in compases:
        for k in range(nb):
            tb = beats[bi]; bi += 1
            if k % 2 == 0: poner(bat, 0.9 * bombo(rng), tb)
            else: poner(bat, 0.7 * caja(rng), tb)
            poner(bat, charles(rng), tb); poner(bat, 0.6 * charles(rng), tb + beat / 2)
    # bajo: patrones por compás
    raices = [40, 45, 43, 38, 40, 47, 45, 41]   # E2 A2 G2 D2 ... (MIDI)
    notas = []
    bi = 0
    for c, nb in enumerate(compases):
        r = raices[c % len(raices)] - 12 * (rng.random() < 0.5)   # a veces una octava abajo (E1...)
        r = max(r, 28)
        tipo = ["repetidas", "raiz_quinta", "sincopa", "repetidas_16"][c % 4]
        eventos = []                     # (posición en semicorcheas dentro del compás, duración, midi)
        if tipo == "repetidas":
            eventos = [(2 * i, 2, r) for i in range(nb * 2)]
        elif tipo == "repetidas_16":
            eventos = [(i, 1, r) for i in range(nb * 4) if i % 4 != 3]
        elif tipo == "raiz_quinta":
            eventos = [(4 * i, 4, r + (7 if i % 2 else 0)) for i in range(nb)]
        else:
            eventos = [(0, 3, r), (3, 3, r), (6, 2, r + 5), (8, 4, r + 7)] + \
                      [(4 * i, 2, r) for i in range(3, nb)]
        b0 = bi
        for pos, dur, p in eventos:
            ib = b0 + pos // 4
            if ib >= len(beats) - 1: continue
            t0 = beats[ib] + (pos % 4) / 4 * (beats[ib + 1] - beats[ib])
            notas.append([t0, dur * beat / 4, int(p)])
        bi += nb
    notas.sort()
    # síntesis: cada nota apaga la anterior (mano izquierda) con un fundido corto
    sonido = []
    for i, (t0, d, p) in enumerate(notas):
        sig = notas[i + 1][0] if i + 1 < len(notas) else t0 + d
        fin_nota = min(t0 + d * (0.9 + 0.1 * rng.random()), sig) + 0.01
        f0 = 440 * 2 ** ((p - 69) / 12)
        vel = rng.uniform(0.55, 1.0)
        x = ks(f0, fin_nota - t0 + 0.02, vel, rng, brillo=0.9 if pulsar == "pua" else 0.4)
        fade = int(0.02 * SR); x[-fade:] *= np.linspace(1, 0, fade)
        poner(bajo, x, t0)
        repetida = i > 0 and notas[i - 1][2] == p
        sonido.append({"t": round(t0, 4), "midi": p, "repetida": bool(repetida)})
    # pad (acordes suaves) para que la mezcla no sea solo bajo y batería
    for c, db in enumerate(downbeats):
        r = raices[c % len(raices)] + 24
        dur = (downbeats[c + 1] if c + 1 < len(downbeats) else fin) - db
        tt = np.arange(int(dur * SR)) / SR
        acorde = sum(np.sin(2 * np.pi * 440 * 2 ** ((r + k - 69) / 12) * tt) for k in (0, 4, 7))
        poner(pad, 0.05 * acorde * np.minimum(1, tt * 4), db)
    if efecto is not None:
        bajo = efecto(bajo)
    mezcla = 0.5 * bajo + 0.35 * bat + pad
    mezcla /= np.abs(mezcla).max() * 1.1
    stem = bajo + 0.03 * bat           # stem separado "imperfecto"
    stem /= np.abs(stem).max() * 1.1
    sf.write(dest / "mezcla.wav", mezcla, SR)
    sf.write(dest / "bajo.wav", stem, SR)
    json.dump({"bpm": bpm, "compases": compases, "beats": beats, "downbeats": downbeats, "notas": sonido},
              open(dest / "verdad.json", "w"), indent=0)
    return dest


if __name__ == "__main__":
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "banco")
    casos = [(0, 118, None, "dedos"), (1, 92, None, "dedos"), (2, 150, None, "pua"),
             (3, 76, [4] * 8 + [5] + [4] * 8 + [2] + [4] * 6, "dedos"), (4, 171, None, "dedos"),
             (7, 138, [3] * 40, "dedos"), (8, 96, [3] * 12 + [2] + [3] * 20, "dedos")]
    for s, bpm, comp, pul in casos:
        print(generar(base / f"caso{s}_{bpm}bpm", s, bpm, comp, pul))

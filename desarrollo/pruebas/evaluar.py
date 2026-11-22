"""Mide transcripción y compases del pipeline contra la verdad de los casos sintéticos.
Uso: python evaluar.py banco [notas|beats|todo] [motor_notas] [motor_beats]"""
import json
import sys
from pathlib import Path

import numpy as np

sys.argv, ARGS = ["x"], sys.argv[1:]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import auto_cdlc as c  # noqa: E402

TOL = 0.05


def emparejar(ref, est, tol=TOL):
    """Emparejamiento voraz 1 a 1 por cercanía; devuelve lista de (i_ref, j_est)."""
    pares, usados = [], set()
    for i, r in enumerate(ref):
        cand = [(abs(e - r), j) for j, e in enumerate(est) if j not in usados and abs(e - r) <= tol]
        if cand:
            _, j = min(cand); usados.add(j); pares.append((i, j))
    return pares


def f1(nref, nest, nok):
    p = nok / max(nest, 1); r = nok / max(nref, 1)
    return 2 * p * r / max(p + r, 1e-9), p, r


def eval_notas(caso, transcribir):
    v = json.load(open(caso / "verdad.json"))
    ref = v["notas"]
    notas = transcribir(caso / "bajo.wav")
    # los ataques del pipeline van adelantados (el desfase se corrige después al cuantizar):
    # se busca el desplazamiento global que más aciertos da, como hace el pipeline
    ref_t = [n["t"] for n in ref]
    mejor = max(np.arange(-0.04, 0.121, 0.004),
                key=lambda d: len(emparejar(ref_t, [n[0] + d for n in notas], 0.03)))
    est_t = [n[0] + mejor for n in notas]
    pares = emparejar(ref_t, est_t)
    ok_tiempo = len(pares)
    ok_tono = sum(1 for i, j in pares if round(notas[j][2]) % 12 == ref[i]["midi"] % 12)
    rep = [i for i, n in enumerate(ref) if n["repetida"]]
    det = {i for i, _ in pares}
    return {"ref": len(ref), "est": len(notas), "f1_ataques": round(f1(len(ref), len(notas), ok_tiempo)[0], 3),
            "precision": round(ok_tiempo / max(len(notas), 1), 3),
            "recall": round(ok_tiempo / len(ref), 3),
            "recall_repetidas": round(sum(i in det for i in rep) / max(len(rep), 1), 3),
            "tono_ok": round(ok_tono / max(ok_tiempo, 1), 3), "desfase_ms": round(mejor * 1000)}


def eval_beats(caso, detectar):
    v = json.load(open(caso / "verdad.json"))
    beats, downs = detectar(caso)
    pb = emparejar(v["beats"], list(beats), 0.07)
    pd = emparejar(v["downbeats"], list(downs), 0.07)
    return {"beats_f1": round(f1(len(v["beats"]), len(beats), len(pb))[0], 3),
            "downbeats_f1": round(f1(len(v["downbeats"]), len(downs), len(pd))[0], 3)}


# ---- motores ----
def notas_actual(wav):
    v = json.load(open(Path(wav).parent / "verdad.json"))
    _, notas, *_ = c.transcribir(wav, 60.0 / v["bpm"] / 4)
    return notas


def beats_actual(caso):
    import soundfile as sf, librosa
    y, sr = librosa.load(str(caso / "mezcla.wav"), sr=44100, mono=True)
    mono = caso / "_mono.wav"; sf.write(mono, y, sr)
    beats, act, alt = c.detectar_beats(mono)
    grid, barras, *_ = c.construir_grid(beats, act, len(y) / sr, alt)
    downs = [grid[b] for b in barras[:-1] if 0 <= grid[b] <= len(y) / sr]
    return beats, downs


MOTORES_NOTAS = {"actual": notas_actual}
MOTORES_BEATS = {"actual": beats_actual}

if __name__ == "__main__":
    base = Path(ARGS[0]); que = ARGS[1] if len(ARGS) > 1 else "todo"
    mn = ARGS[2] if len(ARGS) > 2 else "actual"; mb = ARGS[3] if len(ARGS) > 3 else "actual"
    if len(ARGS) > 4:
        exec(open(ARGS[4]).read())   # motores experimentales
    for caso in sorted(p for p in base.iterdir() if (p / "verdad.json").exists()):
        r = {"caso": caso.name}
        if que in ("notas", "todo"):
            for m in mn.split(","):
                rr = eval_notas(caso, MOTORES_NOTAS[m])
                r.update({f"{m}:{k}": v for k, v in rr.items() if k in ("f1_ataques", "precision", "recall_repetidas", "tono_ok")})
        if que in ("beats", "todo"): r.update(eval_beats(caso, MOTORES_BEATS[mb]))
        print(json.dumps(r, ensure_ascii=False), flush=True)

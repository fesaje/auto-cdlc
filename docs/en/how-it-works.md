# How it works

**English** | [Español](../es/funcionamiento.md)

The whole pipeline is in `cdlc_bajo.py`. The figures in this document are those of version 0.3.

## 1. Preparing the batch

`entrada` is compared with `salida`: a song is done if its folder has the `.gp5`. Pending songs are
grouped by album artist and album, taken from the tags, or from an iTunes search if there's no album.

Earlier logs tell which songs failed and how long a song takes on average. Each album's answers are saved
in `salida/ajustes_discos.json`.

## 2. Bass separation

MDX-Net model **kuielab_b_bass**, run with
[audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (ONNX on CPU). If the separated
bass is 35 dB or more below the mix, the song has no bass and is skipped.

## 3. Beat, downbeat and time signature

- **Beats**: [madmom](https://github.com/CPJKU/madmom)'s recurrent network + DBN model, with tempo between
  60 and 180 BPM. `vendor/` ships a pure-Python build of madmom, checked against the original, so nothing
  has to be compiled on Windows.
- **Downbeat**: [Beat This!](https://github.com/CPJKU/beat_this) (CPJKU). It's used whenever it counts the
  same beat as madmom, or half of it.
  - In triple-time songs, Beat This! counts eighth notes and its downbeat is also valid.
  - If none of these matches, madmom's bar network is used.
  - If madmom jumps between tempos (more than 3 % of beats out of place), Beat This!'s beats are used.
- **Repair**: gaps of 2–4 beats are filled in and doubled beats are removed.
- **Time signature**: a bar-by-bar Viterbi with a base of 4/4 or 3/4. The more likely one wins, and odd
  bars of 2 to 6 beats are allowed with low probability. The last bars are forced to the base metre,
  because beats are unreliable in endings.

## 4. Notes

- **Onsets**: `librosa`. For rhythm it uses the attack's peak minus the song's typical backtrack, not the
  "backtracked" onset, which sometimes lands far too early.
- **Pitch**: first pYIN, and a CQT with harmonic summation when it's unsure. Then
  [CREPE](https://github.com/maxrmorrison/torchcrepe) (*tiny* model):
  - the audio is fed to it one octave higher, because CREPE fails on low bass notes;
  - when CREPE and pYIN disagree by one or two semitones, the note in the song's own scale wins (so modes
    are respected).
- **Repeated notes**: the string keeps ringing, so two hits on the same note look like one. It looks for
  fast energy rises below 400 Hz that come after a dip and are close to the note's peak, and splits the
  note there.

## 5. Quantisation, tuning and fingering

- **Quantisation**: to sixteenth notes. The offset between onset and beat is found by scoring alignment
  with sixteenths, eighths and quarters, within a bounded physical window.
- **Tuning**: the one that fits the repeated low notes is chosen (E standard down to B standard,
  including Drop tunings).
- **Fingering**: dynamic programming over string and fret that minimises hand jumps. Hand positions
  (anchors) are computed afterwards.

## 6. Dynamic difficulty

Each note gets a rhythmic level: 0 if it's the first of the bar, 1 the half-bar one, 2 the beat, 3 the
eighth and 4 the rest.

Phrases are 4 bars long (8 for very long songs). The phrase boundaries are shifted by 0 to 3 bars to find
more repetitions.

For each phrase, versions from easiest to complete are generated. Each rhythmic step is added first in the
odd bars and then in all of them, like the community's DDC, up to 10 levels.

Repeated phrases are recognised with a one-sixteenth margin and share a name, so Rocksmith adds up their
progress. Each repetition gets its *heroLevels* (easy, medium and hard); without them the game would show
100 % from the start.

## 7. Tone, lyrics and simplified arrangement

- **Tone**: DLC Builder's database of official tones ([iminashi/tones](https://github.com/iminashi/tones)).
  It looks for the song first, then the artist and otherwise uses one of the reference tones.
- **Lyrics**: [LRCLIB](https://lrclib.net), only with the same length (±2 s). Words are spread within each
  line, and characters missing from Rocksmith's font are replaced with similar ones.
- **Simplified arrangement**: the notes up to the chosen rhythmic level, held until the next one, with its
  own dynamic difficulty. It's marked as an alternative arrangement.

## 8. Project and build

The program writes:

- each arrangement's XML in Rocksmith format;
- the DLC Builder `.rs2dlc` project, on which DLC Builder's own checks are repeated.

It's built by **cdlc-pack** (`herramientas/cdlc-pack/codigo`), a small console application based on DLC
Builder's libraries, [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) by iminashi (MIT
licence):

1. it converts the audio with Wwise;
2. it packages the `.psarc` with the same settings as DLC Builder's *Build Release*;
3. it reopens the package to check what ended up inside (levels, phrases, notes, lyrics).

## Test bench

`desarrollo/pruebas/` (in the repository, not in the download package) contains a generator of synthetic songs with a known answer, and an evaluator. The generator
makes bass, drums and accompaniment, with odd bars, syncopation, repeated notes and 3/4 bars. The
evaluator measures, against that answer:

- onset F1;
- repeated notes recovered;
- notes with the right pitch;
- beat and downbeat F1.

```
uv run python desarrollo/pruebas/sintetico.py FOLDER        # generates the cases
uv run python desarrollo/pruebas/evaluar.py FOLDER todo      # evaluates them
```

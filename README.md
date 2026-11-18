# auto-cdlc

**English** | [Español](README.es.md)

**Turn your mp3s into bass CDLC for Rocksmith 2014: on your own PC, for free.**

Put your songs in a folder, run a `.bat` file and get `.psarc` files ready to play bass in Rocksmith 2014
Remastered. For each song you get:

- the bass tab,
- dynamic difficulty,
- the amp tone,
- the album art,
- on-screen lyrics (when available),
- a second, simplified arrangement.

Everything runs locally with open-source models: no accounts, no per-song fees and your music is never
uploaded anywhere.

> **Note:** the program itself (prompts, reports and `configuracion.txt`) is in Spanish. This guide
> explains everything you need to use it.

---

## What it does

| Step | How |
|---|---|
| Separates the bass from the rest of the mix | MDX model *kuielab_b_bass* (audio-separator) |
| Finds the beat, the downbeat and the time signature (4/4, 3/4, 6/8 and odd bars) | madmom + Beat This! |
| Transcribes the notes, including repeated ones | librosa + pYIN + CREPE |
| Picks the tuning (E, Eb, Drop D, D… down to B) and the fingering | dynamic programming that minimises hand movement |
| Dynamic difficulty similar to official songs | up to 10 levels per phrase; repeated phrases share progress |
| Bass tone | the official one if the song or the artist has official DLC; otherwise the one you choose per album |
| On-screen lyrics | LRCLIB, if there is a version with the same length |
| Second, simplified arrangement ("Alt. Bass") | one note per beat, per bar… your choice |
| Album art, album and year | mp3 tags, iTunes or Deezer |
| Builds the `.psarc` without opening DLC Builder | `cdlc-pack`, built on DLC Builder's libraries |

It works in batches. Before starting, it groups what's pending by artist and album and asks only what it
needs (starting difficulty, tone and pick for each album). Then it processes the whole batch unattended,
overnight if you like. It takes about 4–5 minutes per song on a regular PC.

## Getting started

1. Install **Wwise** (converts audio to Rocksmith's format) and the **CDLC Enabler** (lets the game load
   custom songs).
2. Download the zip from the [latest release](https://github.com/fesaje/auto-cdlc/releases/latest),
   unzip it and run **`instalar.bat`**.
3. Put your mp3s in `entrada` and run **`procesar.bat`**.

Step by step in **[docs/en/installation.md](docs/en/installation.md)**.

## Documentation

- **[Installation](docs/en/installation.md)**: requirements, Wwise, CDLC Enabler, installer and first
  test.
- **[Usage](docs/en/usage.md)**: processing songs, the questions asked for each batch, the output, every
  option in `configuracion.txt`, checking the result and playing it in Rocksmith.
- **[How it works](docs/en/how-it-works.md)**: the pipeline in detail, for the curious and for
  contributors.
- **[Changelog](CHANGELOG.md)**.
- **[Third-party software and licences](THIRD_PARTY.md)**.

## Limitations

- **Windows** only (10/11, 64-bit) and **4-string** bass only.
- Transcription is automatic. Rhythm and notes are usually right, but there may be extra or missing
  notes, especially when the bass is quiet in the mix.
- Techniques are not detected: slides, hammer-ons, slap and harmonics come out as plain notes.
- It cannot tell whether the bass is distorted: the tone is chosen per album or taken from official DLC.

## Legal notice

auto-cdlc does not include or download any music. It is meant for making CDLC **for personal use** from
songs you already own. Do not share CDLC of copyrighted songs without permission, especially songs that
exist as official DLC.

Rocksmith is a trademark of Ubisoft. This project is not affiliated with Ubisoft or CustomsForge.

madmom's models are licensed CC BY-NC-SA, so the program as a whole may only be used
**non-commercially**. Details in [THIRD_PARTY.md](THIRD_PARTY.md).

## Licence

Code under the [MIT](LICENSE) licence. Third-party software keeps its own licences.

## Contributing

If something fails, open an [issue](https://github.com/fesaje/auto-cdlc/issues) and attach the **batch
log** (`salida\registro_….txt`), which includes the full diagnostics for every song. Issues in English or
Spanish are welcome.

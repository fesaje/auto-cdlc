# auto-cdlc

**English** | [Español](README.es.md)

**Turn your mp3s into bass CDLC for Rocksmith 2014: on your own PC, for free.**

Put your songs in a folder, run `procesar.bat` and get `.psarc` files ready to play bass in Rocksmith 2014
Remastered. Each song comes with:

- the **bass tab**, with **dynamic difficulty** (DD) like official songs,
- a **second, simplified arrangement** to warm up with,
- the **amp tone** (the official one when the artist has DLC),
- **on-screen lyrics** and **album art**, when available.

Everything runs locally with open-source models: no accounts, no per-song fees, and your music is never
uploaded anywhere.

> English and Spanish interface. It checks for new versions and updates itself.

---

## Why

I play bass with Rocksmith and kept finding very few songs in Spanish on the usual CDLC sites, so I built
a tool to chart the songs nobody else has charted. It's meant for **personal practice**, and also as a
**starting point** for anyone who wants to polish a chart by hand.

## What it does

| Step | How |
|---|---|
| Separates the bass from the rest of the mix | MDX model *kuielab_b_bass* (audio-separator) |
| Finds the beat, the downbeat and the time signature (4/4, 3/4 and odd bars) | madmom + Beat This!, checked against the bass line |
| Transcribes the notes, including repeated ones | librosa + pYIN + CREPE |
| Picks the tuning (E, Eb, Drop D, D… down to B) and the fingering | dynamic programming that minimises hand movement |
| Dynamic difficulty similar to official songs | up to 10 levels per phrase; repeated phrases share progress |
| Simplified arrangement ("Alt. Bass") | one note per beat, half bar or bar: your choice |
| Bass tone | the official one if the song or artist has official DLC; otherwise the one you choose per album |
| Lyrics, album art, album and year | LRCLIB; mp3 tags, iTunes or Deezer |
| Builds the `.psarc` without opening DLC Builder | `cdlc-pack`, built on DLC Builder's libraries |

It works in **batches**. Before starting, it groups what's pending by artist and album and asks only what
it needs (starting difficulty, tone and pick for each album). Then it runs unattended, overnight if you
like: about **3–4 minutes per song** on a regular PC. At the end you get a summary with a **reliability
rating** for every song and a list of the ones worth checking.

## Getting started

1. Install **Wwise** (converts audio to Rocksmith's format) and the **CDLC Enabler** (lets the game load
   custom songs).
2. Download `auto-cdlc-…-windows.zip` from the
   [latest release](https://github.com/fesaje/auto-cdlc/releases/latest), unzip it and run
   **`instalar.bat`**.
3. Put your songs in `entrada` and run **`procesar.bat`**.

Step by step in **[docs/en/installation.md](docs/en/installation.md)**. Quick answers in the
**[FAQ](docs/en/faq.md)**.

## Checking and polishing a song

Each song gets its own folder in `salida` with everything used to build it:

- **`_AB.mp3`**: with headphones, the real bass on the left and the tab on the right. Wrong notes stand out.
- **`_clics.mp3`**: a click on every beat, higher on beat 1, to check the bars.
- **`.gp5`**, **`.svl`**, the arrangement **XMLs** and a **DLC Builder project**: open them in Guitar Pro,
  TuxGuitar, Editor on Fire or DLC Builder and fix what you need.

After editing, rebuild the `.psarc` without analysing the audio again:

```
procesar.bat --rebuild "salida\Artist - Title"
```

## Documentation

- **[Installation](docs/en/installation.md)**: requirements, Wwise, CDLC Enabler, installer and first
  test.
- **[FAQ](docs/en/faq.md)**: how to use it, checking a song, editing and rebuilding, common problems.
- **[Usage](docs/en/usage.md)**: the batch questions, the output, every option in `configuracion.txt`.
- **[How it works](docs/en/how-it-works.md)**: the pipeline in detail, for the curious and for
  contributors.
- **[Changelog](CHANGELOG.md)** · **[Third-party software and licences](THIRD_PARTY.md)**.

## Limitations

- **Windows** only (10/11, 64-bit), **4-string bass** only.
- It's an **automatic transcription**: clear, simple basslines come out very playable; busy, syncopated or
  muddy ones will have extra, missing or misplaced notes. Compound meters (6/8, 12/8) and swing are not
  handled well yet.
- Techniques are not detected: slides, hammer-ons, slap and harmonics come out as plain notes.
- It can't tell whether the bass is distorted: the tone is chosen per album or taken from official DLC.

## Helping improve it

When you process a batch, it asks whether to send an **anonymous report** for each song: the diagnostics
and the generated tab, never the audio, the lyrics or your folders. It's optional
(`enviar_resultados = no` turns it off for good) and it's how the transcription gets better.

Found a bug or a song that comes out badly? Open an [issue](https://github.com/fesaje/auto-cdlc/issues)
and attach the **batch log** (`salida\registro_….txt`). English or Spanish, both welcome.

## Legal notice

auto-cdlc does not include or download any music. It's meant for making CDLC **for personal use** from
songs you already own. Don't upload the generated charts as they are to CDLC sites, and don't share CDLC
of copyrighted songs without permission, especially songs that exist as official DLC.

Rocksmith is a trademark of Ubisoft. This project is not affiliated with Ubisoft or CustomsForge.

madmom's models are licensed CC BY-NC-SA, so the program as a whole may only be used
**non-commercially**. Details in [THIRD_PARTY.md](THIRD_PARTY.md).

## Licence

Code under the [MIT](LICENSE) licence. Third-party software keeps its own licences.

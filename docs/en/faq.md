# FAQ

**English** | [Español](../es/preguntas-frecuentes.md)

Short answers to the usual questions. The details are in [Installation](installation.md) and
[Usage](usage.md).

## Getting started

### What does it do, in one paragraph?
You give it audio files (mp3, flac, wav, ogg, m4a…) and it gives you a bass CDLC for Rocksmith 2014 for
each one. For every song it separates the bass from the mix, finds the beats and bars, transcribes the
notes into a tab, builds the difficulty levels (DD), adds lyrics and album art when it finds them, picks a
bass tone and packs the `.psarc`. Everything runs on your PC.

### How do I process songs?
1. Put the songs in the **`input`** folder (or drag them onto `process.bat`).
2. Double-click **`process.bat`**.
3. Answer the questions (or just press Enter: the values in brackets are sensible defaults).
4. Wait. The `.psarc` files end up in the `psarc` folder, or in the one set in `psarc_folder`.

You can keep adding songs to `input`: the ones already processed are skipped.

### What will it ask me?
Once per batch: starting difficulty, simplified arrangement and whether to send anonymous results. Once
per album: bass tone and pick or fingers. Then a summary with the estimated time and "Start?". If nobody
answers within 60 seconds, it uses the defaults and starts on its own, so you can launch it and walk away.

### How long does it take?
About 3–4 minutes per song on a normal PC. A 100-song batch is a night's work.

### Where do I put the `.psarc` so the game sees it?
In Rocksmith's `dlc` folder. The easiest way is to set `psarc_folder` in `config.txt` to that
folder (the installer offers to do it). The game also needs the **CDLC Enabler**: see
[Installation](installation.md#cdlc-enabler-lets-rocksmith-load-custom-songs).

### Can I use it in English?
Yes: `language = en` in `config.txt`. The installer asks the first time.

## Quality

### How good are the tabs?
It's an automatic transcription. Clean, simple basslines come out very playable; busy, syncopated or muddy
basslines will have mistakes. Each song gets a **reliability** level (high, medium, low) with the reasons,
and at the end of the batch you get a "Worth checking" list.

### How do I check a song without playing it?
In its folder inside `output`:
- **`_AB.mp3`**, with headphones: the real bass on the left, the tab played back on the right. If they
  don't match, the tab is wrong there.
- **`_clics.mp3`**: the song with a click on every beat, higher on beat 1. If the high click doesn't fall at
  the start of the bar, the bars are shifted.
- **`informe.txt`**: tuning, time signature, tone, lyrics and warnings.

### It's too hard to play
- Lower `start_difficulty` (or answer lower when it asks): the song starts with fewer notes and Rocksmith
  adds them as you play well.
- Use the **simplified arrangement** (second bass arrangement in the game): one note per beat, half bar or
  bar, depending on `simple_arrangement`.
- If the notes don't match what you hear, it's a transcription problem: tell me which song and where
  (see "How do I report a problem?").

### Rocksmith asks me to retune
The program detected a tuning other than E standard because it found low notes below E. Sometimes a few
wrong notes are enough to fool it. Check `informe.txt`; if the band plays in E standard, tell me the song.

### A song says "no bass"
The separated bass was almost silent: interludes, intros, acoustic songs… It's not an error. Those songs
are skipped in later batches; to try again, use `--force`.

## Editing by hand

### Can I fix the tab myself?
Yes. Each song's folder has everything you need: `.gp5` (Guitar Pro / TuxGuitar / EOF), `.svl` (beat map
for EOF), the arrangement XMLs and a DLC Builder project (`.rs2dlc`). See
[Building or editing by hand](usage.md#building-or-editing-by-hand).

### How do I rebuild the `.psarc` after editing?
```
process.bat --rebuild "output\Artist - Title"
```
It packs the song again from its project and XMLs, without analysing the audio again. You can pass
several folders.

### Can I upload the songs to CustomsForge / Ignition?
Not as they come out of the program: they're automatic charts and don't meet the quality the community
expects. If you use them as a base and polish a chart by hand into a proper CDLC, that's a different
story: follow CustomsForge's rules.

## Problems

### No `.psarc` is created
Almost always Wwise. The final summary lists songs "without .psarc" with the reason. Install Wwise 2019,
2021, 2022 or 2023; if it's on another drive, put its folder in `wwise` in `config.txt`. Then run
those songs again with `--force`, or use `--rebuild`.

### The update failed
Usually a network hiccup: run `process.bat` again. Your installation is untouched until an update
completes.

### "Couldn't send the results"
The server couldn't be reached. In Spain this happens on football match days, when some Cloudflare IPs are
blocked. Nothing is lost: the results are saved in `pending_uploads` and sent in the next batch.

### The antivirus complains
It's usually the CDLC Enabler (`D3DX9_42.dll`) or `cdlc-pack.exe`, an unsigned program. Add an exception
for those folders.

### How do I report a problem?
Open an issue on [GitHub](https://github.com/fesaje/auto-cdlc/issues) and attach the batch log,
`output\log_YYYY-MM-DD_HH-MM.txt`. Say which song and, if it's about the tab, roughly where
(minute:second).

## Other

### What is sent if I say yes to sending results?
The diagnostics, the report and the generated bass tab of each song. Never the audio, never the lyrics and
never your user name or folders. It's anonymous and optional: `send_results = no` turns it off for
good.

### Guitar?
Not for now. Separating a guitar from voices and other guitars and transcribing chords (especially
distorted ones) is much harder than a bass line. It's on the list, but far away.

### Mac or Linux?
No, Windows only for now: Rocksmith 2014, Wwise and the packaging tool are set up for Windows.

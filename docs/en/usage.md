# Usage

**English** | [Español](../es/uso.md)

With `idioma = en` the program's menus, questions and reports are in English. The keys in
`configuracion.txt` stay in Spanish (the comments are in English); the table below explains them.

## Processing songs

Menus, questions and reports use the language chosen at install time (`idioma = es` or `en` in
`configuracion.txt`).

**Updates**: when it starts, the program checks whether a new version has been published. If so, it shows
what's new and asks whether to update. The update:

- doesn't touch your configuration, your songs or the downloaded models;
- adds any new options to `configuracion.txt`;
- relaunches the program with the new version.

Unattended batches don't update. Turn it off with `buscar_actualizaciones = no` or `--sin-actualizar`.

- **In batches:** put your songs (mp3, flac, wav, ogg, m4a…) in the **`entrada`** folder and double-click
  **`procesar.bat`**. You can keep adding songs there: the ones already processed are skipped.
- **One by one:** drag songs or a folder onto `procesar.bat`.

### Before starting: the batch questions

1. **Checks what's pending.** It compares `entrada` with `salida` and tells you how many songs there are,
   how many are done and how many are left.
2. **Groups by artist > album**, using the mp3 tags (album artist and album). If a song has no album, it
   looks it up online by artist and title. If that fails too, it goes under "(sin disco)".
3. **Songs that failed before**: if any songs gave an error in earlier batches (for example, interludes
   with no bass), it lists them and asks whether to retry. The default is no. Songs you don't retry are
   left out of the batch and nothing is asked about them.
4. **Batch questions**: starting difficulty, simplified arrangement and whether you want to **send the
   results** to help improve auto-cdlc (see below).
5. **Album questions**: bass tone and pick (`auto`, `pick` or `fingers`).
6. **Summary**: settings, albums, number of songs and estimated time. At the end, "Start? (y/n)".

In every question, **Enter** keeps the value in brackets. That's the value in `configuracion.txt`, or
whatever you chose last time for that album (saved in `salida\ajustes_discos.json`).

If nobody answers within 60 seconds (`espera_preguntas`), the defaults are used for everything and the
batch starts on its own, so you can launch it and walk away. With `--sin-preguntas` nothing is asked.

Each song takes about 4–5 minutes, depending on the computer.

### Output

- The **`.psarc`** files go to the `psarc` folder, or to the folder set in `carpeta_psarc` (Rocksmith's
  `dlc` folder is the handy choice).
- Everything else goes to **`salida\Artist - Title\`**:

| File | What for |
|---|---|
| `informe.txt` | **Read this first**: tuning, pick, time signature, tone, lyrics, simplified arrangement, warnings. |
| `diagnostico.json` | All internal measurements. Only for debugging. |
| `*.rs2dlc` | DLC Builder project, in case you want to rebuild or edit by hand. |
| `*_bass_RS2.xml`, `*_bass2_RS2.xml`, `*_vocals_RS2.xml` | Bass arrangement, simplified arrangement and lyrics in Rocksmith format. |
| `*.ogg`, `*_preview.ogg` | Audio with a silent lead-in for the count-in bar, and the preview. |
| `portada.png` | Album art. |
| `*_AB.mp3` | **With headphones**: left = real bass, right = synthesised tab. |
| `*_clics.mp3` | The song with a click on every beat, higher-pitched on the downbeat. |
| `*.gp5`, `*.svl`, `*.mid` | Tab (Guitar Pro), beat map and MIDI, for Editor on Fire. |

- `salida` also gets a **log for each batch** (`registro_YYYY-MM-DD_HH-MM.txt`): one line per song, the
  reports and the full diagnostics. This is the file to attach if something goes wrong.

## `configuracion.txt`

| Key | Values | What for |
|---|---|---|
| `carpeta_psarc` | path | Where to save the `.psarc` files. Empty: the program's `psarc` folder. |
| `compilar_psarc` | `si` / `no` | With `no`, only the `.rs2dlc` project is created. |
| `buscar_caratulas` | `si` / `no` | With `no` it never goes online: no album art, official tones or lyrics. |
| `wwise` | path | Wwise folder or path to `WwiseConsole.exe`, only if it isn't found automatically (it checks Program Files and `WWISEROOT`). |
| `umbral_cents` | number (30) | Minimum deviation of the recording from A = 440 before the *Tuning Pitch* is changed. |
| `dificultad` | `propia` / `dlcbuilder` / `ninguna` | Type of dynamic difficulty (see below). |
| `dificultad_inicial` | 0–95 | % of notes each phrase starts with. Asked for each batch. |
| `partir_repetidas`, `umbral_reataque_db` | `si` / `no`, dB (3) | Split repeated notes that come out as one long note. |
| `tono_crepe` | `si` / `no` | Pitch of each note with the CREPE network. |
| `tono_bajo` | `auto`, `limpio`, `limpio_pua`, `saturado`, `distorsion`, `fuzz` or an official tone | Bass tone. It's the default for each album's question. |
| `velocidad_scroll` | 0.5–5, or `auto 1.3` | How fast notes travel down the highway (see below). |
| `arreglo_simple` | `tiempo`, `medio`, `compas`, `corchea`, `no` | Simplified second arrangement. Asked for each batch. |
| `letra` | `si` / `no` | On-screen lyrics from LRCLIB. |
| `espera_preguntas` | seconds (60) | Time without an answer before starting with the defaults. |
| `idioma` | `es` / `en` | Language of menus, questions and reports. Asked by `instalar.bat`. |
| `buscar_actualizaciones` | `si` / `no` | Check for new versions when starting and offer to install them. |
| `enviar_resultados` | `preguntar` (ask) / `si` / `no` | Voluntary sending of results (asked in every batch by default). |

Command-line options: `--forzar` (redo songs already processed), `--sin-preguntas`, `--sin-actualizar`, `--sin-psarc`,
`--sin-internet`, `--psarc FOLDER`, `--wwise PATH` and `--salida FOLDER`.

### Dynamic difficulty

With `dificultad = propia`, each 4-bar phrase starts with very few notes and adds more in rhythmic steps:
one note per bar, per half bar, per beat, per eighth note, and all of them. Each step is added first in
the odd bars of the phrase and then in all of them, up to 10 levels. Phrases that repeat (choruses,
verses) share progress.

`dificultad_inicial` removes the easiest levels. With 50, every phrase already starts with half of its
notes.

### Bass tone

- `auto`: if the song or the artist has official DLC, its tone is used. For that it checks a database of
  1,611 official bass tones, the same one DLC Builder uses. Otherwise it uses the clean tone, or the
  bright clean one if a pick is detected.
- `limpio` (clean), `limpio_pua` (bright clean, for pick), `saturado` (overdrive), `distorsion`
  (distortion), `fuzz`: tones from official songs chosen as references for each kind of sound.
- Any official tone name also works, for example `RageKilling_bassdist`.

There is no automatic distortion detection: it can't be told apart reliably from what the separator
leaves. That's why it's asked per album.

### Scroll speed

How fast the notes come towards you:

- **Lower:** you see them further ahead, but closer together.
- **Higher:** further apart, but with less time to read them.

With `auto 1.3` it follows each song's tempo: 1.3 at 120 BPM, half at 60, one and a half times at 180,
always between 0.9 and 2.2.

### Simplified arrangement

It shows up in the game as **"Alt. Bass"**, next to the normal bass. It only has the notes on the strong
points of the rhythm:

- `tiempo`: one per beat (default);
- `medio`: one per half bar;
- `compas`: one per bar;
- `corchea`: one per eighth note.

Each note is held until the next one. It has its own dynamic difficulty and its own percentage.

### Lyrics

They're looked up on [LRCLIB](https://lrclib.net) and only used if the length matches your file
(±2 s). LRCLIB gives the start time of each line: the words within the line are spread out
approximately.

### Sending results

It's voluntary: you're asked in every batch. Enter means "yes", but if nobody answers (unattended batch)
nothing is sent. If you say yes, after each song this is sent:

- the diagnostics, the report and the tab (the bass XML files);
- the version, the system and the settings used;
- an anonymous installation ID.

The audio and the lyrics are never sent, and paths on your computer are removed before sending. It's
about 10 KB per song. It helps find the cases where the program fails and improve it.

## What it detects on its own

- **Tuning**: E standard, Eb, Drop D, D, Drop C#, C#, Drop C, C, Drop B or B standard. It stays in E
  standard unless there are low notes that don't fit. Rocksmith's tuner asks for the right one.
- **Recording's tuning reference**: many records aren't at A = 440 Hz. If the deviation is large
  (`umbral_cents`), it's set as the *Tuning Pitch*.
- **Pick or fingers**, from the "click" of the attack. It can be set per album.
- **Time signature**: 4/4 or 3/4 (also 6/8), with odd bars of 2 to 6 beats. The report gives the
  minute of each odd bar.
- **Songs without bass** (interludes, intros): skipped with a warning instead of inventing a tab.

## Checking the result

1. Listen to `_clics.mp3`: the clicks should follow the drums and the high click should land on the
   downbeat. If the report says "tiempo 1 dudoso" (doubtful downbeat), start here.
2. Listen to `_AB.mp3` with headphones:
   - only the left side sounds → a note is **missing**;
   - only the right side sounds → there's an **extra** note;
   - both sound but clash → wrong note or wrong octave.

## In Rocksmith

- Pick the song in *Learn a Song*. If it has a simplified arrangement, you'll see **Bass** and **Alt.
  Bass**.
- Dynamic difficulty goes up by itself as you play well. To play everything from the start: **Riff
  Repeater** → select the whole song → *Set Difficulty* to 100 %.

## Building or editing by hand

- **DLC Builder**: open the `.rs2dlc` (*Project → Open Project…*) and press *Build*. Useful if the
  `.psarc` wasn't built or if you want to change something (tone, album art…).
- **Editor on Fire**: create a project with the `.ogg` and import the `.svl` (*File → Import → Sonic
  Visualiser*). Then import the `.gp5` (*File → Import → Guitar Pro*, track *PART REAL_BASS*, accepting
  the *time signatures*). Afterwards, replace the arrangement XML in DLC Builder with the one EOF saves.

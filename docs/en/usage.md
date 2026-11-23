# Usage

**English** | [Español](../es/uso.md)

With `language = en` the program's menus, questions and reports are in English. Folders, files,
options and `config.txt` keys are in English for everyone since 0.5. If you come from 0.4 or earlier, the
first run renames your folders (`entrada` → `input`, `salida` → `output`…) and converts your
`configuracion.txt` into `config.txt` (a copy is kept as `configuracion.txt.bak`). The old names
(`procesar.bat`, `--forzar`, Spanish keys and values) still work.

## Processing songs

Menus, questions and reports use the language chosen at install time (`language = es` or `en` in
`config.txt`).

**Updates**: when it starts, the program checks whether a new version has been published. If so, it shows
what's new and asks whether to update. The update:

- doesn't touch your configuration, your songs or the downloaded models;
- adds any new options to `config.txt`;
- relaunches the program with the new version.

Unattended batches don't update. Turn it off with `check_updates = no` or `--no-update`.

- **In batches:** put your songs (mp3, flac, wav, ogg, m4a…) in the **`input`** folder and double-click
  **`process.bat`**. You can keep adding songs there: the ones already processed are skipped.
- **One by one:** drag songs or a folder onto `process.bat`.

### Before starting: the batch questions

1. **Checks what's pending.** It compares `input` with `output` and tells you how many songs there are,
   how many are done and how many are left.
2. **Groups by artist > album**, using the mp3 tags (album artist and album). If a song has no album, it
   looks it up online by artist and title. If that fails too, it goes under "(sin disco)".
3. **Songs that failed before**: if any songs gave an error in earlier batches, it lists them and asks
   whether to retry (the default is no). Songs with no bass (interludes, intros) are skipped without asking. Songs you don't retry are
   left out of the batch and nothing is asked about them.
4. **Batch questions**: starting difficulty, simplified arrangement and whether you want to **send the
   results** to help improve auto-cdlc (see below).
5. **Album questions**: bass tone and pick (`auto`, `pick` or `fingers`).
6. **Summary**: settings, albums, number of songs and estimated time. At the end, "Start? (y/n)".

In every question, **Enter** keeps the value in brackets. That's the value in `config.txt`, or
whatever you chose last time for that album (saved in `output\album_settings.json`).

If nobody answers within 60 seconds (`question_timeout`), the defaults are used for everything and the
batch starts on its own, so you can launch it and walk away. With `--no-questions` nothing is asked.

Each song takes about 3–4 minutes, depending on the computer. At the end, the summary lists the songs worth
checking (low reliability), the ones left without `.psarc` and the ones with no bass, and offers to move the
batch's files out of `input` (to `input\processed` and `input\discarded`).

### Output

- The **`.psarc`** files go to the `psarc` folder, or to the folder set in `psarc_folder` (Rocksmith's
  `dlc` folder is the handy choice).
- Everything else goes to **`output\Artist - Title\`**:

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

- `output` also gets a **log for each batch** (`log_YYYY-MM-DD_HH-MM.txt`): one line per song, the
  reports and the full diagnostics. This is the file to attach if something goes wrong.

## `config.txt`

| Key | Values | What for |
|---|---|---|
| `psarc_folder` | path | Where to save the `.psarc` files. Empty: the program's `psarc` folder. |
| `build_psarc` | `yes` / `no` | With `no`, only the `.rs2dlc` project is created. |
| `online` | `yes` / `no` | With `no` it never goes online: no album art, official tones, lyrics or updates. |
| `wwise` | path | Wwise folder or path to `WwiseConsole.exe`, only if it isn't found automatically (it checks Program Files and `WWISEROOT`). |
| `cents_threshold` | number (30) | Minimum deviation of the recording from A = 440 before the *Tuning Pitch* is changed. |
| `difficulty` | `own` / `dlcbuilder` / `none` | Type of dynamic difficulty (see below). |
| `start_difficulty` | 0–95 | % of notes each phrase starts with. Asked for each batch. |
| `split_repeated`, `reattack_threshold_db` | `yes` / `no`, dB (3) | Split repeated notes that come out as one long note. |
| `crepe_pitch` | `yes` / `no` | Pitch of each note with the CREPE network. |
| `bass_tone` | `auto`, `clean`, `clean_pick`, `overdrive`, `distortion`, `fuzz` or an official tone | Bass tone. It's the default for each album's question. |
| `scroll_speed` | 0.5–5, or `auto 1.3` | How fast notes travel down the highway (see below). |
| `simple_arrangement` | `beat`, `half`, `bar`, `eighth`, `no` | Simplified second arrangement. Asked for each batch. |
| `lyrics` | `yes` / `no` | On-screen lyrics from LRCLIB. |
| `question_timeout` | seconds (60) | Time without an answer before starting with the defaults. |
| `language` | `es` / `en` | Language of menus, questions and reports. Asked by `install.bat`. |
| `check_updates` | `yes` / `no` | Check for new versions when starting and offer to install them. |
| `send_results` | `ask` / `yes` / `no` | Voluntary sending of results (asked in every batch by default). |

Command-line options (for `process.bat` or `uv run auto_cdlc.py`): `--force` (redo songs already processed),
`--no-questions`, `--no-update`, `--no-psarc`, `--offline`, `--rebuild` (see below), `--psarc FOLDER`,
`--wwise PATH` and `--output FOLDER`. `--help` lists them all.

### Dynamic difficulty

With `difficulty = own`, each 4-bar phrase starts with very few notes and adds more in rhythmic steps:
one note per bar, per half bar, per beat, per eighth note, and all of them. Each step is added first in
the odd bars of the phrase and then in all of them, up to 10 levels. Phrases that repeat (choruses,
verses) share progress.

`start_difficulty` removes the easiest levels. With 50, every phrase already starts with half of its
notes.

### Bass tone

- `auto`: if the song or the artist has official DLC, its tone is used. For that it checks a database of
  1,611 official bass tones, the same one DLC Builder uses. Otherwise it uses the clean tone, or the
  bright clean one if a pick is detected.
- `clean`, `clean_pick` (bright clean, for pick), `overdrive`, `distortion`, `fuzz`: tones from official
  songs chosen as references for each kind of sound.
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

- `beat`: one per beat (default);
- `half`: one per half bar;
- `bar`: one per bar;
- `eighth`: one per eighth note.

Each note is held until the next one. It has its own dynamic difficulty and its own percentage.

### Bass separation model

`separation_model = mdx` (default) gives the steadiest note pitch. `demucs` puts the notes on the beat more
precisely on clean mixes, but on dense ones it can lose the pitch, and it takes about 1.5 times longer. Worth
trying on a song whose rhythm came out wrong: change it, then process that song again with `--force`. With
a synth bass it may find no bass at all; go back to `mdx` for those.

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
  (`cents_threshold`), it's set as the *Tuning Pitch*.
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

## The interface (`auto-cdlc.bat`)

Since 0.5.1 there is also a text interface, in the style of Midnight Commander: run **`auto-cdlc.bat`**.
It works with the mouse or the keyboard and has three tabs:

- **Songs**: every processed song by artist, album and title (click a column header to sort by it, press
  **/** to filter) with its reliability, BPM, tuning, tone, pick, scroll speed and
  arrangement. Select one to see its report. Keys: **e** retouch (tone, pick, speed… see below), **b**
  build the `.psarc` again, **o** open its folder, **c** play the clicks, **a** play the A/B, **r** refresh.
- **Batch**: the songs in `input` (the ones already processed are marked). Tick the ones you want, choose
  starting difficulty, simplified arrangement, tone, pick and whether to send results, and press
  **Start**. The progress shows up below. It's the same as `process.bat`, without the questions.
- **Settings**: every option in `config.txt`, with a short explanation. **Save** writes them to the file.

`process.bat` keeps working as always and is still the one that checks for updates.

**Where the .psarc files go.** With several Rocksmith installs on the PC (other Steam libraries, a copy on
another drive), **Find Rocksmith…** next to `psarc_folder` in Settings lists them all with how many .psarc
each dlc folder has; pick one, or the first option for auto-cdlc's own `psarc` folder, and press Save. The
same from the command line: `process.bat --find-rocksmith`. The installer asks this too.

## Retouching a song without analysing it again

Tone, pick, scroll speed, simplified arrangement and starting difficulty can be changed afterwards in a few
seconds, without analysing the audio again. From the interface (**e** on the song) or from the command line:

```
process.bat --regenerate "output\Artist - Title" --tone fuzz --pick yes --scroll 1.6
```

Options: `--tone` (`auto`, `clean`, `clean_pick`, `overdrive`, `distortion`, `fuzz` or an official tone
name), `--pick yes|no`, `--scroll` (0.5–5), `--simple no|bar|half|beat|eighth` and `--start-difficulty`
(%). Whatever you don't pass is kept. It rewrites the XMLs and the DLC Builder project and builds the
`.psarc` again; the change is noted at the end of `informe.txt`.

Songs processed before 0.5.1 don't have the saved analysis (`analisis.json`), so for those only tone, pick
and speed can be changed.

The same options without `--regenerate` apply to a whole batch and skip those questions:
`process.bat --tone overdrive --pick no --simple bar`. `--send yes|no` too.

## Building or editing by hand

- **DLC Builder**: open the `.rs2dlc` (*Project → Open Project…*) and press *Build*. Useful if the
  `.psarc` wasn't built or if you want to change something (tone, album art…).
- **Editor on Fire**: create a project with the `.ogg` and import the `.svl` (*File → Import → Sonic
  Visualiser*). Then import the `.gp5` (*File → Import → Guitar Pro*, track *PART REAL_BASS*, accepting
  the *time signatures*). Afterwards, replace the arrangement XML in DLC Builder with the one EOF saves.
- **Rebuild with auto-cdlc**: after editing the arrangement XMLs in the song's folder (or saving the EOF
  XML over `..._bass_RS2.xml`), rebuild the `.psarc` without analysing the audio again:

  ```
  process.bat --rebuild "output\Artist - Title"
  ```

  You can pass several folders or `.rs2dlc` files. It uses the same Wwise and `psarc` folder as normal
  processing. Dynamic difficulty is only generated for arrangements that have a single level; if your
  XML already has its own levels, they are kept.

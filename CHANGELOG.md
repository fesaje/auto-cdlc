# Changelog

**English** | [Español](CHANGELOG.es.md)

Up to 0.2.9.1 the project was called **cdlc-bajo** and its versions were numbered 1.x and 2.x (2.9.1 is
0.2.9.1). The git history keeps the code of versions 0.1.0, 0.1.1, 0.1.1.1, 0.1.3.1, 0.2.3, 0.2.3.2, 0.2.4,
0.2.5, 0.2.5.1, 0.2.5.2, 0.2.7, 0.2.8.1, 0.2.9 and 0.2.9.1. Those before 0.2.9.1 only contain the text
files: code, configuration, README and installers.

- **0.4.2**:
  - The time estimate before starting is shown in hours, minutes and seconds (e.g. "about 20 min 48 s
    (5 min 12 s per song)").
  - Wwise is found on any drive: through `WWISEROOT` even if the folder name has no year, and the `wwise`
    key accepts the Wwise folder as well as `WwiseConsole.exe`. If it's missing, it warns before starting.
  - Songs that end without a `.psarc` are counted and listed apart in the final summary, with the reason,
    instead of looking like a normal "OK".
  - Beats are detected while the bass is being separated, at the same time: on the results received, that
    was about a quarter of the time per song.
  - Each song gets a reliability level (high, medium, low) with the reasons (unsteady beat, doubtful downbeat,
    many odd bars, notes off the grid, unclear bass pitch). They show in its line and in a "worth checking"
    list at the end.
  - Songs with no bass are no longer an error: they're marked "no bass" and skipped in later batches (unless
    `--forzar`).
  - File names like "Artist - Album - 08 - Title" (no tags) give title "Title" and album "Album"; a leading
    track number and suffixes like "(Official Video)" or a YouTube id are removed.
  - The diagnostics record where notes fall inside each beat, to study swing and triplets.
  - When the downbeat is doubtful, the bars are moved to start on the beat where the bass changes note most
    often (it usually changes with the chord, on beat 1).
  - At the end of a batch it offers to move its files out of `entrada`: processed ones to
    `entrada\procesadas`, errors and songs with no bass to `entrada\descartadas`. Nothing is deleted
    and the default is no.
- **0.4.1**:
  - In the question about sending results, Enter means "yes". If nobody answers (unattended batch),
    nothing is sent.
  - Developer tools (results server, download script and test bench) move to `desarrollo/`: still in the
    repository but no longer in the package or in updates.
  - Results server: optional Telegram notification for each song received. The download script asks for
    the token without showing it, because typed on the command line it broke with `&` or `%`.
- **0.4.0**:
  - English and Spanish interface: `instalar.bat` asks for the language (`idioma` in
    `configuracion.txt`) and menus, questions, warnings, reports and logs use it. `configuracion.en.txt`
    is the template with English comments.
  - Updates: when it starts it checks for a new version and offers to install it without going to
    GitHub. It doesn't touch the configuration, songs or models; it adds new options to
    `configuracion.txt` and relaunches the program. `buscar_actualizaciones`, `--sin-actualizar`.
  - Voluntary sending of results (diagnostics, report and tab; never audio or lyrics; no personal paths)
    to a dedicated Cloudflare Workers + R2 server. Asked in every batch (`enviar_resultados`). Server code
    and download script in `desarrollo/` (repository only).
- **0.3.0**: first public release, now as **auto-cdlc**.
  - New documentation in English and Spanish: README, installation guide, usage guide, how it works and
    third-party licences.
  - The installer downloads `cdlc-pack` if it's missing, checks for Wwise and offers to save the `.psarc`
    files in Rocksmith's `dlc` folder.
  - `cdlc-pack` becomes a single executable published in the *releases*.
  - The synthetic test bench is in `pruebas/`.
  - MIT licence.
- **0.2.9.1**: the question about retrying songs that failed comes first; if you say no, their albums are
  no longer asked about or shown in the summary.
- **0.2.9**: before starting, it checks what's pending in `entrada` against `salida` and groups it by
  artist > album (tags; if missing, an online lookup). It asks for the batch's starting difficulty and
  simplified arrangement, whether to retry earlier failures, and each album's tone and pick (Enter = the
  value in configuracion.txt or the one chosen last time for that album, saved in
  `salida/ajustes_discos.json`). Summary with estimated time and confirmation. If nobody answers within
  `espera_preguntas` seconds (60), it starts on its own with the defaults. `--sin-preguntas` to ask
  nothing.
- **0.2.8.1**: `velocidad_scroll = auto 1.3` adapts note speed to each song's tempo (1.3 at 120 BPM,
  proportional, between 0.9 and 2.2). The report shows the value used.
- **0.2.8**: triple metre: if a song is in 3 (3/4, 6/8, zambas, waltzes) it's written in 3/4 throughout
  instead of 4/4 with dozens of "odd" bars, and in those songs Beat This! is used even when it counts
  double. Second, simplified arrangement ('Alt. Bass', option `arreglo_simple`, one note per beat by
  default, with its own DD). On-screen lyrics from LRCLIB when the length matches (option `letra`,
  line-synced). New option `velocidad_scroll`. Beat This! replaces madmom from 3 % unstable beats
  (previously 5 %). cdlc-pack rebuilt to also verify the lyrics.
- **0.2.7**: in-game bass sound (amp and pedals) per song. New option `tono_bajo` in configuracion.txt:
  `auto` uses the official Rocksmith tone if the song or the artist has official DLC (database of 1,611
  bass tones from DLC Builder, downloaded on first use), otherwise clean (or bright clean with a pick).
  `limpio`, `limpio_pua`, `saturado`, `distorsion`, `fuzz` or an official tone name can also be set. Each
  song's report says which tone it has. Automatic distortion detection isn't applied yet: its measurements
  are logged in the diagnostics for calibration.
- **0.2.6**: steadier, faster beat tracking. Gaps where the beat tracker went silent (causing 6/4 bars or
  absurd tempos) are filled in, and doubled beats removed. If madmom jumps between tempos and Beat This!
  agrees on the tempo, Beat This!'s beats are used. madmom's bar network only runs when needed (the beat
  stage drops from ~160 s to ~50 s). Phrases no longer always start at bar 1: shifts of 0–3 bars are tried
  and the one finding the most repetitions is kept (more progress shared between choruses).
- **0.2.5.2**: if the tags include the album, the album art and year come from THAT album (artist + album
  search) and the album name is the one in your tags. Only if it isn't found is the song looked up.
- **0.2.5.1**: more accurate rhythm: each note is placed from the peak of its attack instead of the
  "backtracked" onset, which sometimes landed far too early and moved the note one sixteenth ahead (onto
  the "a" of the previous beat). In "Mi furia paranoica" misplaced notes drop from 19 % to 7 %. Pitch ties
  are settled with the notes the song itself uses (respects modes such as mixolydian).
- **0.2.5**: DD closer to official songs: up to 10 levels per phrase, starting with one note every two
  bars. Each rhythmic step comes in first in the phrase's odd bars and then in all of them (like the
  community's DDC). `dificultad_inicial` removes the easiest levels.
- **0.2.4.2**: fixed 0.2.4's repeated-note splitting, which invented notes in silences (the tail of a
  fading note was taken for a new hit; in "Rostro de actriz" there were ~130 ghost notes, almost all on
  the D and G strings). When CREPE and pYIN disagree by a semitone, the note in the song's key wins (the
  key is estimated automatically).
- **0.2.4.1**: Beat This! runs only once per song (it used to run twice, doubling the bar stage). When Beat
  This! counts at half tempo its downbeat is also used, and if madmom jumps between tempos its beats are
  used. Songs without bass (the separated track is almost silent) are skipped with a warning instead of
  inventing a tab. Repeated phrases are recognised with a one-sixteenth margin.
- **0.2.4**: three new engines. (1) Repeated notes (A-A-A-A) that came out as one held note are split
  where the bass is plucked again (`partir_repetidas`, `umbral_reataque_db`). (2) Each note's pitch comes
  from CREPE (`tono_crepe`). (3) The downbeat comes from Beat This! when it counts the same beat as madmom;
  its model (81 MB) is downloaded to `modelos\` on first use with a checksum, or you can copy
  `beat_this-final0.ckpt` there.
- **0.2.3.2**: album art, album and year always come from the same album (previously the original album's
  cover could appear with the name and year of the compilation in the tags).
- **0.2.3.1**: `dificultad_inicial` in `configuracion.txt`: the custom DD starts with that % of each
  phrase's notes (for example 60) and rises in five steps to the full phrase.
- **0.2.3**: fixed a one-sixteenth shift of the whole tab in some songs (notes on the beat and on the "and"
  landed on the "e" and the "a"). Repeated phrases are recognised even if the transcription isn't
  identical, so they really share progress. Tags from YouTube downloads ("ArtistVEVO", "(Videoclip)")
  cleaned up; double spaces in titles; the album takes the store's spelling.
- **0.2.2.1**: fixed the custom DD: each phrase's reference levels were missing, so the game showed 100 %
  mastery and scored only on the easiest level's notes.
- **0.2.2**: custom dynamic difficulty (`dificultad = propia`): five levels, the same across the song (one
  note per bar, per half bar, per beat, per eighth and complete), 4-bar phrases, and repeated phrases share
  progress. You can switch back to DLC Builder's or turn it off (`dlcbuilder`, `ninguna`).
- **0.2.1.1**: artist and title from the mp3's ID3 tags (when valid); the output folder is named
  `Artist - Title` even if the file is called "01 - track.mp3".
- **0.2.1**: full diagnostics for each song (`diagnostico.json` in its folder and a DIAGNÓSTICO section at
  the end of the log, also for errors); the builder checks the freshly made psarc (DD levels, phrases,
  notes). Fixed: false odd bars at the end, garbled accented text ("EdiciÃ³n"), accents lost in the psarc
  name, and album art from "EP" or "Imprescindibles" releases.
- **0.2.0.2**: the *Tuning Pitch* only changes for deviations of 30 cents or more (`umbral_cents`).
- **0.2.0.1**: album art, album and year come from the original album, not from compilations or live
  albums.
- **0.2.0**: automatic build to `.psarc` (without opening DLC Builder) into its own folder, configurable
  in `configuracion.txt`. Album art, album and year from iTunes/Deezer.
- **0.1.3.2**: general log for each batch.
- **0.1.3.1**: minute of each odd bar in the report; texts updated.
- **0.1.3**: arrangement XML and DLC Builder project generated directly; EOF no longer needed.
- **0.1.2**: odd bars detected bar by bar.
- **0.1.1.x**: automatic tuning, tuning reference in cents, pick index (7 dB threshold) and fixes (fast
  tempos, false Eb/B, songs starting mid-bar).
- **0.1.0**: first version.

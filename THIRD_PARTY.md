# Third-party software

**English** | [Español](TERCEROS.md)

auto-cdlc builds on a lot of other people's work. None of these projects is affiliated with auto-cdlc.
Each keeps its own licence: check its repository for the full text.

## Installed by `instalar.bat` (Python packages)

| Project | Used for | Licence |
|---|---|---|
| [madmom](https://github.com/CPJKU/madmom) | Beat and time signature | Code BSD; **models and data CC BY-NC-SA 4.0 (non-commercial)** |
| [Beat This!](https://github.com/CPJKU/beat_this) | Downbeat and beat | Code MIT; the model is downloaded separately, check its repository |
| [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | Bass separation | MIT |
| MDX-Net model *kuielab_b_bass* | Bass separation (downloaded by audio-separator) | See [kuielab/mdx-net](https://github.com/kuielab/mdx-net) |
| [torchcrepe](https://github.com/maxrmorrison/torchcrepe) (CREPE) | Note pitch | MIT |
| [librosa](https://github.com/librosa/librosa) | Audio analysis | ISC |
| [PyTorch](https://pytorch.org), [ONNX Runtime](https://onnxruntime.ai), NumPy, SciPy | Computation | BSD / MIT |
| [pretty_midi](https://github.com/craffel/pretty-midi) | MIDI | MIT |
| [PyGuitarPro](https://github.com/Perlence/PyGuitarPro) | `.gp5` file | LGPL-3.0 |
| [mutagen](https://github.com/quodlibet/mutagen) | ID3 tags | GPL-2.0 or later |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | Loudness | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | Album art | MIT-CMU |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Ships ffmpeg | BSD-2; ffmpeg is LGPL/GPL |

The madmom build in `vendor/` is the original, adapted to work without compiling. It keeps its licences.

## Shipped with the program

| Project | Used for | Licence |
|---|---|---|
| [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) (iminashi, DLC Builder's libraries) | `cdlc-pack`: building the `.psarc` | MIT (see `herramientas/cdlc-pack/LICENCIA-Rocksmith2014.NET.txt`) |

## Queried or downloaded while running

| Service or data | Used for |
|---|---|
| [iminashi/tones](https://github.com/iminashi/tones) | Database of official Rocksmith tones (the one DLC Builder uses) |
| [LRCLIB](https://lrclib.net) | Synced lyrics. Lyrics belong to their authors. |
| iTunes Search API, Deezer API | Album art, album and year |

## You install these yourself

- **Wwise** (Audiokinetic): proprietary software with its own licence, needed for Rocksmith audio.
- **CDLC Enabler** (CustomsForge): lets Rocksmith load custom songs.

## About commercial use

madmom's models are licensed CC BY-NC-SA. So, although auto-cdlc's code is MIT, the program as a whole may
only be used non-commercially.

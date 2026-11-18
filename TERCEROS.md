# Software de terceros

auto-cdlc se apoya en mucho trabajo ajeno. Ninguno de estos proyectos está afiliado a auto-cdlc. Cada uno
mantiene su licencia: consulta su repositorio para el texto completo.

## Se instalan con `instalar.bat` (paquetes de Python)

| Proyecto | Uso en auto-cdlc | Licencia |
|---|---|---|
| [madmom](https://github.com/CPJKU/madmom) | Pulso y compás | Código BSD; **modelos y datos CC BY-NC-SA 4.0 (uso no comercial)** |
| [Beat This!](https://github.com/CPJKU/beat_this) | Tiempo 1 y pulso | Código MIT; el modelo se descarga aparte, consulta su repositorio |
| [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | Separación del bajo | MIT |
| Modelo MDX-Net *kuielab_b_bass* | Separación del bajo (lo descarga audio-separator) | Consulta [kuielab/mdx-net](https://github.com/kuielab/mdx-net) |
| [torchcrepe](https://github.com/maxrmorrison/torchcrepe) (CREPE) | Altura de las notas | MIT |
| [librosa](https://github.com/librosa/librosa) | Análisis de audio | ISC |
| [PyTorch](https://pytorch.org), [ONNX Runtime](https://onnxruntime.ai), NumPy, SciPy | Cálculo | BSD / MIT |
| [pretty_midi](https://github.com/craffel/pretty-midi) | MIDI | MIT |
| [PyGuitarPro](https://github.com/Perlence/PyGuitarPro) | Archivo `.gp5` | LGPL-3.0 |
| [mutagen](https://github.com/quodlibet/mutagen) | Etiquetas ID3 | GPL-2.0 o posterior |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | Volumen | MIT |
| [Pillow](https://github.com/python-pillow/Pillow) | Carátulas | MIT-CMU |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | Trae ffmpeg | BSD-2; ffmpeg es LGPL/GPL |

La versión de madmom de `vendor/` es la original, adaptada para funcionar sin compilar. Sigue con sus
licencias.

## Va con el programa

| Proyecto | Uso | Licencia |
|---|---|---|
| [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) (iminashi, librerías de DLC Builder) | `cdlc-pack`: compilación del `.psarc` | MIT (ver `herramientas/cdlc-pack/LICENCIA-Rocksmith2014.NET.txt`) |

## Se consultan o descargan al usarlo

| Servicio o dato | Uso |
|---|---|
| [iminashi/tones](https://github.com/iminashi/tones) | Base de tonos oficiales de Rocksmith (la misma que usa DLC Builder) |
| [LRCLIB](https://lrclib.net) | Letras sincronizadas. Las letras pertenecen a sus autores. |
| iTunes Search API, Deezer API | Carátula, álbum y año |

## Lo instalas tú

- **Wwise** (Audiokinetic): software propietario con su propia licencia, necesario para el audio de
  Rocksmith.
- **CDLC Enabler** (CustomsForge): para que Rocksmith cargue canciones propias.

## Nota sobre el uso comercial

Los modelos de madmom tienen licencia CC BY-NC-SA. Por eso, aunque el código de auto-cdlc es MIT, el
programa completo solo puede usarse sin fines comerciales.

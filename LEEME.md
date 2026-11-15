# cdlc-bajo 2.0: de mp3 a CDLC de bajo para Rocksmith 2014

Mete canciones (mp3, flac, wav, ogg, m4a…) y saca **archivos `.psarc` listos para jugar** con el
arreglo de **bajo**. Todo funciona en local y gratis, sin pagar tokens de IA.

Requisitos:
- Windows 10/11 de 64 bits y ~3 GB libres.
- Conexión a internet la primera vez (y para buscar carátulas).
- **Wwise** 2019, 2021, 2022 o 2023 instalado, que es lo que convierte el audio al formato de Rocksmith.
  Es el mismo que usa DLC Builder. Se descarga de https://ignition4.customsforge.com/tools/wwise

No hace falta instalar Python, ffmpeg ni .NET: el instalador y el paquete se encargan.

---

## 1. Instalación (una sola vez)

1. Descomprime esta carpeta donde quieras, por ejemplo en `Documentos\cdlc-bajo`.
2. Haz doble clic en **`instalar.bat`**. Tarda unos minutos.
3. Opcional: abre **`configuracion.txt`** y pon en `carpeta_psarc` la carpeta `dlc` de Rocksmith.
   Así las canciones aparecen directamente en el juego.

La primera canción que proceses descargará además el modelo de separación del bajo (30 MB).

## 2. Uso

- **Por lotes:** mete los mp3 en la carpeta **`entrada`** y haz doble clic en **`procesar.bat`**.
- **Sueltas:** arrastra una o varias canciones, o una carpeta, encima de `procesar.bat`.

**Artista y título**: se toman de las etiquetas del mp3 (ID3) si traen ambos y no son de relleno
("Unknown Artist", "Track 03", webs...). Si no, del nombre del archivo `Artista - Título.mp3`. Con
ellos se nombran la carpeta de `salida` y el psarc, se rellena la información del juego y se busca la
carátula. El `informe.txt` dice de dónde salió el nombre.

Las canciones ya procesadas se saltan (también las de versiones anteriores, con su carpeta antigua).
Para repetir una, borra su carpeta en `salida`.

Tarda de 3 a 5 minutos por canción, según el ordenador.

**Resultado:**
- Los **`.psarc`** van a la carpeta **`psarc`**, o a la que pongas en `configuracion.txt`. Si esa
  carpeta no es la `dlc` de Rocksmith, cópialos allí.
- En `salida\<canción>\` queda todo lo demás, incluido el **`informe.txt`** de cada canción.
- En `salida` queda además un **registro general** de cada tanda (`registro_AAAA-MM-DD_HH-MM.txt`):
  una línea por canción (bien, saltada o con error), los informes de todas y el detalle técnico de
  cualquier error. Es el archivo que hay que pasar si algo falla. Se va guardando según avanza.

## 3. `configuracion.txt`

| Clave | Para qué |
|---|---|
| `carpeta_psarc` | Dónde dejar los `.psarc`. Vacío: carpeta `psarc` junto al programa. |
| `compilar_psarc` | `si` (por defecto) o `no` para quedarte solo con el proyecto `.rs2dlc`. |
| `buscar_caratulas` | `si` (por defecto) o `no` para no conectarse a internet. |
| `wwise` | Ruta a `WwiseConsole.exe`, solo si no la encuentra solo. |
| `umbral_cents` | Desvío mínimo de la grabación (en cents) para cambiar el *Tuning Pitch*. Por defecto 30: por debajo se queda en 440 y no reafinas en cada canción. |

Las mismas opciones existen en la línea de comandos: `--psarc CARPETA`, `--sin-psarc`, `--sin-internet`,
`--wwise RUTA` y `--forzar`, que vuelve a procesar las canciones ya hechas.

## 4. Qué hay en `salida\<canción>\`

| Archivo | Para qué |
|---|---|
| `informe.txt` | **Léelo primero**: psarc, afinación, referencia en cents, púa/dedos, compases irregulares. |
| `diagnostico.json` | Todas las medidas internas (tiempos, sonoridad, beats, notas, afinación...). Para depurar: no hace falta mirarlo. |
| `<nombre>.rs2dlc` | Proyecto de DLC Builder: el `.psarc` se compila desde aquí. Sirve para recompilar a mano. |
| `<nombre>_bass_RS2.xml` | El arreglo de bajo en formato Rocksmith. |
| `<nombre>.ogg`, `<nombre>_preview.ogg` | Audio con silencio inicial para el compás COUNT, y vista previa de 28 s. |
| `portada.png` | Carátula: de internet (iTunes/Deezer), la incrustada en el mp3 o una generada. |
| `<nombre>_AB.mp3` | **Con cascos**: izquierda = bajo real, derecha = tablatura sintetizada. |
| `<nombre>_clics.mp3` | La canción con un clic en cada beat, más agudo en el tiempo 1. |
| `<nombre>.gp5`, `<nombre>.svl` | Tablatura y mapa de beats, para retocar la canción en EOF. |
| `<nombre>.mid` | La transcripción en MIDI. |

### Lo que detecta solo (todo va ya dentro del `.psarc`)

- **Afinación**: E estándar, Eb, Drop D, D, Drop C#, C#, Drop C, C, Drop B o B estándar. Se queda en
  E estándar salvo que haya notas graves repetidas que no quepan. Solo tienes que reafinar el bajo:
  el afinador de Rocksmith te lo pedirá.
- **Referencia de afinación de la grabación** (cents): muchos discos no están exactamente a La = 440 Hz.
  Solo si el desvío es grande (30 cents o más, configurable) se pone como *Tuning Pitch*. Si es menor, se
  queda en 440 para no obligarte a reafinar. Siempre se tiene en cuenta al reconocer las notas.
- **Púa o dedos**: a partir de 7 dB de "clic" en el ataque, púa. Si sale cerca del umbral, el informe
  avisa para que lo compruebes de oído.
- **Compases irregulares** (2, 3, 5 o 6 tiempos): se siguen compás a compás. El informe da el minuto
  de cada uno en la canción original.
- **Carátula, álbum y año**: si el mp3 no los trae, se buscan en iTunes o Deezer. Solo se acepta una
  carátula si coinciden artista y título.

### Revisión rápida

1. Escucha `_clics.mp3`: los clics deben ir con la batería y el agudo caer en el "uno".
2. Escucha `_AB.mp3` con cascos:
   - suena solo la izquierda → **falta** una nota;
   - suena solo la derecha → **sobra** una nota;
   - suenan las dos pero desafinan → nota equivocada o en otra octava.

## 5. En Rocksmith

Para tocar todas las notas desde el principio sin perder el seguimiento: **Riff Repeater** → selecciona
la canción entera (teclas **0** y **9**) → **Set Difficulty** al 100 %.

## 6. Compilar o retocar a mano

- **Recompilar con DLC Builder**: abre el `.rs2dlc` (**Project → Open Project…**, o arrástralo a su
  ventana) y pulsa **Build**. Sirve si el `.psarc` no se generó (el informe dice por qué) o si quieres
  cambiar el tono, la portada…
- **Corregir notas en Editor on Fire**: crea un proyecto nuevo con el `.ogg` (**File → New**) e importa
  el `.svl` (**File → Import → Sonic Visualiser**). Luego importa el `.gp5` (**File → Import → Guitar Pro**,
  pista **PART REAL_BASS**, aceptando los *time signatures*). En DLC Builder sustituye después el XML del
  arreglo por el que guarde EOF.

## 7. Limitaciones

- Bajo de **4 cuerdas**. Compás de base 4/4, con compases sueltos de 2, 3, 5 o 6 tiempos; no sirve para
  canciones enteras en 3/4 o 6/8.
- La transcripción es automática: ritmo y notas salen bien en general, pero puede haber notas
  sueltas de más o de menos. Repasa con el A/B.
- No detecta técnicas (slides, ligados, slap…): todo sale como notas normales.
- Funciona mejor cuanto más claro suene el bajo en la mezcla.

## 8. Cómo funciona por dentro

1. **Separación del bajo**: modelo MDX *kuielab_b_bass* mediante `audio-separator`.
2. **Beats y compases**: `madmom` (red neuronal + modelo probabilístico), con el "uno" seguido compás a
   compás. En `vendor\` va una versión 100 % Python de madmom, verificada contra la original.
3. **Notas**: ataques con `librosa`, altura con pYIN y, cuando pYIN duda, con una CQT con suma de armónicos.
4. **Cuantización** a semicorcheas, con corrección automática del desfase entre ataque y pulso.
5. **Afinación y digitación**: programación dinámica que minimiza el movimiento de la mano.
6. **Arreglo y proyecto**: XML de Rocksmith con posiciones de mano, y proyecto de DLC Builder. Antes de
   compilar se repiten las mismas comprobaciones que hace DLC Builder.
7. **Compilación** (`herramientas\cdlc-pack`): usa las librerías de DLC Builder (Rocksmith2014.NET, de
   iminashi, licencia MIT). Convierte el audio con Wwise, genera la dificultad dinámica y empaqueta el
   `.psarc` con los mismos ajustes por defecto que el "Build Release" de DLC Builder. Su código va en
   `herramientas\cdlc-pack\codigo`.

Los modelos de madmom tienen licencia CC BY-NC-SA: solo para uso no comercial.

## 9. Problemas

- **`instalar.bat` falla al instalar uv**: instálalo a mano desde https://docs.astral.sh/uv/ y vuelve a ejecutarlo.
- **"No encuentro uv"**: cierra la ventana y vuelve a abrir `procesar.bat`. Si sigue, ejecuta otra vez `instalar.bat`.
- **"sin psarc: … Wwise …"**: no encuentra Wwise. Comprueba que está instalado o pon su ruta en
  `configuracion.txt` (`wwise = …\WwiseConsole.exe`). Mientras tanto, compila a mano con DLC Builder.
- **Una canción da ERROR**: el resto del lote sigue. El detalle va en el registro general.
- **"tiempo 1 dudoso"**: puede que el compás esté desplazado. Compruébalo con el archivo de clics.

## Historial

- **2.4**: tres motores nuevos. (1) Las notas repetidas (La-La-La-La) que salían como una sola nota
  mantenida se cortan donde el bajo vuelve a pulsar (`partir_repetidas`, `umbral_reataque_db`).
  (2) El tono de cada nota sale de CREPE (`tono_crepe`). (3) El tiempo 1 sale de Beat This! cuando
  cuenta el mismo pulso que madmom; su modelo (81 MB) se descarga solo la primera vez a `modelos\`
  con comprobación de huella, o puedes copiar ahí `beat_this-final0.ckpt`.
- **2.3.2**: carátula, álbum y año salen siempre del mismo disco (antes podía salir la portada del
  disco original con el nombre y el año del recopilatorio que traían las etiquetas).
- **2.3.1**: `dificultad_inicial` en `configuracion.txt`: la DD propia empieza con ese % de notas de cada
  frase (por ejemplo 60) y sube en cinco escalones hasta la completa.
- **2.3**: arreglado un corrimiento de toda la tablatura una semicorchea en algunas canciones (las notas
  del tiempo y del "y" caían en la "e" y la "a"). Las frases repetidas se reconocen aunque la
  transcripción no salga idéntica, así comparten progreso de verdad. Etiquetas de descargas de YouTube
  ("ArtistaVEVO", "(Videoclip)") limpiadas; espacios dobles en títulos; el álbum toma la grafía de la tienda.
- **2.2.1**: arreglada la DD propia: faltaban los niveles de referencia de cada frase, y el juego daba
  100 % de dominio y puntuaba solo sobre las notas del nivel más fácil.
- **2.2**: dificultad dinámica propia (`dificultad = propia`): cinco niveles iguales en toda la canción
  (una nota por compás, por medio compás, por tiempo, por corchea y completa), frases de 4 compases y
  las repetidas comparten progreso. Se puede volver a la de DLC Builder o quitarla (`dlcbuilder`, `ninguna`).
- **2.1.1**: artista y título desde las etiquetas ID3 del mp3 (si son válidas); la carpeta de salida
  se llama `Artista - Título` aunque el archivo se llame "01 - pista.mp3".
- **2.1**: diagnóstico completo de cada canción (`diagnostico.json` en su carpeta y una sección
  DIAGNÓSTICO al final del registro, también en los errores); el compilador comprueba el psarc
  recién hecho (niveles de DD, frases, notas). Arreglados: compases irregulares falsos al final,
  textos con acentos rotos ("EdiciÃ³n"), acentos perdidos en el nombre del psarc y carátulas de "EP"
  o "Imprescindibles".
- **2.0.2**: el *Tuning Pitch* solo cambia con desvíos de 30 cents o más (`umbral_cents`).
- **2.0.1**: la carátula, el álbum y el año salen del disco original y no de recopilatorios ni directos.
- **2.0**: compilación automática a `.psarc` (sin abrir DLC Builder) a una carpeta propia, configurable
  en `configuracion.txt`. Carátula, álbum y año desde iTunes/Deezer.
- **1.3.2**: registro general de cada tanda.
- **1.3.1**: minuto de cada compás irregular en el informe; textos al día.
- **1.3**: XML del arreglo y proyecto de DLC Builder generados directamente; ya no hace falta EOF.
- **1.2**: compases irregulares detectados compás a compás.
- **1.1.x**: afinación automática, referencia en cents, índice de púa (umbral 7 dB) y correcciones
  (tempos rápidos, falsos Eb/B, canciones que empiezan a mitad de compás).
- **1.0**: primera versión.

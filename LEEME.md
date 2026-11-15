# cdlc-bajo: de mp3 a CDLC de bajo para Rocksmith 2014

Convierte canciones (mp3, flac, wav, ogg, m4a…) en el material para montar un CDLC de **bajo** con
Editor on Fire (EOF) y DLC Builder. Todo funciona en local, gratis y sin pagar tokens de IA.

Requisitos: Windows 10/11 de 64 bits, conexión a internet la primera vez y ~3 GB libres.
No hace falta instalar Python ni ffmpeg: el instalador se encarga.

---

## 1. Instalación (una sola vez)

1. Descomprime esta carpeta donde quieras, por ejemplo en `Documentos\cdlc-bajo`.
2. Haz doble clic en **`instalar.bat`**. Instala `uv`, que es el gestor de Python, y descarga las
   librerías. Tarda unos minutos.

La primera canción que proceses descargará además el modelo de separación del bajo (30 MB).

## 2. Uso

- **Por lotes:** mete los mp3 en la carpeta **`entrada`** y haz doble clic en **`procesar.bat`**.
- **Sueltas:** arrastra una o varias canciones, o una carpeta, encima de `procesar.bat`.

**Nombra los archivos `Artista - Título.mp3`**: de ahí salen el artista y el título.
Las canciones ya procesadas se saltan. Para repetir una, borra su carpeta en `salida`.

Tarda de 2 a 4 minutos por canción, según el ordenador.

## 3. Qué obtienes

En `salida\<nombre de la canción>\`:

| Archivo | Para qué |
|---|---|
| `<nombre>.rs2dlc` | **Proyecto de DLC Builder listo para compilar.** Es lo único que tienes que abrir. |
| `<nombre>_bass_RS2.xml` | El arreglo de bajo en formato Rocksmith (lo usa el proyecto). |
| `<nombre>_preview.ogg`, `portada.png` | Vista previa de 28 s y portada (la del mp3 o una generada). |
| `<nombre>.ogg` | El audio con silencio al principio, para el compás de cuenta (COUNT). |
| `<nombre>.svl`, `<nombre>.gp5` | Mapa de beats y tablatura, solo si quieres retocar la canción en EOF (ver más abajo). |
| `<nombre>_AB.mp3` | **Con cascos**: izquierda = bajo real, derecha = tablatura sintetizada. |
| `<nombre>_clics.mp3` | La canción con un clic en cada beat, más agudo en el tiempo 1. |
| `<nombre>.mid` | La transcripción en MIDI. |
| `informe.txt` | **Afinación, referencia en cents y púa/dedos** (léelo primero), más tempo y notas dudosas. |

### Lo que detecta solo (mira el informe)

- **Afinación**: E estándar, Eb, Drop D, D, Drop C#, C#, Drop C, C, Drop B o B estándar. Se queda en
  E estándar salvo que la canción tenga notas graves repetidas que no quepan; si las tiene, la nota
  más grave fija la cuerda grave y la digitación decide entre "drop" y estándar. La afinación va
  dentro del `.gp5`, así que EOF y DLC Builder la recogen solos. Solo tienes que reafinar el bajo.
- **Compases irregulares**: el "uno" se sigue compás a compás. Si en algún pasaje hay un compás de 2, 3,
  5 o 6 tiempos, el script lo detecta, lo pone así en el `.gp5` y la canción vuelve a cuadrar después.
  El informe dice en qué compases están. En EOF, acepta importar los compases (*time signatures*).
  Si la rotura es ambigua, puede quedar colocada un compás antes o después de donde está en realidad;
  las notas suenan igual en su sitio, solo cambia por dónde pasa la barra de compás.
- **Referencia de afinación de la grabación** (cents): muchos discos no están exactamente a La = 440 Hz.
  El informe te dice qué poner en **Tuning Pitch** en DLC Builder para que el afinador de Rocksmith
  te deje empastado con el disco. Además, el script descuenta ese desvío al reconocer las notas.
- **Púa o dedos**: mide el "clic" agudo del ataque de cada nota. A partir de 7 dB, púa; por debajo,
  dedos. Umbral calibrado con canciones conocidas; si sale a menos de 1 dB del umbral, el informe avisa
  para que lo compruebes de oído. Si es púa, márcalo en EOF
  (**Track → Rocksmith → Picked Bass**) o en la casilla **Picked** de DLC Builder.

### Revisión rápida antes de montar el CDLC

1. Escucha `_clics.mp3`: los clics deben ir con la batería y el agudo caer en el "uno".
2. Escucha `_AB.mp3` con cascos:
   - suena solo la izquierda → **falta** una nota;
   - suena solo la derecha → **sobra** una nota;
   - suenan las dos pero desafinan → nota equivocada o en otra octava.

## 4. Montar el CDLC

### Camino rápido: directo a DLC Builder (sin EOF)

1. Abre el `.rs2dlc` en DLC Builder: **Project → Open Project…**, o arrástralo a su ventana.
   Ya trae el arreglo, el audio, la vista previa, la portada, la afinación, el *Tuning Pitch*, la púa y un tono de bajo.
2. Pulsa **Build Test** o **Build Release**.

Deja marcado **Generate DD levels** en la configuración. Las frases y secciones las crea DLC Builder solo al compilar.
Si el informe dice "con problemas", es que el proyecto no pasaría las comprobaciones de DLC Builder. Avísame.

### Camino con retoques: pasando por Editor on Fire

Si una canción necesita correcciones (notas de más o de menos que oyes en el A/B), móntala en EOF:

Crea siempre un **proyecto nuevo** por canción y sigue este orden:

1. **File → New** y elige el `.ogg`.
2. **F9** (propiedades de la canción): revisa artista, título, álbum y año.
3. **File → Import → Sonic Visualiser** y elige el `.svl`. Si pregunta si desbloquear el mapa de tempo, di que **sí**.
4. **File → Import → Guitar Pro**, elige el `.gp5` y la pista **PART REAL_BASS**. Si ofrece importar los compases (time signatures), acepta.
5. Opcional: **Edit → Metronome** y **Edit → Claps** para comprobarlo de oído.
6. Guarda. El aviso de *fret hand positions* es normal: dale a Aceptar y EOF las genera solo.

### En DLC Builder (si has pasado por EOF)

1. **Add** el XML que guardó EOF, del tipo `PART REAL_BASS_RS2.xml`, de la carpeta del proyecto.
2. Audio: el `guitar.ogg` de la carpeta del proyecto de EOF. **Create** para la vista previa.
3. Tono: *A new tone* sirve. Asígnalo como tono base del bajo.
   En la ficha del arreglo, ajusta **Tuning Pitch** si el informe lo indica, y **Picked** si es con púa.
   Comprueba que la afinación que muestra el arreglo coincide con la del informe.
4. Si sale *"The first phrase contains notes"*, puedes darle a **Ignore**: DLC Builder crea las frases solo.
5. Configuración (engranaje) → **Build**: deja marcado **Generate DD levels**. Sin DD, Rocksmith no
   guarda el porcentaje ni la evolución de la canción.
6. **Build Test** o **Build Release**, y el `.psarc` a la carpeta `dlc` de Rocksmith.

Necesitas **Wwise** 2019 o 2021 instalado para que DLC Builder convierta el audio. Lo descargas de
https://ignition4.customsforge.com/tools/wwise

### En Rocksmith

Para tocar todas las notas desde el principio sin perder el seguimiento:
**Riff Repeater** → selecciona la canción entera (teclas **0** y **9**) → **Set Difficulty** al 100 %.

## 5. Limitaciones

- Bajo de **4 cuerdas**. Compás de base 4/4, con compases sueltos de 2, 3, 5 o 6 tiempos; no sirve para
  canciones enteras en 3/4 o 6/8. Afinaciones: las diez de la lista de arriba.
- La transcripción es automática: ritmo y notas salen bien en general, pero puede haber notas
  sueltas de más o de menos. Repasa con el A/B y corrige en EOF o en Guitar Pro / TuxGuitar.
- No detecta técnicas (slides, ligados, slap…): todo sale como notas normales.
- Funciona mejor cuanto más claro suene el bajo en la mezcla.

## 6. Cómo funciona por dentro

1. **Separación del bajo**: modelo MDX *kuielab_b_bass* mediante `audio-separator`.
2. **Beats y compases**: `madmom` (red neuronal + modelo probabilístico de tempo). Se incluye en
   `vendor\` una versión 100 % Python, sin compilar, para que se instale en Windows sin
   compilador. Se ha verificado que da los mismos resultados que la original.
3. **Notas**: los ataques se detectan con `librosa`, la altura con pYIN y, cuando pYIN duda,
   con una CQT con suma de armónicos.
4. **Cuantización** a semicorcheas sobre el grid de beats, con corrección automática del desfase
   entre ataque detectado y pulso.
5. **Afinación y digitación**: se elige la afinación como se explica arriba, y la digitación se hace
   con programación dinámica que minimiza el movimiento de la mano.
6. **Púa**: contraste de energía entre 2 y 8 kHz entre el ataque (0-45 ms) y el sostenido (80-200 ms).
7. **Salidas**: `.gp5` con PyGuitarPro, mapa de beats en formato Sonic Visualiser y audio con ffmpeg.

Los modelos de madmom tienen licencia CC BY-NC-SA: solo para uso no comercial.

## 7. Problemas

- **`instalar.bat` falla al instalar uv**: instálalo a mano desde https://docs.astral.sh/uv/ y vuelve a ejecutarlo.
- **"No encuentro uv"**: cierra la ventana y vuelve a abrir `procesar.bat`. Si sigue, ejecuta otra vez `instalar.bat`.
- **Una canción da ERROR**: el resto del lote sigue procesándose. El motivo sale al final, en el resumen.
- **"tiempo 1 dudoso"**: puede que el compás empiece desplazado. Compruébalo con el archivo de clics.

## Historial

- **1.3.1**: el informe da el minuto de cada compás irregular y sus textos reflejan que afinación,
  Tuning Pitch y púa ya van dentro del proyecto.
- **1.3**: el script genera directamente el XML del arreglo y el proyecto de DLC Builder (`.rs2dlc`) con
  portada, vista previa y volumen automático. Ya no hace falta pasar por EOF.
- **1.2**: compases irregulares (2/4, 3/4, 5/4, 6/4) detectados compás a compás; ya no se descoloca
  el resto de la canción tras un pasaje que rompe el compás.
- **1.1.3**: umbral de púa calibrado en 7 dB.
- **1.1.2**: en tempos rápidos (unos 140 BPM o más) la tablatura podía salir desplazada una semicorchea;
  corregido. La afinación grave solo se elige si el detector principal (pYIN) ve notas graves repetidas,
  para evitar falsos Eb/B por errores de octava.
- **1.1.1**: corregido el error "'list' argument must have no negative elements" en canciones
  cuyo bajo entra antes del primer compás completo.
- **1.1**: detección automática de afinación (10 afinaciones de 4 cuerdas), medición del desvío de
  afinación de la grabación (cents) con corrección al reconocer notas, e índice de púa/dedos (experimental).
- **1.0**: primera versión.

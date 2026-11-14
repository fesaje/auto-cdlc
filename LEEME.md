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
| `<nombre>.ogg` | El audio con silencio al principio, para el compás de cuenta (COUNT). **Es el que se abre en EOF.** |
| `<nombre>.svl` | El mapa de beats: las marcas de tiempo siguen a la banda aunque acelere o frene. |
| `<nombre>.gp5` | La tablatura de bajo (Guitar Pro 5). El compás 1 va vacío: es el COUNT. |
| `<nombre>_AB.mp3` | **Con cascos**: izquierda = bajo real, derecha = tablatura sintetizada. |
| `<nombre>_clics.mp3` | La canción con un clic en cada beat, más agudo en el tiempo 1. |
| `<nombre>.mid` | La transcripción en MIDI. |
| `informe.txt` | Tempo, número de notas, notas dudosas… |

### Revisión rápida antes de montar el CDLC

1. Escucha `_clics.mp3`: los clics deben ir con la batería y el agudo caer en el "uno".
2. Escucha `_AB.mp3` con cascos:
   - suena solo la izquierda → **falta** una nota;
   - suena solo la derecha → **sobra** una nota;
   - suenan las dos pero desafinan → nota equivocada o en otra octava.

## 4. Montar el CDLC

### En Editor on Fire

Crea siempre un **proyecto nuevo** por canción y sigue este orden:

1. **File → New** y elige el `.ogg`.
2. **F9** (propiedades de la canción): revisa artista, título, álbum y año.
3. **File → Import → Sonic Visualiser** y elige el `.svl`. Si pregunta si desbloquear el mapa de tempo, di que **sí**.
4. **File → Import → Guitar Pro**, elige el `.gp5` y la pista **PART REAL_BASS**. Si ofrece importar los compases (time signatures), acepta.
5. Opcional: **Edit → Metronome** y **Edit → Claps** para comprobarlo de oído.
6. Guarda. El aviso de *fret hand positions* es normal: dale a Aceptar y EOF las genera solo.

### En DLC Builder

1. **Add** el XML que guardó EOF, del tipo `PART REAL_BASS_RS2.xml`, de la carpeta del proyecto.
2. Audio: el `guitar.ogg` de la carpeta del proyecto de EOF. **Create** para la vista previa.
3. Tono: *A new tone* sirve. Asígnalo como tono base del bajo.
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

- Bajo de **4 cuerdas, afinación estándar (Mi-La-Re-Sol)** y compás de **4/4**.
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
5. **Digitación**: programación dinámica que minimiza el movimiento de la mano.
6. **Salidas**: `.gp5` con PyGuitarPro, mapa de beats en formato Sonic Visualiser y audio con ffmpeg.

Los modelos de madmom tienen licencia CC BY-NC-SA: solo para uso no comercial.

## 7. Problemas

- **`instalar.bat` falla al instalar uv**: instálalo a mano desde https://docs.astral.sh/uv/ y vuelve a ejecutarlo.
- **"No encuentro uv"**: cierra la ventana y vuelve a abrir `procesar.bat`. Si sigue, ejecuta otra vez `instalar.bat`.
- **Una canción da ERROR**: el resto del lote sigue procesándose. El motivo sale al final, en el resumen.
- **"tiempo 1 dudoso"**: puede que el compás empiece desplazado. Compruébalo con el archivo de clics.

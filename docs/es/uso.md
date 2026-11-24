# Uso

[English](../en/usage.md) | **Español**

## Procesar canciones

Los menús, las preguntas y los informes salen en el idioma elegido al instalar (`language = es` o `en` en
`config.txt`).

Desde la 0.5, las carpetas, los archivos, las opciones y las claves de `config.txt` van en inglés para todo
el mundo. Si vienes de la 0.4 o anterior, la primera vez se renombran tus carpetas (`entrada` → `input`,
`salida` → `output`…) y tu `configuracion.txt` se convierte en `config.txt` (queda una copia en
`configuracion.txt.bak`). Los nombres antiguos (`procesar.bat`, `--forzar`, claves y valores en español)
siguen funcionando.

**Actualizaciones**: al empezar, el programa mira si hay una versión nueva publicada. Si la hay, enseña
las novedades y pregunta si actualizar. La actualización:

- no toca tu configuración, tus canciones ni los modelos descargados;
- añade a `config.txt` las opciones nuevas, si las hay;
- vuelve a lanzar el programa con la versión nueva.

Si la tanda va desatendida, no se actualiza. Se desactiva con `check_updates = no` o
`--no-update`.

- **Por lotes:** mete las canciones (mp3, flac, wav, ogg, m4a…) en la carpeta **`input`** y haz doble
  clic en **`process.bat`**. Puedes ir dejando canciones ahí: las ya procesadas se saltan.
- **Sueltas:** arrastra canciones o una carpeta encima de `process.bat`.

### Antes de empezar: las preguntas de la tanda

1. **Revisa lo pendiente.** Compara `input` con `output` y te dice cuántas hay, cuántas están hechas y
   cuántas faltan.
2. **Agrupa por artista > disco**, con las etiquetas del mp3 (artista del disco y álbum). Si una canción
   no trae disco, lo busca en internet por artista y título. Si tampoco aparece, va a "(sin disco)".
3. **Fallidas de tandas anteriores**: si hay canciones que dieron error, las enseña y pregunta si
   reintentarlas (por defecto, no). Las que no se reintentan salen de la tanda y no se pregunta nada sobre
   ellas. Las que no tenían bajo (interludios, intros) se saltan sin preguntar.
4. **Preguntas de la tanda**: dificultad inicial, arreglo simplificado y si quieres **enviar los
   resultados** para ayudar a mejorar auto-cdlc (ver más abajo).
5. **Preguntas de cada disco**: tono del bajo y púa (`auto`, `pua` o `dedos`).
6. **Resumen**: ajustes, discos, número de canciones y tiempo estimado. Al final, "¿Empezar? (s/n)".

En todas las preguntas, **Intro** deja lo que hay entre corchetes. Es lo de `config.txt`, o lo que
elegiste la última vez para ese disco (se guarda en `output\album_settings.json`).

Si nadie contesta en 60 segundos (`question_timeout`), se usan los valores por defecto en todo y la tanda
arranca sola: puedes lanzarla y marcharte. Con `--no-questions` no pregunta nada.

Cada canción tarda unos 3-4 minutos, según el ordenador. Al final, el resumen lista las canciones que
conviene revisar (fiabilidad baja), las que se quedaron sin `.psarc` y las que no tenían bajo, y ofrece sacar
los archivos de la tanda de `input` (a `input\processed` y `input\discarded`).

### Qué sale

- Los **`.psarc`** van a la carpeta `psarc`, o a la que pongas en `psarc_folder` (lo práctico es la
  `dlc` de Rocksmith).
- En **`output\Artista - Título\`** queda todo lo demás:

| Archivo | Para qué |
|---|---|
| `informe.txt` | **Léelo primero**: afinación, púa, compás, tono, letra, arreglo simplificado, avisos. |
| `diagnostico.json` | Todas las medidas internas. Solo para depurar. |
| `*.rs2dlc` | Proyecto de DLC Builder, por si quieres recompilar o retocar a mano. |
| `*_bass_RS2.xml`, `*_bass2_RS2.xml`, `*_vocals_RS2.xml` | Arreglo de bajo, arreglo simplificado y letra en formato Rocksmith. |
| `*.ogg`, `*_preview.ogg` | Audio con silencio inicial para el compás de cuenta, y vista previa. |
| `portada.png` | Carátula. |
| `*_AB.mp3` | **Con cascos**: izquierda = bajo real, derecha = tablatura sintetizada. |
| `*_clics.mp3` | La canción con un clic en cada pulso, más agudo en el tiempo 1. |
| `*.gp5`, `*.svl`, `*.mid` | Tablatura (Guitar Pro), mapa de pulsos y MIDI, para Editor on Fire. |

- En `output` queda además el **registro de cada tanda** (`log_AAAA-MM-DD_HH-MM.txt`): una línea
  por canción, los informes y el diagnóstico completo. Es el archivo que hay que adjuntar si algo falla.

## `config.txt`

| Clave | Valores | Para qué |
|---|---|---|
| `psarc_folder` | ruta | Dónde dejar los `.psarc`. Vacío: carpeta `psarc` del programa. |
| `build_psarc` | `yes` / `no` | Con `no` solo se genera el proyecto `.rs2dlc`. |
| `online` | `yes` / `no` | Con `no` no se conecta a internet: sin carátulas, tonos oficiales, letra ni actualizaciones. |
| `wwise` | ruta | Carpeta de Wwise o ruta de `WwiseConsole.exe`, solo si no lo encuentra solo (mira Program Files y `WWISEROOT`). |
| `cents_threshold` | número (30) | Desvío mínimo de la grabación respecto a La = 440 para cambiar el *Tuning Pitch*. |
| `difficulty` | `own` (propia) / `dlcbuilder` / `none` (ninguna) | Tipo de dificultad dinámica (ver abajo). |
| `start_difficulty` | 0–95 | % de notas con que empieza cada frase. Se pregunta en cada tanda. |
| `split_repeated`, `reattack_threshold_db` | `yes` / `no`, dB (3) | Cortar las notas repetidas que salen como una larga. |
| `crepe_pitch` | `yes` / `no` | Tono de cada nota con la red CREPE. |
| `bass_tone` | `auto`, `clean`, `clean_pick`, `overdrive`, `distortion`, `fuzz` o un tono oficial | Sonido del bajo. Es el valor por defecto de la pregunta de cada disco. |
| `scroll_speed` | 0.5–5, o `auto 1.3` | Velocidad de las notas por el mástil (ver abajo). |
| `simple_arrangement` | `beat`, `half`, `bar`, `eighth`, `no` | Segundo arreglo simplificado. Se pregunta en cada tanda. |
| `lyrics` | `yes` / `no` | Letra en pantalla desde LRCLIB. |
| `question_timeout` | segundos (60) | Tiempo sin respuesta antes de arrancar con los valores por defecto. |
| `language` | `es` / `en` | Idioma de menús, preguntas e informes. Lo pregunta `install.bat`. |
| `check_updates` | `yes` / `no` | Buscar versiones nuevas al empezar y ofrecer instalarlas. |
| `send_results` | `ask` / `yes` / `no` | Envío voluntario de resultados (por defecto se pregunta en cada tanda). |

Opciones de la línea de comandos (para `process.bat` o `uv run auto_cdlc.py`): `--force` (repite canciones
ya hechas), `--no-questions`, `--no-update`, `--no-psarc`, `--offline`, `--rebuild` (ver abajo),
`--psarc CARPETA`, `--wwise RUTA` y `--output CARPETA`. `--help` las lista todas.

### Dificultad dinámica

Con `difficulty = own`, cada frase de 4 compases empieza con muy pocas notas y va sumando por pasos
rítmicos: una nota por compás, por medio compás, por tiempo, por corchea y todas. Cada paso entra
primero en los compases impares de la frase y luego en todos, hasta 10 niveles. Las frases que se repiten
(estribillos, estrofas) comparten progreso.

`start_difficulty` quita los niveles más fáciles. Con 50, cada frase empieza ya con la mitad de sus
notas.

### Tono del bajo

- `auto`: si la canción o el artista tienen DLC oficial, usa su tono. Para eso consulta una base de
  1.611 tonos de bajo oficiales, la misma que usa DLC Builder. Si no, usa el limpio, o el limpio
  brillante si se detecta púa.
- `clean` (limpio), `clean_pick` (limpio con púa), `overdrive` (saturado), `distortion`, `fuzz`: tonos de canciones oficiales elegidos como
  referencia para cada tipo de sonido.
- También vale el nombre de cualquier tono oficial, por ejemplo `RageKilling_bassdist`.

No hay detección automática de distorsión: con lo que deja el separador no se distingue bien. Por eso se
pregunta por disco.

### Velocidad de scroll

Es lo rápido que vienen las notas hacia ti:

- **Más baja:** las ves con más antelación, pero más juntas.
- **Más alta:** más separadas, pero con menos margen para leerlas.

Con `auto 1.3` se ajusta al tempo de cada canción: 1.3 a 120 BPM, la mitad a 60, vez y media a 180,
siempre entre 0.9 y 2.2.

### Arreglo simplificado

En el juego aparece como **"Alt. Bass"**, junto al bajo normal. Solo lleva las notas de los puntos fuertes
del ritmo:

- `beat`: una por tiempo (por defecto);
- `half`: una por medio compás;
- `bar`: una por compás;
- `eighth`: una por corchea.

Cada nota se mantiene hasta la siguiente. Tiene su propia dificultad dinámica y su propio porcentaje.

### Modelo de separación del bajo

`separation_model = mdx` (por defecto) da el tono de las notas más estable. `demucs` coloca las notas más
exactas en el tiempo en mezclas limpias, pero en las densas puede perder el tono, y tarda 1,5 veces más.
Vale la pena probarlo en una canción con el ritmo mal: cámbialo y vuelve a procesar esa canción con
`--force`. Con un bajo de sintetizador puede no encontrar bajo; para esas, vuelve a `mdx`.

### Letra

Se busca en [LRCLIB](https://lrclib.net) y solo se usa si la duración coincide con la de tu archivo
(±2 s). LRCLIB da el momento en que empieza cada línea: las palabras de la línea se reparten de forma
aproximada.

### Envío de resultados

Es voluntario: en cada tanda se pregunta. Intro equivale a "sí", pero si nadie contesta (tanda
desatendida) no se envía nada. Si dices que sí, al acabar cada canción se envía:

- el diagnóstico, el informe y la tablatura (los XML del bajo);
- la versión, el sistema y la configuración usada;
- un identificador anónimo de la instalación.

Nunca se envían el audio ni la letra, y las rutas de tu ordenador se quitan antes de enviar. Son unos
10 KB por canción. Sirve para encontrar los casos en los que falla y mejorar el programa.

## Lo que detecta solo

- **Afinación**: E estándar, Eb, Drop D, D, Drop C#, C#, Drop C, C, Drop B o B estándar. Se queda en E
  estándar salvo que haya notas graves que no quepan. El afinador de Rocksmith te pide la correcta.
- **Referencia de afinación de la grabación**: muchos discos no están a La = 440 Hz. Si el desvío es
  grande (`cents_threshold`), se pone como *Tuning Pitch*.
- **Púa o dedos**, por el "clic" del ataque. Se puede fijar por disco.
- **Compás**: 4/4 o 3/4 (también 6/8), con compases sueltos de 2 a 6 tiempos. El informe da el minuto
  de cada compás irregular.
- **Canciones sin bajo** (interludios, intros): se saltan con un aviso en vez de inventar una
  tablatura.

## Revisar el resultado

1. Escucha `_clics.mp3`: los clics deben ir con la batería y el agudo caer en el tiempo 1. Si el
   informe dice "tiempo 1 dudoso", empieza por aquí.
2. Escucha `_AB.mp3` con cascos:
   - suena solo la izquierda → **falta** una nota;
   - suena solo la derecha → **sobra** una nota;
   - suenan las dos pero desafinan → nota equivocada o en otra octava.

## En Rocksmith

- Elige la canción en *Learn a Song*. Si tiene arreglo simplificado, verás **Bass** y **Alt. Bass**.
- La dificultad dinámica sube sola según aciertas. Para tocarla entera desde el principio: **Riff
  Repeater** → selecciona toda la canción → *Set Difficulty* al 100 %.

## La interfaz (`auto-cdlc.bat`)

Desde la 0.5.1 hay también una interfaz de texto, al estilo de Midnight Commander: ejecuta
**`auto-cdlc.bat`**. Se maneja con ratón o teclado y tiene tres pestañas:

- **Canciones**: todas las procesadas por artista, álbum y título (pulsa una cabecera para ordenar por esa
  columna, **/** para filtrar), con fiabilidad, BPM, afinación, tono, púa, velocidad de scroll y
  arreglo. Al seleccionar una ves su informe. Teclas: **e** retocar (tono, púa, velocidad… ver abajo),
  **b** volver a compilar el `.psarc`, **o** abrir su carpeta, **c** oír los clics, **a** oír el A/B,
  **r** recargar.
- **Tanda**: las canciones de `input` (marcadas las ya procesadas). Marca las que quieras, elige dificultad
  inicial, arreglo simplificado, tono, púa y si envías resultados, y pulsa **Empezar**. El progreso sale
  debajo. Es lo mismo que `process.bat`, sin las preguntas.
- **Ajustes**: todas las opciones de `config.txt` con una explicación corta. **Guardar** las escribe en el
  archivo.

`process.bat` sigue funcionando como siempre. Los dos buscan versión nueva al arrancar.

**Dónde van los .psarc.** Si tienes varias instalaciones de Rocksmith en el PC (otras bibliotecas de Steam,
una copia en otro disco), **Buscar Rocksmith…**, junto a `psarc_folder` en Ajustes, las lista todas con
cuántos .psarc tiene cada carpeta dlc; elige una, o la primera opción para la carpeta `psarc` de auto-cdlc,
y pulsa Guardar. Lo mismo desde la línea de comandos: `process.bat --find-rocksmith`. El instalador también
lo pregunta.

## Retocar una canción sin volver a analizarla

Tono, púa, velocidad de scroll, arreglo simplificado y dificultad inicial se pueden cambiar después en unos
segundos, sin volver a analizar el audio. Desde la interfaz (**e** sobre la canción) o desde la línea de
comandos:

```
process.bat --regenerate "output\Artista - Título" --tone fuzz --pick yes --scroll 1.6
```

Opciones: `--tone` (`auto`, `clean`, `clean_pick`, `overdrive`, `distortion`, `fuzz` o el nombre de un tono
oficial), `--pick yes|no`, `--scroll` (0,5–5), `--simple no|bar|half|beat|eighth` y `--start-difficulty`
(%). Lo que no pases se queda como está. Reescribe los XML y el proyecto de DLC Builder y vuelve a compilar
el `.psarc`; el cambio queda apuntado al final de `informe.txt`.

Las canciones procesadas antes de la 0.5.1 no tienen el análisis guardado (`analisis.json`), así que en
ellas solo se pueden cambiar tono, púa y velocidad.

Las mismas opciones sin `--regenerate` valen para toda una tanda y se saltan esas preguntas:
`process.bat --tone overdrive --pick no --simple bar`. También `--send yes|no`.

## Compilar o retocar a mano

- **DLC Builder**: abre el `.rs2dlc` (*Project → Open Project…*) y pulsa *Build*. Sirve si el `.psarc` no
  se generó o si quieres cambiar algo (tono, portada…).
- **Editor on Fire**: crea un proyecto con el `.ogg` e importa el `.svl` (*File → Import → Sonic
  Visualiser*). Después importa el `.gp5` (*File → Import → Guitar Pro*, pista *PART REAL_BASS*,
  aceptando los *time signatures*). Luego sustituye en DLC Builder el XML del arreglo por el que guarde
  EOF.
- **Reempaquetar con auto-cdlc**: después de retocar los XML del arreglo en la carpeta de la canción (o de
  guardar el XML de EOF encima de `..._bass_RS2.xml`), vuelve a crear el `.psarc` sin analizar el audio:

  ```
  process.bat --rebuild "output\Artista - Título"
  ```

  Se pueden pasar varias carpetas o archivos `.rs2dlc`. Usa el mismo Wwise y la misma carpeta `psarc`
  que el proceso normal. La dificultad dinámica solo se genera en los arreglos que tienen un solo nivel;
  si tu XML ya trae sus niveles, se respetan.

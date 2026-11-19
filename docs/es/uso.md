# Uso

[English](../en/usage.md) | **Español**

## Procesar canciones

Los menús, las preguntas y los informes salen en el idioma elegido al instalar (`idioma = es` o `en` en
`configuracion.txt`).

**Actualizaciones**: al empezar, el programa mira si hay una versión nueva publicada. Si la hay, enseña
las novedades y pregunta si actualizar. La actualización:

- no toca tu configuración, tus canciones ni los modelos descargados;
- añade a `configuracion.txt` las opciones nuevas, si las hay;
- vuelve a lanzar el programa con la versión nueva.

Si la tanda va desatendida, no se actualiza. Se desactiva con `buscar_actualizaciones = no` o
`--sin-actualizar`.

- **Por lotes:** mete las canciones (mp3, flac, wav, ogg, m4a…) en la carpeta **`entrada`** y haz doble
  clic en **`procesar.bat`**. Puedes ir dejando canciones ahí: las ya procesadas se saltan.
- **Sueltas:** arrastra canciones o una carpeta encima de `procesar.bat`.

### Antes de empezar: las preguntas de la tanda

1. **Revisa lo pendiente.** Compara `entrada` con `salida` y te dice cuántas hay, cuántas están hechas y
   cuántas faltan.
2. **Agrupa por artista > disco**, con las etiquetas del mp3 (artista del disco y álbum). Si una canción
   no trae disco, lo busca en internet por artista y título. Si tampoco aparece, va a "(sin disco)".
3. **Fallidas de tandas anteriores**: si hay canciones que dieron error (por ejemplo, interludios sin
   bajo), las enseña y pregunta si reintentarlas. Por defecto no. Las que no se reintentan salen de la
   tanda y no se pregunta nada sobre ellas.
4. **Preguntas de la tanda**: dificultad inicial, arreglo simplificado y si quieres **enviar los
   resultados** para ayudar a mejorar auto-cdlc (ver más abajo).
5. **Preguntas de cada disco**: tono del bajo y púa (`auto`, `pua` o `dedos`).
6. **Resumen**: ajustes, discos, número de canciones y tiempo estimado. Al final, "¿Empezar? (s/n)".

En todas las preguntas, **Intro** deja lo que hay entre corchetes. Es lo de `configuracion.txt`, o lo que
elegiste la última vez para ese disco (se guarda en `salida\ajustes_discos.json`).

Si nadie contesta en 60 segundos (`espera_preguntas`), se usan los valores por defecto en todo y la tanda
arranca sola: puedes lanzarla y marcharte. Con `--sin-preguntas` no pregunta nada.

Cada canción tarda unos 4–5 minutos, según el ordenador.

### Qué sale

- Los **`.psarc`** van a la carpeta `psarc`, o a la que pongas en `carpeta_psarc` (lo práctico es la
  `dlc` de Rocksmith).
- En **`salida\Artista - Título\`** queda todo lo demás:

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

- En `salida` queda además el **registro de cada tanda** (`registro_AAAA-MM-DD_HH-MM.txt`): una línea
  por canción, los informes y el diagnóstico completo. Es el archivo que hay que adjuntar si algo falla.

## `configuracion.txt`

| Clave | Valores | Para qué |
|---|---|---|
| `carpeta_psarc` | ruta | Dónde dejar los `.psarc`. Vacío: carpeta `psarc` del programa. |
| `compilar_psarc` | `si` / `no` | Con `no` solo se genera el proyecto `.rs2dlc`. |
| `buscar_caratulas` | `si` / `no` | Con `no` no se conecta a internet: sin carátulas, tonos oficiales ni letra. |
| `wwise` | ruta | Ruta de `WwiseConsole.exe`, solo si no lo encuentra solo. |
| `umbral_cents` | número (30) | Desvío mínimo de la grabación respecto a La = 440 para cambiar el *Tuning Pitch*. |
| `dificultad` | `propia` / `dlcbuilder` / `ninguna` | Tipo de dificultad dinámica (ver abajo). |
| `dificultad_inicial` | 0–95 | % de notas con que empieza cada frase. Se pregunta en cada tanda. |
| `partir_repetidas`, `umbral_reataque_db` | `si` / `no`, dB (3) | Cortar las notas repetidas que salen como una larga. |
| `tono_crepe` | `si` / `no` | Tono de cada nota con la red CREPE. |
| `tono_bajo` | `auto`, `limpio`, `limpio_pua`, `saturado`, `distorsion`, `fuzz` o un tono oficial | Sonido del bajo. Es el valor por defecto de la pregunta de cada disco. |
| `velocidad_scroll` | 0.5–5, o `auto 1.3` | Velocidad de las notas por el mástil (ver abajo). |
| `arreglo_simple` | `tiempo`, `medio`, `compas`, `corchea`, `no` | Segundo arreglo simplificado. Se pregunta en cada tanda. |
| `letra` | `si` / `no` | Letra en pantalla desde LRCLIB. |
| `espera_preguntas` | segundos (60) | Tiempo sin respuesta antes de arrancar con los valores por defecto. |
| `idioma` | `es` / `en` | Idioma de menús, preguntas e informes. Lo pregunta `instalar.bat`. |
| `buscar_actualizaciones` | `si` / `no` | Buscar versiones nuevas al empezar y ofrecer instalarlas. |
| `enviar_resultados` | `preguntar` / `si` / `no` | Envío voluntario de resultados (por defecto se pregunta en cada tanda). |

Opciones de la línea de comandos: `--forzar` (repite canciones ya hechas), `--sin-preguntas`, `--sin-actualizar`,
`--sin-psarc`, `--sin-internet`, `--psarc CARPETA`, `--wwise RUTA` y `--salida CARPETA`.

### Dificultad dinámica

Con `dificultad = propia`, cada frase de 4 compases empieza con muy pocas notas y va sumando por pasos
rítmicos: una nota por compás, por medio compás, por tiempo, por corchea y todas. Cada paso entra
primero en los compases impares de la frase y luego en todos, hasta 10 niveles. Las frases que se repiten
(estribillos, estrofas) comparten progreso.

`dificultad_inicial` quita los niveles más fáciles. Con 50, cada frase empieza ya con la mitad de sus
notas.

### Tono del bajo

- `auto`: si la canción o el artista tienen DLC oficial, usa su tono. Para eso consulta una base de
  1.611 tonos de bajo oficiales, la misma que usa DLC Builder. Si no, usa el limpio, o el limpio
  brillante si se detecta púa.
- `limpio`, `limpio_pua`, `saturado`, `distorsion`, `fuzz`: tonos de canciones oficiales elegidos como
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

- `tiempo`: una por pulso (por defecto);
- `medio`: una por medio compás;
- `compas`: una por compás;
- `corchea`: una por corchea.

Cada nota se mantiene hasta la siguiente. Tiene su propia dificultad dinámica y su propio porcentaje.

### Letra

Se busca en [LRCLIB](https://lrclib.net) y solo se usa si la duración coincide con la de tu archivo
(±2 s). LRCLIB da el momento en que empieza cada línea: las palabras de la línea se reparten de forma
aproximada.

### Envío de resultados

Es voluntario: en cada tanda se pregunta, con "no" por defecto. Si dices que sí, al acabar cada canción
se envía:

- el diagnóstico, el informe y la tablatura (los XML del bajo);
- la versión, el sistema y la configuración usada;
- un identificador anónimo de la instalación.

Nunca se envían el audio ni la letra, y las rutas de tu ordenador se quitan antes de enviar. Son unos
10 KB por canción. Sirve para encontrar los casos en los que falla y mejorar el programa.

## Lo que detecta solo

- **Afinación**: E estándar, Eb, Drop D, D, Drop C#, C#, Drop C, C, Drop B o B estándar. Se queda en E
  estándar salvo que haya notas graves que no quepan. El afinador de Rocksmith te pide la correcta.
- **Referencia de afinación de la grabación**: muchos discos no están a La = 440 Hz. Si el desvío es
  grande (`umbral_cents`), se pone como *Tuning Pitch*.
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

## Compilar o retocar a mano

- **DLC Builder**: abre el `.rs2dlc` (*Project → Open Project…*) y pulsa *Build*. Sirve si el `.psarc` no
  se generó o si quieres cambiar algo (tono, portada…).
- **Editor on Fire**: crea un proyecto con el `.ogg` e importa el `.svl` (*File → Import → Sonic
  Visualiser*). Después importa el `.gp5` (*File → Import → Guitar Pro*, pista *PART REAL_BASS*,
  aceptando los *time signatures*). Luego sustituye en DLC Builder el XML del arreglo por el que guarde
  EOF.

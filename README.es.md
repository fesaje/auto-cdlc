# auto-cdlc

[English](README.md) | **Español**

**De mp3 a CDLC de bajo para Rocksmith 2014, en tu PC y gratis.**

Metes tus canciones en una carpeta, ejecutas `procesar.bat` y sales con archivos `.psarc` listos para
tocar el bajo en Rocksmith 2014 Remastered. Cada canción trae:

- la **tablatura de bajo**, con **dificultad dinámica** (DD) como las oficiales,
- un **segundo arreglo simplificado** para calentar,
- el **tono del ampli** (el oficial si el artista tiene DLC),
- la **letra en pantalla** y la **carátula**, cuando las hay.

Todo se calcula en local con modelos de código abierto: sin cuentas, sin pagar por canción y sin subir tu
música a ningún sitio.

> Interfaz en español e inglés. Avisa cuando hay versiones nuevas y se actualiza solo.

---

## Por qué

Toco el bajo con Rocksmith y en las webs habituales de CDLC encontraba muy pocas canciones en español, así
que hice una herramienta para chartear las canciones que nadie ha charteado. Está pensada para **practicar
por tu cuenta** y también como **punto de partida** para quien quiera pulir un chart a mano.

## Qué hace

| Paso | Cómo |
|---|---|
| Separa el bajo del resto de la mezcla | Modelo MDX *kuielab_b_bass* (audio-separator) |
| Encuentra el pulso, el tiempo 1 y el compás (4/4, 3/4 y compases sueltos) | madmom + Beat This!, contrastado con la línea de bajo |
| Transcribe las notas, también las repetidas | librosa + pYIN + CREPE |
| Elige la afinación (E, Eb, Drop D, D… hasta B) y la digitación | programación dinámica que minimiza el movimiento de la mano |
| Dificultad dinámica parecida a la de las canciones oficiales | hasta 10 niveles por frase; las frases repetidas comparten progreso |
| Arreglo simplificado ("Alt. Bass") | una nota por tiempo, por medio compás o por compás: a elegir |
| Tono del bajo | el oficial si la canción o el artista tienen DLC; si no, el que elijas por disco |
| Letra, carátula, álbum y año | LRCLIB; etiquetas del mp3, iTunes o Deezer |
| Compila el `.psarc` sin abrir DLC Builder | `cdlc-pack`, hecho con las librerías de DLC Builder |

Funciona **por lotes**. Antes de empezar agrupa lo pendiente por artista y disco y pregunta lo justo
(dificultad inicial, tono y púa de cada disco). Luego trabaja solo, la noche entera si quieres: unos
**3-4 minutos por canción** en un PC normal. Al final sale un resumen con la **fiabilidad** de cada canción
y la lista de las que conviene revisar.

## Empezar

1. Instala **Wwise** (convierte el audio al formato de Rocksmith) y el **CDLC Enabler** (para que el juego
   cargue canciones propias).
2. Descarga `auto-cdlc-…-windows.zip` de la
   [última versión](https://github.com/fesaje/auto-cdlc/releases/latest), descomprímelo y ejecuta
   **`instalar.bat`**.
3. Mete tus canciones en `entrada` y ejecuta **`procesar.bat`**.

Paso a paso en **[docs/es/instalacion.md](docs/es/instalacion.md)**. Respuestas rápidas en las
**[preguntas frecuentes](docs/es/preguntas-frecuentes.md)**.

## Revisar y pulir una canción

Cada canción tiene su carpeta en `salida` con todo lo que se usó para crearla:

- **`_AB.mp3`**: con cascos, el bajo real a la izquierda y la tablatura a la derecha. Las notas falsas se
  oyen enseguida.
- **`_clics.mp3`**: un clic en cada tiempo, más agudo en el 1, para comprobar los compases.
- **`.gp5`**, **`.svl`**, los **XML** de los arreglos y un **proyecto de DLC Builder**: ábrelos en Guitar
  Pro, TuxGuitar, Editor on Fire o DLC Builder y corrige lo que haga falta.

Después de retocar, vuelve a crear el `.psarc` sin analizar otra vez el audio:

```
procesar.bat --reempaquetar "salida\Artista - Título"
```

## Documentación

- **[Instalación](docs/es/instalacion.md)**: requisitos, Wwise, CDLC Enabler, instalador y primera prueba.
- **[Preguntas frecuentes](docs/es/preguntas-frecuentes.md)**: cómo usarlo, revisar una canción, retocar y
  reempaquetar, problemas habituales.
- **[Uso](docs/es/uso.md)**: las preguntas de cada tanda, qué sale, todas las opciones de
  `configuracion.txt`.
- **[Cómo funciona](docs/es/funcionamiento.md)**: el proceso por dentro, para curiosos y para quien quiera
  colaborar.
- **[Historial de cambios](CHANGELOG.es.md)** · **[Software de terceros y licencias](TERCEROS.md)**.

## Limitaciones

- Solo **Windows** (10/11, 64 bits) y **bajo de 4 cuerdas**.
- Es una **transcripción automática**: las líneas de bajo claras y sencillas salen muy tocables; las muy
  movidas, sincopadas o con la mezcla embarrada tendrán notas de más, de menos o descolocadas. Los compases
  compuestos (6/8, 12/8) y el swing todavía no se resuelven bien.
- No detecta técnicas: slides, hammer-ons, slap o armónicos salen como notas normales.
- No sabe si el bajo va distorsionado: el tono se elige por disco o se toma del DLC oficial.

## Ayudar a mejorarlo

Al procesar una tanda pregunta si quieres enviar un **informe anónimo** de cada canción: el diagnóstico y
la tablatura generada, nunca el audio, la letra ni tus carpetas. Es voluntario
(`enviar_resultados = no` lo quita para siempre) y es lo que permite mejorar la transcripción.

¿Un fallo o una canción que sale mal? Abre una [incidencia](https://github.com/fesaje/auto-cdlc/issues) y
adjunta el **registro de la tanda** (`salida\registro_….txt`). En español o en inglés.

## Aviso legal

auto-cdlc no incluye ni descarga música. Está pensado para crear CDLC **de uso personal** a partir de
canciones que ya tienes. No subas los charts generados tal cual a webs de CDLC, y no compartas CDLC de
canciones con derechos sin permiso, sobre todo si existen como DLC oficial.

Rocksmith es una marca de Ubisoft. Este proyecto no está afiliado a Ubisoft ni a CustomsForge.

Los modelos de madmom tienen licencia CC BY-NC-SA, así que el programa en conjunto solo puede usarse de
forma **no comercial**. Detalles en [TERCEROS.md](TERCEROS.md).

## Licencia

Código bajo licencia [MIT](LICENSE). El software de terceros mantiene sus propias licencias.

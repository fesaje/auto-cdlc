# auto-cdlc

[English](README.md) | **Español**

**De mp3 a CDLC de bajo para Rocksmith 2014, en tu PC y gratis.**

Metes tus canciones en una carpeta, ejecutas un `.bat` y sales con archivos `.psarc` listos para tocar
el bajo en Rocksmith 2014 Remastered. Para cada canción se generan:

- la tablatura de bajo,
- la dificultad dinámica,
- el tono del ampli,
- la carátula,
- la letra en pantalla (si está disponible),
- un segundo arreglo simplificado.

Todo se calcula en local con modelos de código abierto: sin cuentas, sin pagar por canción y sin subir tu
música a ningún sitio.

> El programa habla español e inglés (lo pregunta el instalador), avisa cuando hay versiones nuevas y se
> actualiza solo.

---

## Qué hace

| Paso | Cómo |
|---|---|
| Separa el bajo del resto de la mezcla | Modelo MDX *kuielab_b_bass* (audio-separator) |
| Encuentra el pulso, el tiempo 1 y el compás (4/4, 3/4, 6/8 y compases sueltos) | madmom + Beat This! |
| Transcribe las notas, también las repetidas | librosa + pYIN + CREPE |
| Elige la afinación (E, Eb, Drop D, D… hasta B) y la digitación | programación dinámica que minimiza el movimiento de la mano |
| Dificultad dinámica parecida a la de las canciones oficiales | hasta 10 niveles por frase; las frases repetidas comparten progreso |
| Tono del bajo | el oficial si la canción o el artista tienen DLC; si no, el que elijas por disco |
| Letra en pantalla | LRCLIB, si hay una versión con la misma duración |
| Segundo arreglo simplificado ("Alt. Bass") | una nota por tiempo, por compás… a elegir |
| Carátula, álbum y año | etiquetas del mp3, iTunes o Deezer |
| Compila el `.psarc` sin abrir DLC Builder | `cdlc-pack`, hecho con las librerías de DLC Builder |

Funciona por lotes: antes de empezar agrupa lo pendiente por artista y disco. Te pregunta lo justo
(dificultad inicial, tono y púa de cada disco) y procesa la noche entera sin vigilancia. Tarda unos
4–5 minutos por canción en un PC normal.

## Empezar

1. Instala **Wwise** (convierte el audio al formato de Rocksmith) y el **CDLC Enabler** (para que el
   juego cargue canciones propias).
2. Descarga el zip de la [última versión](https://github.com/fesaje/auto-cdlc/releases/latest),
   descomprímelo y ejecuta **`instalar.bat`**.
3. Mete tus mp3 en `entrada` y ejecuta **`procesar.bat`**.

Paso a paso en **[docs/es/instalacion.md](docs/es/instalacion.md)**.

## Documentación

- **[Instalación](docs/es/instalacion.md)**: requisitos, Wwise, CDLC Enabler, instalador y primera prueba.
- **[Preguntas frecuentes](docs/es/preguntas-frecuentes.md)**: respuestas rápidas: cómo usarlo, revisar una
  canción, retocar y reempaquetar a mano, problemas habituales.
- **[Uso](docs/es/uso.md)**: cómo procesar canciones, las preguntas de cada tanda, qué sale, todas las
  opciones de `configuracion.txt`, cómo revisar el resultado y cómo tocarlo en Rocksmith.
- **[Cómo funciona](docs/es/funcionamiento.md)**: el proceso por dentro, para curiosos y para quien quiera
  colaborar.
- **[Historial de cambios](CHANGELOG.es.md)**.
- **[Software de terceros y licencias](TERCEROS.md)**.

## Limitaciones

- Solo **Windows** (10/11, 64 bits) y bajo de **4 cuerdas**.
- La transcripción es automática. Ritmo y notas suelen salir bien, pero puede haber notas de más o de
  menos, sobre todo si el bajo suena poco en la mezcla.
- No detecta técnicas: slides, ligados, slap y armónicos salen como notas normales.
- No detecta si el bajo va distorsionado: el tono se elige por disco o sale del DLC oficial.

## Aviso legal

auto-cdlc no incluye ni descarga música. Está pensado para que hagas CDLC **de uso personal** a partir de
canciones que ya tienes. No compartas CDLC de canciones protegidas sin permiso, y menos de canciones que
existen como DLC oficial.

Rocksmith es una marca de Ubisoft. Este proyecto no está afiliado a Ubisoft ni a CustomsForge.

Los modelos de madmom tienen licencia CC BY-NC-SA: el conjunto solo puede usarse **sin fines
comerciales**. Detalles en [TERCEROS.md](TERCEROS.md).

## Licencia

Código bajo licencia [MIT](LICENSE). El software de terceros mantiene sus propias licencias.

## Colaborar

Si algo falla, abre una [incidencia](https://github.com/fesaje/auto-cdlc/issues) y adjunta el
**registro de la tanda** (`salida\registro_….txt`), que trae el diagnóstico completo de cada canción.

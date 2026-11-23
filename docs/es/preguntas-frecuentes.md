# Preguntas frecuentes

[English](../en/faq.md) | **Español**

Respuestas cortas a lo que más se pregunta. El detalle está en [Instalación](instalacion.md) y
[Uso](uso.md).

## Para empezar

### ¿Qué hace, en un párrafo?
Le das archivos de audio (mp3, flac, wav, ogg, m4a…) y te devuelve un CDLC de bajo para Rocksmith 2014 de
cada uno. Para cada canción separa el bajo de la mezcla, busca los tiempos y los compases, transcribe las
notas a tablatura, crea los niveles de dificultad (DD), añade letra y portada si las encuentra, elige un
tono de bajo y empaqueta el `.psarc`. Todo se hace en tu PC.

### ¿Cómo proceso canciones?
1. Mete las canciones en la carpeta **`input`** (o arrástralas encima de `process.bat`).
2. Haz doble clic en **`process.bat`**.
3. Contesta las preguntas (o pulsa Intro: los valores entre corchetes son razonables).
4. Espera. Los `.psarc` acaban en la carpeta `psarc`, o en la que pongas en `psarc_folder`.

Puedes seguir añadiendo canciones a `input`: las ya procesadas se saltan.

### ¿Qué me va a preguntar?
Una vez por tanda: dificultad inicial, arreglo simplificado y si quieres enviar resultados anónimos. Una
vez por disco: tono del bajo y púa o dedos. Después, un resumen con el tiempo estimado y "¿Empezar?". Si
nadie contesta en 60 segundos, usa los valores por defecto y arranca solo, así que puedes lanzarlo e irte.

### ¿Cuánto tarda?
Unos 3-4 minutos por canción en un PC normal. Una tanda de 100 canciones es trabajo de una noche.

### ¿Dónde pongo el `.psarc` para que lo vea el juego?
En la carpeta `dlc` de Rocksmith. Lo más cómodo es poner esa carpeta en `psarc_folder` en
`config.txt` (el instalador se ofrece a hacerlo). El juego necesita además el **CDLC Enabler**: mira
[Instalación](instalacion.md#cdlc-enabler-para-que-rocksmith-cargue-canciones-propias).

### ¿Se puede usar en inglés?
Sí: `language = en` en `config.txt`. El instalador lo pregunta la primera vez.

## Calidad

### ¿Cómo de buenas salen las tablaturas?
Es una transcripción automática. Las líneas de bajo claras y sencillas salen muy tocables; las muy movidas,
sincopadas o con la mezcla embarrada tendrán fallos. Cada canción lleva una **fiabilidad** (alta, media,
baja) con los motivos, y al final de la tanda sale una lista de "Conviene revisar".

### ¿Cómo reviso una canción sin tocarla?
En su carpeta dentro de `output`:
- **`_AB.mp3`**, con cascos: el bajo real a la izquierda y la tablatura sonando a la derecha. Donde no
  coinciden, la tab está mal.
- **`_clics.mp3`**: la canción con un clic en cada tiempo, más agudo en el 1. Si el clic agudo no cae al
  principio del compás, los compases están corridos.
- **`informe.txt`**: afinación, compás, tono, letra y avisos.

### Me cuesta mucho tocarla
- Baja `start_difficulty` (o contesta más bajo cuando lo pregunta): la canción empieza con menos notas y
  Rocksmith las va añadiendo según tocas bien.
- Usa el **arreglo simplificado** (segundo arreglo de bajo en el juego): una nota por tiempo, por medio
  compás o por compás, según `simple_arrangement`.
- Si las notas no se parecen a lo que suena, es un fallo de transcripción: dime qué canción y en qué
  momento (mira "¿Cómo aviso de un problema?").

### Rocksmith me pide reafinar
El programa detectó una afinación distinta de Mi estándar porque encontró notas por debajo del Mi grave. A
veces bastan unas pocas notas mal detectadas para engañarlo. Mira `informe.txt`; si el grupo toca en Mi
estándar, dime la canción.

### Una canción sale "sin bajo"
El bajo separado estaba casi en silencio: interludios, intros, canciones acústicas… No es un error. Esas
canciones se saltan en las tandas siguientes; para repetirlas, usa `--force`.

## Retocar a mano

### ¿Puedo corregir la tablatura yo?
Sí. La carpeta de cada canción trae todo lo necesario: `.gp5` (Guitar Pro / TuxGuitar / EOF), `.svl`
(mapa de tiempos para EOF), los XML de los arreglos y un proyecto de DLC Builder (`.rs2dlc`). Mira
[Compilar o retocar a mano](uso.md#compilar-o-retocar-a-mano).

### ¿Cómo vuelvo a crear el `.psarc` después de retocar?
```
process.bat --rebuild "output\Artista - Título"
```
Vuelve a empaquetar la canción desde su proyecto y sus XML, sin analizar otra vez el audio. Se pueden pasar
varias carpetas.

### ¿Puedo subir las canciones a CustomsForge / Ignition?
Tal como salen del programa, no: son charts automáticos y no tienen la calidad que pide la comunidad. Si
las usas como base y pules un chart a mano hasta dejarlo como un CDLC de verdad, es otra historia: sigue
las normas de CustomsForge.

## Problemas

### No se crea el `.psarc`
Casi siempre es Wwise. El resumen final lista las canciones "sin .psarc" con el motivo. Hace falta Wwise
2019, 2021, 2022 o 2023: **la 2024 y posteriores no valen**, y el Audiokinetic Launcher instala por defecto
la más nueva. Instala también la 2023.1 desde el Launcher (pueden convivir) y auto-cdlc usará esa. Si está
en otra unidad, pon su carpeta en `wwise` en `config.txt`. Después, `process.bat --rebuild` sin nada más
crea los .psarc de todas las canciones que se quedaron sin él, sin volver a analizarlas.

### Dos versiones de la misma canción (estudio y directo)

Rocksmith distingue las canciones por artista y título. Desde la 0.5.1, si procesas una canción cuyo artista
y título ya están en `output` pero de otro mp3, se le añade el álbum al título: *Canción (Directo en X)*.
Las dos aparecen en el juego y ningún archivo pisa al otro. El álbum sale de las etiquetas del mp3, del nombre
"Artista - Álbum - NN - Título" o de la carpeta donde está el mp3.

Las canciones procesadas con versiones anteriores podían compartir una clave interna, y el juego solo
mostraba una. Al empezar cada tanda sale la lista de esas; regenera una de cada pareja (tecla **e** en
`auto-cdlc.bat`, o `process.bat --regenerate "output\<carpeta>"`) y copia su `.psarc` nuevo.

### Ha fallado la actualización
Suele ser un fallo puntual de red: vuelve a ejecutar `process.bat`. Tu instalación no se toca hasta que
una actualización termina bien.

### "No se han podido enviar los resultados"
El servidor no respondía. En España pasa los días de fútbol, cuando se bloquean algunas IPs de Cloudflare.
No se pierde nada: los resultados se guardan en `pending_uploads` y se mandan en la siguiente tanda.

### El antivirus protesta
Suele ser por el CDLC Enabler (`D3DX9_42.dll`) o por `cdlc-pack.exe`, un programa sin firmar. Añade una
excepción para esas carpetas.

### ¿Cómo aviso de un problema?
Abre una incidencia en [GitHub](https://github.com/fesaje/auto-cdlc/issues) y adjunta el registro de la
tanda, `output\log_AAAA-MM-DD_HH-MM.txt`. Di qué canción y, si es de la tablatura, más o menos dónde
(minuto:segundo).

## Otras

### ¿Qué se envía si digo que sí a enviar resultados?
El diagnóstico, el informe y la tablatura de bajo generada de cada canción. Nunca el audio, nunca la letra
y nunca tu nombre de usuario ni tus carpetas. Es anónimo y voluntario: `send_results = no` lo quita
para siempre.

### ¿Y para guitarra?
De momento, no. Separar una guitarra de la voz y de otras guitarras y transcribir acordes (sobre todo con
distorsión) es mucho más difícil que una línea de bajo. Está en la lista, pero lejos.

### ¿Mac o Linux?
No, de momento solo Windows: Rocksmith 2014, Wwise y la herramienta de empaquetado están montados para
Windows.

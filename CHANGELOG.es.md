# Historial de cambios

[English](CHANGELOG.md) | **Español**

Hasta la 0.2.9.1 el proyecto se llamaba **cdlc-bajo** y sus versiones iban numeradas como 1.x y 2.x
(la 2.9.1 es la 0.2.9.1). El historial de git guarda el código de las versiones 0.1.0, 0.1.1, 0.1.1.1,
0.1.3.1, 0.2.3, 0.2.3.2, 0.2.4, 0.2.5, 0.2.5.1, 0.2.5.2, 0.2.7, 0.2.8.1, 0.2.9 y 0.2.9.1. Las de antes de la
0.2.9.1 solo tienen los archivos de texto: código, configuración, LEEME e instaladores.

- **0.4.3** (sin publicar): la descarga de la actualización reintenta y, si no llega al servidor de código
  de GitHub, usa el paquete para Windows adjunto a la release. Los resultados que no se pueden enviar (p. ej.
  por los bloqueos de IPs de Cloudflare en España en días de fútbol) se guardan en `envios_pendientes` y se
  mandan en la siguiente tanda.
- **0.4.2**:
  - La estimación de tiempo antes de empezar se muestra en horas, minutos y segundos (por ejemplo,
    "unos 20 min 48 s (5 min 12 s por canción)").
  - Wwise se encuentra en cualquier unidad: por `WWISEROOT` aunque la carpeta no lleve el año, y la clave
    `wwise` acepta la carpeta de Wwise además de `WwiseConsole.exe`. Si falta, avisa antes de empezar.
  - Las canciones que terminan sin `.psarc` se cuentan y se listan aparte en el resumen final, con el
    motivo, en vez de parecer un "OK" normal.
  - Los beats se detectan mientras se separa el bajo, a la vez: en los resultados recibidos era más o menos
    un cuarto del tiempo de cada canción.
  - Cada canción lleva una fiabilidad (alta, media, baja) con los motivos (pulso inestable, tiempo 1 dudoso,
    muchos compases irregulares, notas fuera de la rejilla, tono del bajo poco claro). Sale en su línea y en
    una lista de "conviene revisar" al final.
  - Las canciones sin bajo ya no son un error: se marcan "sin bajo" y se saltan en las tandas siguientes
    (salvo con `--forzar`).
  - Los nombres de archivo tipo "Artista - Disco - 08 - Título" (sin etiquetas) dan título "Título" y disco
    "Disco"; se quitan el número de pista inicial y coletillas como "(Official Video)" o el id de YouTube.
  - El diagnóstico guarda dónde caen las notas dentro de cada tiempo, para estudiar swing y tresillos.
  - Cuando el tiempo 1 es dudoso, los compases se corren para empezar en el tiempo en el que más cambia de
    nota el bajo (suele cambiar con el acorde, en el 1).
  - Al final de cada tanda ofrece sacar sus archivos de `entrada`: los procesados a `entrada\procesadas` y
    los que dieron error o no tenían bajo a `entrada\descartadas`. No se borra nada y por defecto es que no.
- **0.4.1**:
  - En la pregunta de enviar resultados, Intro equivale a "sí". Si nadie contesta (tanda desatendida),
    no se envía nada.
  - Las herramientas de desarrollo (servidor de envíos, script de descarga y banco de pruebas) pasan a
    `desarrollo/`: siguen en el repositorio pero ya no van en el paquete ni en las actualizaciones.
  - Servidor de envíos: aviso opcional por Telegram de cada canción recibida. El script de descarga pide
    el token sin mostrarlo, porque escrito en la línea de comandos se rompía con `&` o `%`.
- **0.4.0**:
  - Interfaz en español e inglés: `instalar.bat` pregunta el idioma (`idioma` en `configuracion.txt`) y
    menús, preguntas, avisos, informes y registro salen en ese idioma. `configuracion.en.txt` es la
    plantilla con los comentarios en inglés.
  - Actualizaciones: al empezar busca si hay una versión nueva y ofrece instalarla sin pasar por GitHub.
    No toca la configuración, las canciones ni los modelos; añade las opciones nuevas a
    `configuracion.txt` y vuelve a lanzar el programa. `buscar_actualizaciones`, `--sin-actualizar`.
  - Envío voluntario de resultados (diagnóstico, informe y tablatura; nunca audio ni letra; sin rutas
    personales) a un servidor propio en Cloudflare Workers + R2. Se pregunta en cada tanda
    (`enviar_resultados`). Código del servidor y script de descarga en `desarrollo/` (solo en el repositorio).
- **0.3.0**: primera versión publicada, ahora como **auto-cdlc**.
  - Documentación nueva en inglés y español: README, guía de instalación, guía de uso, funcionamiento por dentro y licencias
    de terceros.
  - El instalador descarga `cdlc-pack` si no está, comprueba Wwise y ofrece dejar los `.psarc` en la
    carpeta `dlc` de Rocksmith.
  - `cdlc-pack` pasa a ser un único ejecutable que se publica en las *releases*.
  - El banco de pruebas sintético va en `pruebas/`.
  - Licencia MIT.
- **0.2.9.1**: la pregunta de reintentar las que fallaron va primero; si dices que no, sus discos ya no
  se preguntan ni salen en el resumen.
- **0.2.9**: antes de empezar mira qué hay pendiente en `entrada` frente a `salida` y lo agrupa por
  artista > disco (etiquetas; si no hay, consulta en internet). Pregunta la dificultad inicial y el arreglo
  simplificado de la tanda, si reintentar las que fallaron antes, y el tono y la púa de cada disco (Intro = lo
  de configuracion.txt o lo elegido la última vez para ese disco, guardado en `salida/ajustes_discos.json`).
  Resumen con tiempo estimado y confirmación. Si nadie contesta en `espera_preguntas` segundos (60) arranca
  sola con los valores por defecto. `--sin-preguntas` para no preguntar nada.
- **0.2.8.1**: `velocidad_scroll = auto 1.3` ajusta la velocidad de las notas al tempo de cada canción (1.3 a
  120 BPM, proporcional, entre 0.9 y 2.2). El informe dice la que se ha usado.
- **0.2.8**: compases ternarios: si la canción va en 3 (3/4, 6/8, zambas, valses) se escribe entera en 3/4
  en vez de 4/4 con decenas de compases "irregulares", y en esas canciones se aprovecha Beat This! aunque cuente
  al doble. Segundo arreglo simplificado ('Alt. Bass', opción `arreglo_simple`, por defecto una nota por tiempo,
  con su propia DD). Letra en pantalla desde LRCLIB si está con la misma duración (opción `letra`, sincronizada
  por líneas). Nueva opción `velocidad_scroll`. Beat This! sustituye a madmom a partir de un 3 % de pulsos
  inestables (antes 5 %). cdlc-pack recompilado para verificar también la letra.
- **0.2.7**: sonido del bajo en el juego (ampli y pedales) según la canción. Nueva opción `tono_bajo` en
  configuracion.txt: `auto` usa el tono oficial de Rocksmith si la canción o el artista tienen DLC oficial (base de
  1.611 tonos de bajo de DLC Builder, se baja sola la primera vez) y si no, limpio (o limpio brillante con púa).
  También se puede fijar `limpio`, `limpio_pua`, `saturado`, `distorsion`, `fuzz` o el nombre de un tono oficial.
  El informe de cada canción dice qué tono lleva. La detección automática de distorsión en el audio aún no se aplica:
  sus medidas se guardan en el diagnóstico para calibrarla.
- **0.2.6**: pulso más estable y más rápido. Los huecos donde el detector de beats se callaba (y salían compases de 6/4 o tempos
  absurdos) se rellenan, y los beats dobles se quitan. Si madmom salta de tempo y Beat This! cuenta igual, se usan los beats
  de Beat This!. La red de compases de madmom solo se calcula cuando hace falta (la fase de pulso pasa de ~160 s a ~50 s).
  Las frases ya no empiezan siempre en el compás 1: se prueba a desplazarlas 0-3 compases y se elige el corte que más
  repeticiones encuentra (más progreso compartido entre estribillos).
- **0.2.5.2**: si las etiquetas traen el álbum, la carátula y el año salen de ESE disco (búsqueda artista +
  álbum) y el nombre del disco es el de tus etiquetas. Solo si no se encuentra se busca por la canción.
- **0.2.5.1**: ritmo más fiel: cada nota se coloca desde el pico de su ataque y no desde el inicio
  "retrocedido", que a veces caía muy atrás y adelantaba la nota una semicorchea (al "a" del tiempo
  anterior). En "Mi furia paranoica" las notas fuera de su sitio bajan del 19 % al 7 %. Los empates de tono
  se resuelven con las notas que usa la propia canción (respeta modos como el mixolidio).
- **0.2.5**: DD más parecida a la de las canciones oficiales: hasta 10 niveles por frase, empezando con
  una nota cada dos compases. Cada paso rítmico entra primero en los compases impares de la frase y luego
  en todos (como el DDC de la comunidad). Con `dificultad_inicial` se quitan los niveles más fáciles.
- **0.2.4.2**: arreglado el corte de notas repetidas de la 0.2.4, que inventaba notas en los silencios (la
  cola de una nota apagándose se tomaba por un golpe nuevo; en "Rostro de actriz" eran ~130 notas
  fantasma, casi todas en las cuerdas Re y Sol). Cuando CREPE y pYIN discrepan en un semitono, gana la
  nota que está en la tonalidad de la canción (se estima sola).
- **0.2.4.1**: Beat This! se ejecuta una sola vez por canción (antes dos: el paso de compases tardaba el
  doble). Cuando Beat This! cuenta a mitad de tempo también se usa su tiempo 1, y si madmom salta entre
  tempos se usan sus beats. Las canciones sin bajo (lo separado es casi silencio) se saltan con un aviso
  en vez de inventar una tablatura. Las frases repetidas se reconocen con una semicorchea de margen.
- **0.2.4**: tres motores nuevos. (1) Las notas repetidas (La-La-La-La) que salían como una sola nota
  mantenida se cortan donde el bajo vuelve a pulsar (`partir_repetidas`, `umbral_reataque_db`).
  (2) El tono de cada nota sale de CREPE (`tono_crepe`). (3) El tiempo 1 sale de Beat This! cuando
  cuenta el mismo pulso que madmom; su modelo (81 MB) se descarga solo la primera vez a `modelos\`
  con comprobación de huella, o puedes copiar ahí `beat_this-final0.ckpt`.
- **0.2.3.2**: carátula, álbum y año salen siempre del mismo disco (antes podía salir la portada del
  disco original con el nombre y el año del recopilatorio que traían las etiquetas).
- **0.2.3.1**: `dificultad_inicial` en `configuracion.txt`: la DD propia empieza con ese % de notas de cada
  frase (por ejemplo 60) y sube en cinco escalones hasta la completa.
- **0.2.3**: arreglado un corrimiento de toda la tablatura una semicorchea en algunas canciones (las notas
  del tiempo y del "y" caían en la "e" y la "a"). Las frases repetidas se reconocen aunque la
  transcripción no salga idéntica, así comparten progreso de verdad. Etiquetas de descargas de YouTube
  ("ArtistaVEVO", "(Videoclip)") limpiadas; espacios dobles en títulos; el álbum toma la grafía de la tienda.
- **0.2.2.1**: arreglada la DD propia: faltaban los niveles de referencia de cada frase, y el juego daba
  100 % de dominio y puntuaba solo sobre las notas del nivel más fácil.
- **0.2.2**: dificultad dinámica propia (`dificultad = propia`): cinco niveles iguales en toda la canción
  (una nota por compás, por medio compás, por tiempo, por corchea y completa), frases de 4 compases y
  las repetidas comparten progreso. Se puede volver a la de DLC Builder o quitarla (`dlcbuilder`, `ninguna`).
- **0.2.1.1**: artista y título desde las etiquetas ID3 del mp3 (si son válidas); la carpeta de salida
  se llama `Artista - Título` aunque el archivo se llame "01 - pista.mp3".
- **0.2.1**: diagnóstico completo de cada canción (`diagnostico.json` en su carpeta y una sección
  DIAGNÓSTICO al final del registro, también en los errores); el compilador comprueba el psarc
  recién hecho (niveles de DD, frases, notas). Arreglados: compases irregulares falsos al final,
  textos con acentos rotos ("EdiciÃ³n"), acentos perdidos en el nombre del psarc y carátulas de "EP"
  o "Imprescindibles".
- **0.2.0.2**: el *Tuning Pitch* solo cambia con desvíos de 30 cents o más (`umbral_cents`).
- **0.2.0.1**: la carátula, el álbum y el año salen del disco original y no de recopilatorios ni directos.
- **0.2.0**: compilación automática a `.psarc` (sin abrir DLC Builder) a una carpeta propia, configurable
  en `configuracion.txt`. Carátula, álbum y año desde iTunes/Deezer.
- **0.1.3.2**: registro general de cada tanda.
- **0.1.3.1**: minuto de cada compás irregular en el informe; textos al día.
- **0.1.3**: XML del arreglo y proyecto de DLC Builder generados directamente; ya no hace falta EOF.
- **0.1.2**: compases irregulares detectados compás a compás.
- **0.1.1.x**: afinación automática, referencia en cents, índice de púa (umbral 7 dB) y correcciones
  (tempos rápidos, falsos Eb/B, canciones que empiezan a mitad de compás).
- **0.1.0**: primera versión.

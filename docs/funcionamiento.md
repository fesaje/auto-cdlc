# Cómo funciona por dentro

Todo el proceso está en `cdlc_bajo.py`. Las cifras de este documento son las de la versión 0.3.

## 1. Preparación de la tanda

Se compara `entrada` con `salida`: una canción está hecha si su carpeta tiene el `.gp5`. Las pendientes
se agrupan por artista del disco y álbum, sacados de las etiquetas, o de una búsqueda en iTunes si no hay
álbum.

Los registros anteriores dicen qué canciones fallaron y cuánto tarda de media una canción. Las respuestas
de cada disco se guardan en `salida/ajustes_discos.json`.

## 2. Separación del bajo

Modelo MDX-Net **kuielab_b_bass**, que se ejecuta con
[audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (ONNX en CPU). Si lo separado
queda 35 dB o más por debajo de la mezcla, la canción no tiene bajo y se salta.

## 3. Pulso, tiempo 1 y compás

- **Pulsos**: red recurrente de [madmom](https://github.com/CPJKU/madmom) + modelo DBN, con tempo entre
  60 y 180 BPM. En `vendor/` va una versión de madmom 100 % Python, verificada contra la original, para
  no tener que compilar nada en Windows.
- **Tiempo 1**: [Beat This!](https://github.com/CPJKU/beat_this) (CPJKU). Se usa siempre que cuente el
  mismo pulso que madmom, o la mitad.
  - En canciones ternarias, Beat This! cuenta corcheas y su tiempo 1 también vale.
  - Si no hay ninguna de estas coincidencias, se usa la red de compases de madmom.
  - Si madmom salta de tempo (más del 3 % de pulsos fuera de sitio), se usan los pulsos de Beat This!.
- **Reparación**: los huecos de 2–4 pulsos se rellenan y los pulsos dobles se quitan.
- **Compás**: un Viterbi compás a compás con compás de base 4/4 o 3/4. Se queda el de mayor
  verosimilitud y admite compases sueltos de 2 a 6 tiempos con probabilidad baja. Los últimos compases
  se fuerzan al compás de base, porque en los finales los pulsos son poco fiables.

## 4. Notas

- **Ataques**: `librosa`. Para el ritmo se usa el pico del ataque menos el retroceso típico de la canción,
  no el inicio "retrocedido", que a veces cae muy atrás.
- **Altura**: primero pYIN, y en las dudas una CQT con suma de armónicos. Después
  [CREPE](https://github.com/maxrmorrison/torchcrepe) (modelo *tiny*):
  - el audio se le pasa una octava más alto, porque CREPE falla en los graves del bajo;
  - cuando CREPE y pYIN discrepan uno o dos semitonos, gana la nota que pertenece a la escala de la
    propia canción (así se respetan los modos).
- **Notas repetidas**: la cuerda sigue sonando, así que dos golpes seguidos a la misma nota parecen uno.
  Se buscan subidas rápidas de energía por debajo de 400 Hz que vengan tras una caída y estén cerca del
  pico de la nota, y se corta ahí.

## 5. Cuantización, afinación y digitación

- **Cuantización**: a semicorcheas. El desfase entre ataque y pulso se busca puntuando la alineación con
  semicorcheas, corcheas y negras, en una ventana física acotada.
- **Afinación**: se elige la que da cabida a las notas graves repetidas (E estándar hasta B estándar,
  incluidas las Drop).
- **Digitación**: programación dinámica sobre cuerda y traste que minimiza los saltos de mano.
  Después se calculan las posiciones de mano (anclas).

## 6. Dificultad dinámica

Cada nota recibe un nivel rítmico: 0 si es la primera del compás, 1 si es la de medio compás, 2 la del
tiempo, 3 la de la corchea y 4 el resto.

Las frases son de 4 compases (8 si la canción es muy larga). El corte de las frases se desplaza de 0 a 3
compases para encontrar más repeticiones.

Para cada frase se generan versiones de más fácil a completa. Cada paso rítmico entra primero en los
compases impares y luego en todos, como en el DDC de la comunidad, hasta 10 niveles.

Las frases repetidas se reconocen con una semicorchea de margen y comparten nombre, así Rocksmith suma su
progreso. Cada repetición lleva sus *heroLevels* (fácil, medio y difícil), sin los que el juego daría el
100 % desde el principio.

## 7. Tono, letra y arreglo simplificado

- **Tono**: base de tonos oficiales de DLC Builder ([iminashi/tones](https://github.com/iminashi/tones)).
  Se busca primero la canción, luego el artista y si no, uno de los tonos de referencia.
- **Letra**: [LRCLIB](https://lrclib.net), solo con la misma duración (±2 s). Las palabras se reparten
  dentro de cada línea y los caracteres que no tiene la fuente de Rocksmith se sustituyen por otros
  parecidos.
- **Arreglo simplificado**: las notas hasta el nivel rítmico elegido, mantenidas hasta la siguiente, y
  con su propia dificultad dinámica. Va marcado como arreglo alternativo.

## 8. Proyecto y compilación

Se escribe:

- el XML de cada arreglo en formato Rocksmith;
- el proyecto `.rs2dlc` de DLC Builder, sobre el que se repiten las comprobaciones de DLC Builder.

Lo compila **cdlc-pack** (`herramientas/cdlc-pack/codigo`), una pequeña aplicación de consola hecha con
las librerías de DLC Builder, [Rocksmith2014.NET](https://github.com/iminashi/Rocksmith2014.NET) de
iminashi (licencia MIT):

1. convierte el audio con Wwise;
2. empaqueta el `.psarc` con los mismos ajustes que el *Build Release* de DLC Builder;
3. reabre el paquete para verificar lo que ha quedado dentro (niveles, frases, notas, letra).

## Banco de pruebas

En `pruebas/` hay un generador de canciones sintéticas con la solución conocida y un evaluador. El
generador hace bajo, batería y acompañamiento, con compases irregulares, síncopas, notas repetidas y
compases de 3/4. El evaluador mide, frente a esa solución:

- F1 de ataques;
- notas repetidas recuperadas;
- notas con la altura correcta;
- F1 de pulsos y de tiempos 1.

```
uv run python pruebas/sintetico.py CARPETA        # genera los casos
uv run python pruebas/evaluar.py CARPETA todo      # los evalúa
```

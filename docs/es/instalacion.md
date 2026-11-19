# Instalación

[English](../en/installation.md) | **Español**

Se hace una sola vez y lleva unos 15 minutos, casi todo descargas.

## Requisitos

- **Windows 10 u 11 de 64 bits**, con unos 3 GB libres.
- **Rocksmith 2014 Remastered** (PC, Steam) y un cable de Rocksmith para el bajo.
- Conexión a internet durante la instalación. Después solo hace falta para carátulas, tonos oficiales y
  letras.

No hace falta instalar Python, ffmpeg ni .NET: el instalador se encarga de todo.

## 1. Programas que necesita el juego y el compilador

### CDLC Enabler (para que Rocksmith cargue canciones propias)

Sin él, el juego ignora los `.psarc` que no son oficiales.

1. Descárgalo de CustomsForge: <https://ignition4.customsforge.com/tools/cdlcenabler>
2. Ejecuta el instalador como administrador y pulsa la opción para desbloquear CDLC.

Instala un archivo `D3DX9_42.dll` en la carpeta de Rocksmith. Si el antivirus lo borra, añade una
excepción para esa carpeta.

### Wwise (convierte el audio al formato de Rocksmith)

Es el mismo que usa DLC Builder.

1. Descarga el instalador desde <https://ignition4.customsforge.com/tools/wwise>
2. Instala la versión 2019, 2021, 2022 o 2023, con las opciones por defecto.

auto-cdlc lo busca solo en `Archivos de programa\Audiokinetic`. Si lo instalas en otro sitio, pon la ruta
de `WwiseConsole.exe` en `configuracion.txt` (clave `wwise`).

## 2. auto-cdlc

1. Descarga **`auto-cdlc-<versión>-windows.zip`** de la
   [última versión](https://github.com/fesaje/auto-cdlc/releases/latest).
2. Descomprímelo en una carpeta tuya, por ejemplo `Documentos\auto-cdlc`. Mejor que no sea
   `Archivos de programa`, porque el programa escribe en su propia carpeta.
3. Haz doble clic en **`instalar.bat`**. Primero pregunta el idioma (español o inglés) y después hace
   cuatro cosas:
   1. instala `uv`, un gestor de Python que no toca el Python de tu sistema;
   2. prepara Python 3.13 y las librerías (alrededor de 1 GB la primera vez);
   3. comprueba que está `cdlc-pack`, el compilador de `.psarc`, y lo descarga si falta;
   4. comprueba si está Wwise. Si encuentra la carpeta `dlc` de Rocksmith en Steam, te ofrece dejar ahí
      los `.psarc` directamente.

> Si clonas el repositorio con git en vez de bajar el zip, `instalar.bat` descarga `cdlc-pack` de la
> última versión publicada.

## 3. Primera prueba

1. Copia un mp3 en la carpeta `entrada`.
2. Haz doble clic en **`procesar.bat`**, contesta a las preguntas (Intro deja el valor por defecto) y
   espera.
3. La primera canción tarda más, porque descarga:
   - el modelo de separación del bajo (unos 30 MB);
   - el de pulso, Beat This! (unos 80 MB);
   - la base de tonos oficiales (unos 8 MB).
4. Cuando acabe, el `.psarc` estará en la carpeta `psarc`, o en la `dlc` de Rocksmith si lo
   configuraste. Abre Rocksmith y búscala en *Learn a Song*.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `instalar.bat` falla al instalar uv | Instálalo a mano desde <https://docs.astral.sh/uv/> y vuelve a ejecutar `instalar.bat`. |
| "No encuentro uv" al procesar | Cierra la ventana y vuelve a abrir `procesar.bat`. Si sigue, ejecuta otra vez `instalar.bat`. |
| El informe dice "sin psarc … Wwise" | No encuentra Wwise: instálalo o pon su ruta en `configuracion.txt`. Mientras, puedes compilar a mano con DLC Builder (ver [uso](uso.md#compilar-o-retocar-a-mano)). |
| La canción no aparece en el juego | Comprueba que el `.psarc` está en la carpeta `dlc` de Rocksmith y que el CDLC Enabler está instalado. |
| El antivirus avisa | Suele ser por el CDLC Enabler o por `cdlc-pack.exe` (un ejecutable sin firmar). Añade una excepción para esas carpetas. |

Si nada de esto lo arregla, abre una [incidencia](https://github.com/fesaje/auto-cdlc/issues) con una
captura de la ventana.

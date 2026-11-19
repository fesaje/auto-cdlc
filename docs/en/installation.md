# Installation

**English** | [Español](../es/instalacion.md)

You only do this once. It takes about 15 minutes, mostly downloads.

## Requirements

- **Windows 10 or 11, 64-bit**, with about 3 GB of free space.
- **Rocksmith 2014 Remastered** (PC, Steam) and a Rocksmith cable for your bass.
- An internet connection during installation. After that it is only needed for album art, official
  tones and lyrics.

You don't need to install Python, ffmpeg or .NET: the installer takes care of everything.

## 1. What the game and the builder need

### CDLC Enabler (lets Rocksmith load custom songs)

Without it the game ignores any `.psarc` that isn't official.

1. Download it from CustomsForge: <https://ignition4.customsforge.com/tools/cdlcenabler>
2. Run the installer as administrator and click the option to unlock CDLC.

It places a `D3DX9_42.dll` file in the Rocksmith folder. If your antivirus deletes it, add an exception
for that folder.

### Wwise (converts audio to Rocksmith's format)

It's the same one DLC Builder uses.

1. Download the installer from <https://ignition4.customsforge.com/tools/wwise>
2. Install version 2019, 2021, 2022 or 2023 with the default options.

auto-cdlc looks for it in `Program Files\Audiokinetic`. If you install it elsewhere, put the path to
`WwiseConsole.exe` in `configuracion.txt` (key `wwise`).

## 2. auto-cdlc

1. Download **`auto-cdlc-<version>-windows.zip`** from the
   [latest release](https://github.com/fesaje/auto-cdlc/releases/latest).
2. Unzip it into one of your own folders, for example `Documents\auto-cdlc`. Better not under
   `Program Files`, because the program writes into its own folder.
3. Double-click **`instalar.bat`**. It first asks for the language (Spanish or English) and then does four
   things:
   1. installs `uv`, a Python manager that doesn't touch your system's Python;
   2. sets up Python 3.13 and the libraries (about 1 GB the first time);
   3. checks that `cdlc-pack`, the `.psarc` builder, is there, and downloads it if missing;
   4. checks for Wwise. If it finds Rocksmith's `dlc` folder in Steam, it offers to save the `.psarc`
      files straight there.

> If you clone the repository with git instead of downloading the zip, `instalar.bat` downloads
> `cdlc-pack` from the latest release.

## 3. First test

1. Copy an mp3 into the `entrada` folder.
2. Double-click **`procesar.bat`**, answer the questions (Enter keeps the default) and wait.
3. The first song takes longer because it downloads:
   - the bass separation model (about 30 MB);
   - the Beat This! beat model (about 80 MB);
   - the database of official tones (about 8 MB).
4. When it's done, the `.psarc` is in the `psarc` folder, or in Rocksmith's `dlc` folder if you set that
   up. Open Rocksmith and look for the song in *Learn a Song*.

## Common problems

| Symptom | Fix |
|---|---|
| `instalar.bat` fails installing uv | Install it manually from <https://docs.astral.sh/uv/> and run `instalar.bat` again. |
| "uv not found" when processing | Close the window and open `procesar.bat` again. If it persists, run `instalar.bat` again. |
| The report says "sin psarc … Wwise" | Wwise wasn't found: install it or put its path in `configuracion.txt`. Meanwhile you can build by hand with DLC Builder (see [usage](usage.md#building-or-editing-by-hand)). |
| The song doesn't show up in the game | Check that the `.psarc` is in Rocksmith's `dlc` folder and that the CDLC Enabler is installed. |
| The antivirus complains | It's usually about the CDLC Enabler or `cdlc-pack.exe` (an unsigned executable). Add an exception for those folders. |

If none of this helps, open an [issue](https://github.com/fesaje/auto-cdlc/issues) with a screenshot of
the window.

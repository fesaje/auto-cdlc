/// cdlc-pack: compila un proyecto de DLC Builder (.rs2dlc) a .psarc sin abrir DLC Builder.
/// Usa las mismas librerías y los mismos valores por defecto que DLC Builder ("Build Release").
module CdlcPack.Program

open System
open System.IO
open Rocksmith2014.Audio
open Rocksmith2014.Common
open Rocksmith2014.DD
open Rocksmith2014.DLCProject
open Rocksmith2014.DLCProject.PackageBuilder
open Rocksmith2014.PSARC
open Rocksmith2014.SNG

type Opciones =
    { Proyecto: string
      Salida: string
      Wwise: string option
      Plataformas: Platform list
      GenerarDD: bool
      Autor: string }

let uso () =
    eprintfn "Uso: cdlc-pack <proyecto.rs2dlc> [--salida CARPETA] [--wwise RUTA\\WwiseConsole.exe]"
    eprintfn "                 [--mac] [--sin-dd] [--autor NOMBRE]"
    eprintfn "Sin --salida, el .psarc se deja junto al proyecto."

let rec leerArgs (args: string list) (o: Opciones) =
    match args with
    | [] -> Ok o
    | "--salida" :: v :: resto -> leerArgs resto { o with Salida = v }
    | "--wwise" :: v :: resto -> leerArgs resto { o with Wwise = Some v }
    | "--mac" :: resto -> leerArgs resto { o with Plataformas = [ PC; Mac ] }
    | "--sin-dd" :: resto -> leerArgs resto { o with GenerarDD = false }
    | "--autor" :: v :: resto -> leerArgs resto { o with Autor = v }
    | v :: resto when not (v.StartsWith "--") && o.Proyecto = "" -> leerArgs resto { o with Proyecto = v }
    | v :: _ -> Error $"Argumento no reconocido: {v}"

let compilar (o: Opciones) =
    async {
        let rutaProyecto = Path.GetFullPath(o.Proyecto)
        let! proyecto = DLCProject.load rutaProyecto |> Async.AwaitTask
        let proyecto = DLCProject.updateToneInfo proyecto

        // 1. Audio: OGG/WAV -> WEM con Wwise (sólo si hace falta, igual que DLC Builder)
        let pendientes = DLCProject.getFilesThatNeedConverting (TimeSpan.FromSeconds 3.0) proyecto |> Seq.toList
        for audio in pendientes do
            printfn "Convirtiendo audio con Wwise: %s" (Path.GetFileName audio)
            let! _ = Wwise.convertToWem o.Wwise audio
            ()

        // 2. Nombre del paquete como en "Build Release": Artista_Titulo_v1
        let nombre =
            let artista = proyecto.ArtistName.SortValue |> Option.ofString |> Option.defaultValue proyecto.ArtistName.Value
            let titulo = proyecto.Title.SortValue |> Option.ofString |> Option.defaultValue proyecto.Title.Value
            sprintf "%s_%s_v%s" artista titulo (proyecto.Version.Replace('.', '_')) |> StringValidator.fileName

        let carpeta =
            if String.IsNullOrWhiteSpace o.Salida then Path.GetDirectoryName rutaProyecto
            else Directory.CreateDirectory(o.Salida).FullName

        // 3. Configuración por defecto de DLC Builder
        let config =
            { Platforms = o.Plataformas
              BuilderVersion = "cdlc-pack (DLC Builder libs)"
              Author = proyecto.Author |> Option.defaultValue o.Autor
              AppId = AppId.CherubRock
              GenerateDD = o.GenerarDD
              ForcePhraseCreation = false
              DDConfig = { PhraseSearchThreshold = Some 80; LevelCountGeneration = LevelCountGeneration.Simple }
              ApplyImprovements = true
              SaveDebugFiles = false
              AudioConversionTask = async { return () }
              IdResetConfig = None
              ProgressReporter = None }

        printfn "Compilando %s ..." nombre
        let! rutas, _ = buildPackages (WithoutPlatformOrExtension(Path.Combine(carpeta, nombre))) config proyecto
        for r in rutas do
            printfn "PSARC: %s" r
        // Verificación: reabrir el paquete de PC y leer el arreglo compilado (SNG)
        for r in rutas |> Array.filter (fun r -> r.EndsWith "_p.psarc") do
            try
                use psarc = PSARC.OpenFile r
                printfn "VERIF archivos=%d" psarc.Manifest.Length
                for sngName in psarc.Manifest |> Seq.filter (fun f -> f.EndsWith ".sng") do
                    let tmp = Path.GetTempFileName()
                    do! psarc.InflateFile(sngName, tmp) |> Async.AwaitTask
                    let! sng = SNG.readPackedFile tmp PC
                    File.Delete tmp
                    if sng.Levels.Length = 0 then
                        printfn "VERIF %s letra=%d" (Path.GetFileNameWithoutExtension sngName) sng.Vocals.Length
                    else
                        let notasMax =
                            sng.PhraseIterations
                            |> Array.sumBy (fun pi ->
                                let lvl = sng.Levels[sng.Phrases[pi.PhraseId].MaxDifficulty]
                                lvl.Notes |> Array.filter (fun n -> n.Time >= pi.StartTime && n.Time < pi.EndTime) |> Array.length)
                        let conHeroe = sng.PhraseIterations |> Array.filter (fun pi -> pi.Difficulty[2] > 0) |> Array.length
                        printfn "VERIF %s niveles=%d frases=%d secciones=%d notas_max=%d notas_nivel0=%d notas_puntuables=%.0f iteraciones_con_dd=%d/%d afinacion=%A duracion=%.1f"
                            (Path.GetFileNameWithoutExtension sngName) sng.Levels.Length sng.Phrases.Length
                            sng.Sections.Length notasMax sng.Levels[0].Notes.Length sng.MetaData.MaxNotesAndChords
                            conHeroe sng.PhraseIterations.Length sng.MetaData.Tuning sng.MetaData.SongLength
            with ex ->
                printfn "VERIF error=%s" ex.Message
        return rutas
    }

[<EntryPoint>]
let main argv =
    Console.OutputEncoding <- Text.Encoding.UTF8
    let porDefecto =
        { Proyecto = ""; Salida = ""; Wwise = None; Plataformas = [ PC ]; GenerarDD = true; Autor = "cdlc-bajo" }
    match leerArgs (List.ofArray argv) porDefecto with
    | Error e ->
        eprintfn "%s" e; uso (); 2
    | Ok o when o.Proyecto = "" || not (File.Exists o.Proyecto) ->
        eprintfn "No encuentro el proyecto: '%s'" o.Proyecto; uso (); 2
    | Ok o ->
        try
            compilar o |> Async.RunSynchronously |> ignore
            0
        with ex ->
            let rec raiz (e: exn) = if isNull e.InnerException then e else raiz e.InnerException
            eprintfn "ERROR: %s" (raiz ex).Message
            1

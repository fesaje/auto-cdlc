"""
ui.py - Text interface for auto-cdlc (launched by auto-cdlc.bat).

Three tabs:
  Songs     processed songs with their reliability, tempo, tuning, tone...; retouch them (tone, pick,
            scroll speed, simplified arrangement, starting difficulty) and rebuild the .psarc in seconds,
            open their folder or listen to the click / A-B tracks.
  Batch     pick songs from 'input', choose the settings and process them, watching the progress.
  Settings  edit config.txt with proper fields.

The heavy lifting is done by auto_cdlc.py: batches run as a separate process (the same as
process.bat --no-questions), retouching calls auto_cdlc.regenerar in a background thread.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (Button, ContentSwitcher, DataTable, Footer, Header, Input, Label, ProgressBar,
                             RichLog, Select, Static, Switch, TabbedContent, TabPane, Tree)

import auto_cdlc as c

CONF = c.entorno_basico()        # language first: the labels below depend on it
T = c.T
TONOS = ["auto", "clean", "clean_pick", "overdrive", "distortion", "fuzz"]
SIMPLE = {"no": None, "bar": 0, "half": 1, "beat": 2, "eighth": 3}
NOMBRE_SIMPLE = {"no": ("no", "no"), "bar": ("bar (1 nota por compás)", "bar (1 note per bar)"),
                 "half": ("half (1 nota cada 2 pulsos)", "half (1 note every 2 beats)"),
                 "beat": ("beat (1 nota por pulso)", "beat (1 note per beat)"),
                 "eighth": ("eighth (1 nota por corchea)", "eighth (1 note per eighth)")}
SIMPLE_INV = {v: k for k, v in SIMPLE.items()}
NIVEL = {"alta": ("high", "green"), "media": ("medium", "yellow"), "baja": ("low", "red")}


def abrir(ruta):
    """Opens a file or folder with the system's default program."""
    try:
        if os.name == "nt":
            os.startfile(str(ruta))                                  # noqa: S606
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(ruta)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def canciones(salida):
    """Processed songs in the output folder, newest first, with what the songs table shows."""
    filas = []
    for carpeta in Path(salida).iterdir() if Path(salida).is_dir() else []:
        if not carpeta.is_dir():
            continue
        info = c.leer_cancion(carpeta)
        if info is None:
            continue
        d = info["diag"]
        b = d.get("beats", {})
        pr = info["datos"]
        campo = lambda k: ((pr.get(k) or {}).get("Value") or "").strip()
        filas.append({
            "carpeta": carpeta, "info": info,
            "nombre": carpeta.name,
            "artista": campo("ArtistName") or carpeta.name.split(" - ")[0],
            "album": campo("AlbumName"),
            "titulo": campo("Title") or carpeta.name.split(" - ", 1)[-1],
            "fiabilidad": (d.get("fiabilidad") or {}).get("nivel"),
            "motivos": (d.get("fiabilidad") or {}).get("motivos") or [],
            "bpm": b.get("tempo_mediano"),
            "metro": b.get("compas_de_base"),
            "afinacion": (d.get("afinacion") or {}).get("elegida"),
            "tono": info["tono"],
            "pua": info["pua"],
            "velocidad": info["velocidad"],
            "simple": info["simple"],
            "fecha": d.get("fecha") or "",
            "completo": info["completo"],
        })
    return filas


# Songs table columns: (key, Spanish label, English label). The key is also what the column sorts by.
COLUMNAS = [("artista", "Artista", "Artist"), ("album", "Álbum", "Album"), ("titulo", "Canción", "Song"),
            ("fiabilidad", "Fiab.", "Rel."), ("bpm", "BPM", "BPM"), ("metro", "Compás", "Time"),
            ("afinacion", "Afinación", "Tuning"), ("tono", "Tono", "Tone"), ("pua", "Púa", "Pick"),
            ("velocidad", "Scroll", "Scroll"), ("simple", "Simpl.", "Simple"), ("fecha", "Fecha", "Date")]
ANCHO = {"artista": 22, "album": 22, "titulo": 28}   # long names are cut so the other columns stay visible
ORDEN_FIABILIDAD = {"alta": 0, "media": 1, "baja": 2}


def normal(texto):
    """Lowercase without accents, for sorting and filtering ("Álbum" == "album")."""
    import unicodedata
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower().strip()


def clave_orden(col):
    """Sort key for a column: text case- and accent-insensitive, numbers as numbers, blanks last."""
    def k(f):
        v = f.get(col)
        if col == "fiabilidad":
            v = ORDEN_FIABILIDAD.get(v, 9)
        elif col == "tono":
            v = (v or "").split(" (")[0]
        elif col == "simple":
            v = -1 if v is None else (v if isinstance(v, int) else 9)
        if v is None or v == "":
            return (1, "")
        if isinstance(v, (int, float, bool)):
            return (0, float(v))
        return (0, normal(str(v)))
    return k


def coincide(f, palabras):
    """True if every word of the filter appears in the song's artist, album, title, tuning or tone."""
    texto = normal(" ".join(str(f.get(k) or "") for k in ("artista", "album", "titulo", "afinacion", "tono")))
    return all(p in texto for p in palabras)


# ---------------------------------------------------------------- batch: songs in input as a tree
CARPETAS_HECHAS = {"processed", "discarded", "procesadas", "descartadas"}   # mover_entradas() puts them there
ESTADOS = {"nueva": ("nueva", "new"), "procesada": ("procesada", "processed"),
           "fallo": ("falló antes", "failed before"), "sin_bajo": ("sin bajo", "no bass")}
ESTADOS_PLURAL = {"nueva": ("nuevas", "new"), "procesada": ("procesadas", "processed"),
                  "fallo": ("fallaron antes", "failed before"), "sin_bajo": ("sin bajo", "no bass")}


def archivos_input():
    """Audio files in input and its subfolders, leaving out the ones already moved to processed/discarded."""
    entrada = c.AQUI / "input"
    if not entrada.is_dir():
        return []
    return sorted(p for p in entrada.rglob("*") if p.is_file() and p.suffix.lower() in c.EXTENSIONES
                  and not (set(x.lower() for x in p.relative_to(entrada).parts[:-1]) & CARPETAS_HECHAS))


def duracion_audio(p):
    try:
        from mutagen import File
        return float(File(str(p)).info.length)
    except Exception:
        return None


class ArbolTanda(Tree):
    """Artist > album > song, with a tick box on each line. Space ticks the line under the cursor (a whole
    album or artist at once); the other keys act on the whole list."""
    BINDINGS = [
        Binding("space", "marcar", T("Marcar", "Tick")),
        Binding("t", "app.marcar_todas", T("Todas", "All")),
        Binding("n", "app.marcar_ninguna", T("Ninguna", "None")),
        Binding("v", "app.marcar_nuevas", T("Solo nuevas", "Only new")),
        Binding("i", "app.marcar_invertir", T("Invertir", "Invert")),
        Binding("m", "app.ver_marcadas", T("Ver solo marcadas", "Show only ticked")),
    ]

    def action_marcar(self):
        if self.cursor_node is not None:
            self.app.marcar_nodo(self.cursor_node)


# ---------------------------------------------------------------- Rocksmith folder chooser
class ElegirDlc(ModalScreen):
    """Lists the Rocksmith installs found and returns the chosen dlc folder ("" = auto-cdlc's psarc folder)."""
    BINDINGS = [Binding("escape", "cancelar", T("Cancelar", "Cancel"))]

    def __init__(self, dlcs):
        super().__init__()
        self.dlcs = dlcs

    def compose(self) -> ComposeResult:
        from textual.widgets import OptionList
        opciones = [T(f"Carpeta psarc de auto-cdlc ({c.AQUI / 'psarc'})",
                      f"auto-cdlc's psarc folder ({c.AQUI / 'psarc'})")]
        for d in self.dlcs:
            n = len(list(d.glob("*.psarc"))) if d.is_dir() else 0
            opciones.append(f"{d}  ({n} .psarc)")
        with Vertical(id="dialogo"):
            yield Label(T("¿Dónde dejo los .psarc? Con una carpeta dlc, las canciones aparecen directamente en el juego.",
                          "Where should the .psarc files go? With a dlc folder, the songs show up straight in the game.")
                        if self.dlcs else
                        T("No he encontrado ninguna instalación de Rocksmith.", "No Rocksmith install found."))
            yield OptionList(*opciones, id="dlcs")

    def on_option_list_option_selected(self, ev):
        self.dismiss("" if ev.option_index == 0 else str(self.dlcs[ev.option_index - 1]))

    def action_cancelar(self):
        self.dismiss(None)


# ---------------------------------------------------------------- retouch dialog
class Retocar(ModalScreen):
    """Dialog to change a song's settings and rebuild it."""
    BINDINGS = [Binding("escape", "cancelar", T("Cancelar", "Cancel"))]

    def __init__(self, fila):
        super().__init__()
        self.fila = fila

    def compose(self) -> ComposeResult:
        f = self.fila
        mantener = T("(no cambiar)", "(keep)")
        with Vertical(id="dialogo"):
            yield Label(f"[b]{f['nombre']}[/b]")
            yield Label(T("Tono", "Tone") + f"  ({T('ahora', 'now')}: {f['tono'] or '?'})")
            yield Select([(mantener, "")] + [(t, t) for t in TONOS], value="", id="tono", allow_blank=False)
            yield Label(T("Púa", "Pick"))
            yield Select([(T("con púa", "pick"), "yes"), (T("con dedos", "fingers"), "no")],
                         value="yes" if f["pua"] else "no", id="pua", allow_blank=False)
            yield Label(T("Velocidad de scroll (0.5-5)", "Scroll speed (0.5-5)"))
            yield Input(str(f["velocidad"] or 1.3), id="velocidad")
            completo = f["completo"]
            aviso = "" if completo else T("  (procesada con una versión anterior: vuelve a procesarla para cambiarlo)",
                                          "  (processed with an older version: process it again to change this)")
            yield Label(T("Arreglo simplificado", "Simplified arrangement") + aviso)
            actual = SIMPLE_INV.get(f["simple"], "no") if completo else ""
            yield Select([(k, k) for k in SIMPLE] + ([] if completo else [(mantener, "")]), value=actual,
                         id="simple", allow_blank=False, disabled=not completo)
            dd = (f["info"]["dd_inicial"] if completo else None)
            yield Label(T("Dificultad inicial (%)", "Starting difficulty (%)") + aviso)
            yield Input("" if dd is None else f"{dd:.0f}", id="dd", disabled=not completo)
            with Horizontal(id="botones"):
                yield Button(T("Aplicar y crear .psarc", "Apply and build .psarc"), variant="primary", id="aplicar")
                yield Button(T("Cancelar", "Cancel"), id="cancelar")

    def action_cancelar(self):
        self.dismiss(None)

    @on(Button.Pressed, "#cancelar")
    def _cancelar(self):
        self.dismiss(None)

    @on(Button.Pressed, "#aplicar")
    def _aplicar(self):
        f = self.fila
        cambios = {}
        tono = self.query_one("#tono", Select).value
        if tono:
            cambios["tono"] = tono
        pua = self.query_one("#pua", Select).value == "yes"
        if pua != f["pua"]:
            cambios["pua"] = pua
        try:
            v = float(self.query_one("#velocidad", Input).value.replace(",", "."))
            if f["velocidad"] is None or abs(v - float(f["velocidad"])) > 1e-6:
                cambios["velocidad"] = v
        except ValueError:
            self.notify(T("La velocidad tiene que ser un número", "The speed must be a number"), severity="error")
            return
        if f["completo"]:
            s = SIMPLE[self.query_one("#simple", Select).value]
            if s != f["simple"]:
                cambios["simple"] = s
            txt = self.query_one("#dd", Input).value.replace("%", "").replace(",", ".").strip()
            if txt:
                try:
                    dd = min(95.0, max(0.0, float(txt)))
                except ValueError:
                    self.notify(T("La dificultad tiene que ser un número", "The difficulty must be a number"),
                                severity="error")
                    return
                if f["info"]["dd_inicial"] is None or abs(dd - float(f["info"]["dd_inicial"])) > 1e-6:
                    cambios["dd_inicial"] = dd
        self.dismiss(cambios)


# ---------------------------------------------------------------- settings fields
CAMPOS = [  # key, kind, choices, label (es, en)
    ("language", "select", ["es", "en"], ("Idioma", "Language")),
    ("psarc_folder", "text", None, ("Carpeta de los .psarc (vacío = carpeta psarc)", "Folder for the .psarc files (empty = psarc folder)")),
    ("build_psarc", "bool", None, ("Compilar los .psarc", "Build the .psarc files")),
    ("online", "bool", None, ("Buscar en internet (carátulas, tonos, letras)", "Go online (album art, tones, lyrics)")),
    ("wwise", "text", None, ("Wwise (carpeta o WwiseConsole.exe; vacío = buscarlo solo)", "Wwise (folder or WwiseConsole.exe; empty = find it)")),
    ("difficulty", "select", ["own", "dlcbuilder", "none"], ("Dificultad dinámica", "Dynamic difficulty")),
    ("start_difficulty", "text", None, ("Dificultad inicial (%)", "Starting difficulty (%)")),
    ("bass_tone", "select", TONOS, ("Tono del bajo por defecto", "Default bass tone")),
    ("scroll_speed", "text", None, ("Velocidad de scroll (número o 'auto 1.3')", "Scroll speed (number or 'auto 1.3')")),
    ("simple_arrangement", "select", list(SIMPLE), ("Arreglo simplificado", "Simplified arrangement")),
    ("lyrics", "bool", None, ("Letra en pantalla", "On-screen lyrics")),
    ("split_repeated", "bool", None, ("Partir notas repetidas", "Split repeated notes")),
    ("crepe_pitch", "bool", None, ("Tono de las notas con CREPE", "Note pitch with CREPE")),
    ("separation_model", "select", ["mdx", "demucs"], ("Separación del bajo (modelo)", "Bass separation (model)")),
    ("cents_threshold", "text", None, ("Umbral de Tuning Pitch (cents)", "Tuning Pitch threshold (cents)")),
    ("question_timeout", "text", None, ("Espera de las preguntas (s)", "Question timeout (s)")),
    ("check_updates", "bool", None, ("Buscar actualizaciones", "Check for updates")),
    ("send_results", "select", ["ask", "yes", "no"], ("Enviar resultados anónimos", "Send anonymous results")),
]
SI = ("yes", "si", "sí", "true", "1", "on")


# ---------------------------------------------------------------- the app
class AutoCdlc(App):
    TITLE = "auto-cdlc"
    CSS = """
    TabPane > Vertical { height: 1fr; }
    #canciones-panel { height: 1fr; }
    #lista { width: 3fr; }
    #filtro { margin: 0 0 0 0; }
    #tabla { height: 1fr; }
    #detalle { width: 2fr; border-left: solid $primary; padding: 0 1; }
    #registro { height: 1fr; border-top: solid $primary; }
    #tanda-cuerpo { height: 1fr; }
    #tanda-lista { width: 3fr; }
    #tanda-botones { height: auto; margin: 1 0 0 0; }
    #tanda-botones Button { margin-right: 1; }
    #arbol { height: 1fr; margin-top: 1; }
    #tanda-ver { height: auto; margin-top: 1; }
    #tanda-filtro { width: 1fr; }
    #m-ver-marcadas { margin-left: 1; }
    #m-ver-marcadas.activo { background: $accent; color: $text; }
    #tanda-derecha { width: 2fr; border-left: solid $primary; padding: 0 1; }
    #tanda-opciones Label { margin-top: 1; }
    #tanda-opciones Select, #tanda-opciones Input { width: 100%; }
    .titulo { text-style: bold; color: $accent; }
    .fila-switch { height: auto; margin-top: 1; }
    .fila-switch Label { margin: 1 0 0 1; }
    #tanda-progreso { height: 1fr; }
    #p-total { margin: 1 0; }
    #tanda-log { height: 1fr; border-top: solid $primary; }
    #tanda-pie { height: auto; border-top: solid $primary; padding: 0 1; }
    #tanda-resumen { width: 1fr; padding: 1 0; }
    #tanda-pie Button { margin-left: 1; }
    #ajustes Horizontal { height: auto; }
    #ajustes Label { width: 50; padding: 1 1 0 0; }
    #ajustes Input, #ajustes Select { width: 1fr; }
    Retocar, ElegirDlc { align: center middle; }
    #dlcs { height: auto; max-height: 12; margin-top: 1; }
    ElegirDlc #dialogo { width: 90%; max-width: 120; }
    ElegirDlc Label { width: 100%; }
    #cfg-buscar-dlc { margin-left: 1; }
    #dialogo { width: 70; height: auto; border: thick $primary; background: $surface; padding: 1 2; }
    #botones { height: auto; margin-top: 1; }
    #botones Button { margin-right: 2; }
    """
    BINDINGS = [
        Binding("q", "quit", T("Salir", "Quit")),
        Binding("e", "retocar", T("Retocar", "Retouch")),
        Binding("b", "reempaquetar", T("Crear .psarc", "Build .psarc")),
        Binding("o", "carpeta", T("Abrir carpeta", "Open folder")),
        Binding("c", "clics", T("Oír clics", "Play clicks")),
        Binding("a", "ab", T("Oír A/B", "Play A/B")),
        Binding("r", "refrescar", T("Refrescar", "Refresh")),
        Binding("slash", "filtrar", T("Filtrar", "Filter")),
        Binding("escape", "quitar_filtro", T("Quitar filtro", "Clear filter"), show=False),
    ]

    def __init__(self):
        super().__init__()
        self.conf = CONF
        self.salida = c.AQUI / "output"
        self.filas = []                  # songs shown, in table order
        self.todas = []                  # every processed song
        self.orden = [("artista", False), ("album", False), ("titulo", False)]   # (column, descending)
        self.proceso = None
        self.items, self.filtro_tanda, self.actual, self.tanda, self.hechas_tanda = [], None, None, {}, []
        self.terminada = False
        self.solo_marcadas = False
        c.log = self._log_hilo           # messages from auto_cdlc go to the log panel, not to the terminal
        self.sub_title = f"{c.VERSION}"

    # ----- layout
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tab-canciones"):
            with TabPane(T("Canciones", "Songs"), id="tab-canciones"):
                with Vertical():
                    with Horizontal(id="canciones-panel"):
                        with Vertical(id="lista"):
                            yield Input(placeholder=T("Filtrar: artista, álbum, canción, afinación, tono…  (tecla /)",
                                                      "Filter: artist, album, song, tuning, tone…  (key /)"),
                                        id="filtro")
                            yield DataTable(id="tabla", cursor_type="row", zebra_stripes=True)
                        yield VerticalScroll(Static(id="informe"), id="detalle")
                    yield RichLog(id="registro", wrap=True, markup=True, max_lines=500)
            with TabPane(T("Tanda", "Batch"), id="tab-tanda"):
                with Vertical():
                    with Horizontal(id="tanda-cuerpo"):
                        with Vertical(id="tanda-lista"):
                            yield Label(id="tanda-cabecera")
                            with Horizontal(id="tanda-botones"):
                                yield Button(T("Todas", "All"), id="m-todas", compact=True)
                                yield Button(T("Ninguna", "None"), id="m-ninguna", compact=True)
                                yield Button(T("Solo nuevas", "Only new"), id="m-nuevas", compact=True)
                                yield Button(T("Invertir", "Invert"), id="m-invertir", compact=True)
                            with Horizontal(id="tanda-ver"):
                                yield Input(placeholder=T("Filtrar: artista, álbum, canción…  (tecla /)",
                                                          "Filter: artist, album, song…  (key /)"), id="tanda-filtro",
                                            compact=True)
                                yield Button(T("Solo marcadas", "Only ticked"), id="m-ver-marcadas", compact=True)
                            yield ArbolTanda("input", id="arbol")
                        with ContentSwitcher(initial="tanda-opciones", id="tanda-derecha"):
                            with VerticalScroll(id="tanda-opciones"):
                                yield Label(T("OPCIONES DE LA TANDA", "BATCH OPTIONS"), classes="titulo")
                                yield Label(T("Tono del bajo", "Bass tone"))
                                yield Select([(T("el de cada disco / config", "each album's / config"), "")] +
                                             [(t, t) for t in TONOS], id="t-tono", allow_blank=False, value="")
                                yield Label(T("Púa", "Pick"))
                                yield Select([(T("la de cada disco / detectar", "each album's / detect"), ""),
                                              (T("con púa", "pick"), "yes"), (T("con dedos", "fingers"), "no")],
                                             id="t-pua", allow_blank=False, value="")
                                yield Label(T("Arreglo simplificado", "Simplified arrangement"))
                                yield Select([(T(*NOMBRE_SIMPLE[k]), k) for k in SIMPLE], id="t-simple",
                                             allow_blank=False, value="beat")
                                yield Label(T("Dificultad inicial (%)", "Starting difficulty (%)"))
                                yield Input(id="t-dd")
                                yield Label(T("[dim]0 = la canción empieza en el nivel más fácil[/dim]",
                                              "[dim]0 = the song starts at the easiest level[/dim]"))
                                with Horizontal(classes="fila-switch"):
                                    yield Switch(id="t-enviar", value=True)
                                    yield Label(T("Enviar resultados anónimos", "Send anonymous results"))
                            with Vertical(id="tanda-progreso"):
                                yield Label(T("PROGRESO", "PROGRESS"), classes="titulo")
                                yield Label(id="p-actual")
                                yield Label(id="p-paso")
                                yield ProgressBar(id="p-total", show_eta=False)
                                yield RichLog(id="tanda-log", wrap=True, max_lines=5000, markup=True)
                    with Horizontal(id="tanda-pie"):
                        yield Label(id="tanda-resumen")
                        yield Button(T("Ver en Canciones", "Show in Songs"), id="t-ver", disabled=True)
                        yield Button(T("▶ Empezar", "▶ Start"), variant="primary", id="t-empezar")
                        yield Button(T("■ Parar", "■ Stop"), variant="error", id="t-parar", disabled=True)
            with TabPane(T("Ajustes", "Settings"), id="tab-ajustes"):
                with VerticalScroll(id="ajustes"):
                    for clave, tipo, opciones, etiqueta in CAMPOS:
                        with Horizontal():
                            yield Label(T(*etiqueta) + f"  [dim]{clave}[/dim]")
                            if tipo == "bool":
                                yield Switch(id=f"cfg-{clave}")
                            elif tipo == "select":
                                yield Select([(o, o) for o in opciones], id=f"cfg-{clave}", allow_blank=True)
                            else:
                                yield Input(id=f"cfg-{clave}")
                            if clave == "psarc_folder":
                                yield Button(T("Buscar Rocksmith…", "Find Rocksmith…"), id="cfg-buscar-dlc")
                    yield Button(T("Guardar en config.txt", "Save to config.txt"), variant="primary", id="cfg-guardar")
        yield Footer()

    def on_mount(self):
        self.cargar_canciones()
        self.cargar_archivos()
        self.cargar_ajustes()
        self.query_one("#t-dd", Input).value = f"{float(self.conf.get('start_difficulty', 0) or 0):.0f}"
        s = c._traducir("simple_arrangement", self.conf.get("simple_arrangement", "beat"))[1].lower()
        if s in SIMPLE:
            self.query_one("#t-simple", Select).value = s
        envio = c._traducir("send_results", self.conf.get("send_results", "ask"))[1].lower()
        self.query_one("#t-enviar", Switch).value = envio != "no"
        if not c.COMPILAR:
            self.escribir(T("[yellow]Aviso: no se pueden crear .psarc (falta cdlc-pack o está desactivado); "
                            "se reescribirán solo los proyectos.[/yellow]",
                            "[yellow]Warning: .psarc files can't be built (cdlc-pack missing or disabled); "
                            "only the projects will be rewritten.[/yellow]"))
        elif c.COMPILAR and not c.WWISE:
            self.escribir(T("[yellow]Aviso: no encuentro Wwise; no se podrán crear .psarc.[/yellow]",
                            "[yellow]Warning: Wwise not found; .psarc files can't be built.[/yellow]"))

    # ----- log helpers
    def escribir(self, texto):
        self.query_one("#registro", RichLog).write(texto)

    def _log_hilo(self, msg):
        if threading.current_thread() is threading.main_thread():
            self.escribir(str(msg))
        else:
            self.call_from_thread(self.escribir, str(msg))

    # ----- songs tab
    def cargar_canciones(self):
        self.todas = canciones(self.salida)
        self.pintar_tabla()

    def pintar_tabla(self):
        """Fills the table with the songs that pass the filter, in the chosen order, keeping the selection."""
        t = self.query_one("#tabla", DataTable)
        antes = self.fila_actual()
        antes = antes["carpeta"] if antes else None
        palabras = normal(self.query_one("#filtro", Input).value).split()
        filas = [f for f in self.todas if coincide(f, palabras)]
        if self.filtro_tanda:                              # "Show in Songs" after a batch
            filas = [f for f in filas if normal(f["titulo"]) in self.filtro_tanda]
        for col, desc in reversed(self.orden):          # stable sorts: the first column in self.orden wins
            filas.sort(key=clave_orden(col), reverse=desc)
        self.filas = filas
        principal, desc = self.orden[0]
        t.clear(columns=True)
        for clave, es, en in COLUMNAS:
            nombre = T(es, en) + ((" ▼" if desc else " ▲") if clave == principal else "")
            t.add_column(nombre, key=clave, width=ANCHO.get(clave))
        for f in self.filas:
            nivel, color = NIVEL.get(f["fiabilidad"], ("?", "white"))
            nivel = T(f["fiabilidad"] or "?", nivel)
            t.add_row(f["artista"], f["album"], f["titulo"], f"[{color}]{nivel}[/{color}]",
                      f"{f['bpm']:.0f}" if f["bpm"] else "?", f["metro"] or "?",
                      c.afin_txt(f["afinacion"]) if f["afinacion"] else "?",
                      c.NOMBRE_PRESET.get((f["tono"] or "?").split(" (")[0], (f["tono"] or "?").split(" (")[0]),
                      T("sí", "yes") if f["pua"] else "no",
                      f"{f['velocidad']}" if f["velocidad"] else "?",
                      SIMPLE_INV.get(f["simple"], "?") if f["completo"] else ("yes" if f["simple"] else "no"),
                      f["fecha"][:10], key=str(f["carpeta"]))
        if self.filas:
            pos = next((i for i, f in enumerate(self.filas) if f["carpeta"] == antes), 0)
            t.move_cursor(row=pos)
            self.mostrar(self.filas[pos])
        elif self.todas:
            self.query_one("#informe", Static).update(T("Ninguna canción coincide con el filtro.",
                                                        "No song matches the filter."))
        else:
            self.query_one("#informe", Static).update(T("Todavía no hay canciones procesadas en output.",
                                                        "No processed songs in output yet."))
        n = len(self.filas)
        self.sub_title = f"{c.VERSION} · " + (T(f"{n} canciones", f"{n} songs") if n == len(self.todas)
                                              else T(f"{n} de {len(self.todas)} canciones",
                                                     f"{n} of {len(self.todas)} songs"))

    @on(Input.Changed, "#filtro")
    def _filtro(self, ev):
        if ev.value:
            self.filtro_tanda = None
        self.pintar_tabla()

    @on(Input.Submitted, "#filtro")
    def _filtro_hecho(self, ev):
        self.query_one("#tabla", DataTable).focus()

    def action_quitar_filtro(self):
        if self.filtro_tanda:
            self.filtro_tanda = None
            self.pintar_tabla()
        filtro = self.query_one("#filtro", Input)
        if filtro.value:
            filtro.value = ""
        self.query_one("#tabla", DataTable).focus()

    def action_filtrar(self):
        if self.query_one("TabbedContent").active == "tab-tanda":
            self.query_one("#tanda-filtro", Input).focus()
            return
        self.query_one("TabbedContent").active = "tab-canciones"
        self.query_one("#filtro", Input).focus()

    @on(DataTable.HeaderSelected, "#tabla")
    def _ordenar(self, ev):
        """Click a column header to sort by it; click it again to reverse. Ties keep artist/album/song order."""
        col = str(ev.column_key.value)
        principal, desc = self.orden[0]
        desc = (not desc) if col == principal else col in ("fecha", "bpm")   # dates and tempo: highest first
        base = [("artista", False), ("album", False), ("titulo", False)]
        self.orden = [(col, desc)] + [o for o in base if o[0] != col]
        self.pintar_tabla()

    def fila_actual(self):
        t = self.query_one("#tabla", DataTable)
        if not self.filas or t.cursor_row is None or t.cursor_row >= len(self.filas):
            return None
        return self.filas[t.cursor_row]

    def mostrar(self, f):
        texto = ""
        if f["motivos"]:
            texto += "[yellow]" + T("Revisar: ", "Check: ") + ", ".join(f["motivos"]) + "[/yellow]\n\n"
        inf = f["carpeta"] / "informe.txt"
        if inf.exists():
            from rich.markup import escape
            texto += escape(inf.read_text(encoding="utf-8", errors="replace"))
        self.query_one("#informe", Static).update(texto)

    @on(DataTable.RowHighlighted, "#tabla")
    def _resaltada(self, ev):
        if 0 <= ev.cursor_row < len(self.filas):
            self.mostrar(self.filas[ev.cursor_row])

    def action_refrescar(self):
        self.filtro_tanda = None
        self.cargar_canciones()
        if self.proceso is None:
            self.volver_a_opciones()

    def action_carpeta(self):
        f = self.fila_actual()
        if f:
            abrir(f["carpeta"])

    def _abrir_mp3(self, sufijo):
        f = self.fila_actual()
        if not f:
            return
        mp3 = next(iter(f["carpeta"].glob(f"*{sufijo}.mp3")), None)
        if mp3:
            abrir(mp3)
        else:
            self.notify(T("No está ese archivo", "That file isn't there"), severity="warning")

    def action_clics(self):
        self._abrir_mp3("_clics")

    def action_ab(self):
        self._abrir_mp3("_AB")

    def action_retocar(self):
        f = self.fila_actual()
        if f is None:
            return

        def hecho(cambios):
            if cambios:
                self.regenerar(f, cambios)
            elif cambios == {}:
                self.notify(T("Sin cambios", "No changes"))
        self.push_screen(Retocar(f), hecho)

    def action_reempaquetar(self):
        f = self.fila_actual()
        if f:
            self.regenerar(f, {})

    @work(thread=True, exclusive=True, group="regenerar")
    def regenerar(self, f, cambios):
        self.call_from_thread(self.escribir, f"[b]{f['nombre']}[/b]: " + T("trabajando...", "working..."))
        try:
            rutas, error, hechos = c.regenerar(f["carpeta"], compilar=c.COMPILAR, **cambios)
        except Exception as ex:
            rutas, error, hechos = [], str(ex), []
        if hechos and cambios:
            self.call_from_thread(self.escribir, "  " + "; ".join(hechos))
        for r in rutas:
            self.call_from_thread(self.escribir, f"  [green]-> {r}[/green]")
        if error and (c.COMPILAR or not hechos):
            self.call_from_thread(self.escribir, f"  [red]ERROR: {error}[/red]")
        self.call_from_thread(self.cargar_canciones)

    # ----- batch tab
    def cargar_archivos(self):
        """Reads input (and its subfolders): artist, album and title of each file from its tags, and whether it
        is new, already processed, failed before or had no bass. New ones come ticked."""
        _, fallidas, sin_bajo = c.historial(self.salida)
        self.items = []
        for p in archivos_input():
            try:
                artista, titulo, _, et = c.metadatos(p)
                album = c._album_de(p, et)
                nombre, carpeta = c.destino(p, self.salida)[:2]
                hecha = (carpeta / f"{nombre}.gp5").exists()
            except Exception:
                artista, titulo, album, hecha = T("Desconocido", "Unknown"), p.stem, "", False
            estado = ("procesada" if hecha else "sin_bajo" if p.name in sin_bajo
                      else "fallo" if p.name in fallidas else "nueva")
            self.items.append({"ruta": p, "artista": artista, "album": album or T("(sin álbum)", "(no album)"),
                               "titulo": titulo, "estado": estado, "marcada": estado == "nueva",
                               "dur": duracion_audio(p), "resultado": None})
        self.pintar_arbol(reconstruir=True)

    def pintar_arbol(self, reconstruir=False):
        arbol = self.query_one("#arbol", ArbolTanda)
        if reconstruir:
            antes = arbol.cursor_node.data if arbol.cursor_node is not None and arbol.cursor_node.data else {}
            antes = antes.get("item") or (antes.get("grupo") or [None])[0]
            arbol.clear()
            arbol.show_root = False
            grupos = {}
            for it in sorted(self.visibles(), key=lambda x: (normal(x["artista"]), normal(x["album"]), normal(x["titulo"]))):
                grupos.setdefault(it["artista"], {}).setdefault(it["album"], []).append(it)
            for artista, albumes in grupos.items():
                na = arbol.root.add("", data={"grupo": [i for l in albumes.values() for i in l]}, expand=True)
                na.data["nombre"] = artista
                for album, items in albumes.items():
                    nb = na.add("", data={"grupo": items, "nombre": album}, expand=True)
                    for it in items:
                        it["nodo"] = nb.add_leaf("", data={"item": it})
            if antes is not None and antes.get("nodo") is not None and antes in self.visibles():
                self.call_after_refresh(arbol.move_cursor, antes["nodo"])
        caja = lambda m: "\\[x] " if m is True else "\\[-] " if m is None else "\\[ ] "
        def pintar(nodo):
            d = nodo.data or {}
            if "item" in d:
                it = d["item"]
                est = it["resultado"] or ("[dim]" + T(*ESTADOS[it["estado"]]) + "[/dim]")
                dur = f"  [dim]{int(it['dur'] // 60)}:{int(it['dur'] % 60):02d}[/dim]" if it["dur"] else ""
                nodo.set_label(f"{caja(it['marcada'])}{it['titulo']}  {est}{dur}")
            elif "grupo" in d:
                ms = [i["marcada"] for i in d["grupo"]]
                m = True if all(ms) else False if not any(ms) else None
                nodo.set_label(f"{caja(m)}[b]{d['nombre']}[/b]\u00a0 [dim]({len(ms)})[/dim]")
            for h in nodo.children:
                pintar(h)
        pintar(arbol.root)
        self.actualizar_resumen()

    def actualizar_resumen(self):
        marcadas = [i for i in self.items if i["marcada"]]
        n = {k: sum(1 for i in self.items if i["estado"] == k) for k in ESTADOS}
        self.query_one("#tanda-cabecera", Label).update(
            T("[b]CANCIONES EN INPUT[/b]\u00a0 ", "[b]SONGS IN INPUT[/b]\u00a0 ") + f"({len(self.items)} · " +
            ", ".join(f"{v} {T(*(ESTADOS if v == 1 else ESTADOS_PLURAL)[k])}" for k, v in n.items() if v) + ")" +
            (T(f"  · se ven {len(self.visibles())}", f"  · showing {len(self.visibles())}")
             if len(self.visibles()) != len(self.items) else ""))
        if self.proceso is not None or self.terminada:
            return
        if not self.items:
            txt = T("No hay canciones en input. Mete los mp3 en la carpeta input (o en subcarpetas) y pulsa r.",
                    "No songs in input. Put your mp3s in the input folder (or subfolders) and press r.")
        elif not marcadas:
            txt = T("Marca las canciones que quieras procesar (espacio, o los botones de arriba).",
                    "Tick the songs to process (space, or the buttons above).")
        else:
            nuevas = sum(1 for i in marcadas if i["estado"] == "nueva")
            seg = (c.historial(self.salida)[0] or 270.0) * len(marcadas)
            txt = T(f"Se van a procesar [b]{len(marcadas)}\u00a0[/b]" + ("canción" if len(marcadas) == 1 else "canciones"),
                    f"[b]{len(marcadas)}\u00a0[/b]" + ("song" if len(marcadas) == 1 else "songs") + " to process")
            if len(marcadas) - nuevas:
                txt += T(f" ({nuevas} nuevas, {len(marcadas) - nuevas} se repiten)",
                         f" ({nuevas} new, {len(marcadas) - nuevas} redone)")
            txt += T(" · unos ", " · about ") + c.duracion_txt(seg)
        self.query_one("#tanda-resumen", Label).update(txt)
        self.query_one("#t-empezar", Button).disabled = not marcadas

    def marcar_nodo(self, nodo):
        d = nodo.data or {}
        if self.proceso is not None or self.terminada:
            return
        if "item" in d:
            d["item"]["marcada"] = not d["item"]["marcada"]
        elif "grupo" in d:
            nuevo = not all(i["marcada"] for i in d["grupo"])
            for i in d["grupo"]:
                i["marcada"] = nuevo
        self.pintar_arbol(reconstruir=self.solo_marcadas)

    def visibles(self):
        """Songs the tree shows: those matching the batch filter and, with "Only ticked" on, the ticked ones."""
        palabras = normal(self.query_one("#tanda-filtro", Input).value).split()
        return [i for i in self.items
                if (not self.solo_marcadas or i["marcada"])
                and all(p in normal(f"{i['artista']} {i['album']} {i['titulo']}") for p in palabras)]

    def _marcar(self, regla):
        """All / None / Only new / Invert: they act on the songs shown (all of them when nothing filters)."""
        if self.proceso is None and not self.terminada:
            for i in self.visibles():
                i["marcada"] = regla(i)
            self.pintar_arbol(reconstruir=self.solo_marcadas)

    def action_ver_marcadas(self):
        self.solo_marcadas = not self.solo_marcadas
        self.query_one("#m-ver-marcadas", Button).set_class(self.solo_marcadas, "activo")
        self.pintar_arbol(reconstruir=True)

    @on(Button.Pressed, "#m-ver-marcadas")
    def _b_ver_marcadas(self):
        self.action_ver_marcadas()

    @on(Input.Changed, "#tanda-filtro")
    def _tanda_filtro(self, ev):
        self.pintar_arbol(reconstruir=True)

    @on(Input.Submitted, "#tanda-filtro")
    def _tanda_filtro_hecho(self, ev):
        self.query_one("#arbol", ArbolTanda).focus()

    def action_marcar_todas(self):
        self._marcar(lambda i: True)

    def action_marcar_ninguna(self):
        self._marcar(lambda i: False)

    def action_marcar_nuevas(self):
        self._marcar(lambda i: i["estado"] == "nueva")

    def action_marcar_invertir(self):
        self._marcar(lambda i: not i["marcada"])

    @on(Button.Pressed, "#m-todas")
    def _b_todas(self):
        self.action_marcar_todas()

    @on(Button.Pressed, "#m-ninguna")
    def _b_ninguna(self):
        self.action_marcar_ninguna()

    @on(Button.Pressed, "#m-nuevas")
    def _b_nuevas(self):
        self.action_marcar_nuevas()

    @on(Button.Pressed, "#m-invertir")
    def _b_invertir(self):
        self.action_marcar_invertir()

    @on(Tree.NodeSelected, "#arbol")
    def _clic_arbol(self, ev):
        if ev.node.data and "item" in ev.node.data:      # click (or Enter) on a song ticks it
            self.marcar_nodo(ev.node)

    @on(Button.Pressed, "#t-empezar")
    def empezar(self):
        if self.terminada:                       # after a batch the button reads "New batch"
            self.volver_a_opciones()
            return
        marcadas = [i for i in self.items if i["marcada"]]
        if not marcadas:
            self.notify(T("No hay canciones marcadas", "No songs ticked"), severity="warning")
            return
        orden = [sys.executable, str(c.AQUI / "auto_cdlc.py"), "--no-questions", "--no-update",
                 *[str(i["ruta"]) for i in marcadas]]
        dd = self.query_one("#t-dd", Input).value.replace("%", "").strip()
        if dd:
            orden += ["--start-difficulty", dd]
        orden += ["--simple", self.query_one("#t-simple", Select).value]
        if self.query_one("#t-tono", Select).value:
            orden += ["--tone", self.query_one("#t-tono", Select).value]
        if self.query_one("#t-pua", Select).value:
            orden += ["--pick", self.query_one("#t-pua", Select).value]
        orden += ["--send", "yes" if self.query_one("#t-enviar", Switch).value else "no"]
        if any(i["estado"] != "nueva" for i in marcadas):
            orden.append("--force")           # a ticked song that was already done (or failed) is redone
        for i in self.items:
            i["resultado"] = ("[dim]" + T("en cola", "queued") + "[/dim]") if i["marcada"] else None
        self.tanda = {i["ruta"].name: i for i in marcadas}
        self.hechas_tanda = []
        barra = self.query_one("#p-total", ProgressBar)
        barra.update(total=len(marcadas), progress=0)
        self.query_one("#p-actual", Label).update("")
        self.query_one("#p-paso", Label).update("")
        self.query_one("#tanda-derecha", ContentSwitcher).current = "tanda-progreso"
        self.query_one("#t-empezar", Button).disabled = True
        self.query_one("#t-parar", Button).disabled = False
        self.query_one("#t-ver", Button).disabled = True
        self.query_one("#tanda-log", RichLog).clear()
        self.proceso = True                 # set before the thread starts: the list is locked from now on
        self.query_one("#tanda-filtro", Input).value = ""
        self.solo_marcadas = True           # while it runs, the tree shows just this batch
        self.query_one("#m-ver-marcadas", Button).set_class(True, "activo")
        self.query_one("#tanda-resumen", Label).update(
            T(f"Procesando {len(marcadas)} " + ("canción…" if len(marcadas) == 1 else "canciones…"),
              f"Processing {len(marcadas)} " + ("song…" if len(marcadas) == 1 else "songs…")))
        self.pintar_arbol(reconstruir=True)
        self.lanzar(orden)

    def _linea_tanda(self, linea):
        """Follows the batch's output: which song is running, how it ended, the current step."""
        import re
        self.query_one("#tanda-log", RichLog).write(linea)
        m = re.match(r"\s*\[(\d+)/(\d+)\] (.+?)  \(", linea)
        if m:
            it = self.tanda.get(m.group(3))
            if it:
                it["resultado"] = "[yellow]" + T("en marcha…", "running…") + "[/yellow]"
                self.actual = it
                self.query_one("#p-actual", Label).update(
                    T(f"Canción {m.group(1)} de {m.group(2)} · ", f"Song {m.group(1)} of {m.group(2)} · ") +
                    f"[b]{it['titulo']}[/b]")
                self.pintar_arbol()
            return
        it = getattr(self, "actual", None)
        if it is None:
            return
        fin = None
        paso = re.match(r"\s*\[(\d)/(\d)\] ", linea)
        if paso:                                 # steps inside a song: move the bar a little
            self.query_one("#p-total", ProgressBar).update(
                progress=len(self.hechas_tanda) + (int(paso.group(1)) - 1) / int(paso.group(2)))
        if linea.startswith("  OK:"):
            dudosa = re.search(r"fiabilidad|reliability|cuidado|careful", linea, re.I)
            fin = ("[green]" + T("hecha", "done") + "[/green] · " +
                   ("[yellow]" + T("revisar", "check it") + "[/yellow]" if dudosa else T("fiable", "reliable")))
        elif linea.startswith(("  ERROR:", "  SIN BAJO:", "  NO BASS:")):
            fin = "[red]" + ("error" if "ERROR" in linea else T("sin bajo", "no bass")) + "[/red]"
        if fin:
            it["resultado"] = fin
            self.hechas_tanda.append(it)
            self.actual = None
            self.query_one("#p-total", ProgressBar).update(progress=len(self.hechas_tanda))
            self.query_one("#p-paso", Label).update("")
            self.pintar_arbol()
        elif linea.strip():
            self.query_one("#p-paso", Label).update("[dim]" + linea.strip()[:70] + "[/dim]")

    @work(thread=True, exclusive=True, group="tanda")
    def lanzar(self, orden):
        entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.proceso = subprocess.Popen(orden, cwd=str(c.AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                        env=entorno, creationflags=flags)
        for linea in self.proceso.stdout:
            linea = linea.rstrip()
            # progress bars of the models would flood the log
            if linea and "it/s]" not in linea and "s/it]" not in linea and "Warning" not in linea:
                self.call_from_thread(self._linea_tanda, linea)
        codigo = self.proceso.wait()
        self.call_from_thread(self.query_one("#tanda-log", RichLog).write,
                              T(f"--- terminado (código {codigo}) ---", f"--- finished (code {codigo}) ---"))
        self.call_from_thread(self._tanda_terminada)

    def _tanda_terminada(self):
        self.proceso = None
        self.query_one("#t-parar", Button).disabled = True
        hechas = len(self.hechas_tanda)
        for i in self.items:                    # songs that never started (stopped batch)
            if i["marcada"] and i not in self.hechas_tanda:
                i["resultado"] = "[dim]" + T("no procesada", "not processed") + "[/dim]"
        self.query_one("#tanda-resumen", Label).update(
            T(f"Tanda terminada: {hechas} de {len(self.tanda)} canciones. ", f"Batch finished: {hechas} of {len(self.tanda)} songs. ") +
            T("[b]Ver en Canciones[/b] para revisarlas, [b]Nueva tanda[/b] para otra.",
              "[b]Show in Songs[/b] to check them, [b]New batch[/b] for another one."))
        self.query_one("#t-ver", Button).disabled = not hechas
        self.terminada = True
        self.query_one("#t-empezar", Button).label = T("Nueva tanda", "New batch")
        self.query_one("#t-empezar", Button).disabled = False
        self.pintar_arbol()
        self.cargar_canciones()

    @on(Button.Pressed, "#t-ver")
    def ver_en_canciones(self):
        """Songs tab filtered to this batch's songs (by title)."""
        self.query_one("TabbedContent").active = "tab-canciones"
        titulos = [i["titulo"] for i in self.hechas_tanda]
        self.filtro_tanda = {normal(t) for t in titulos}
        self.query_one("#filtro", Input).value = ""
        self.pintar_tabla()
        self.query_one("#tabla", DataTable).focus()

    def volver_a_opciones(self):
        self.terminada = False
        self.solo_marcadas = False
        self.query_one("#m-ver-marcadas", Button).set_class(False, "activo")
        self.query_one("#t-empezar", Button).label = T("▶ Empezar", "▶ Start")
        self.query_one("#tanda-derecha", ContentSwitcher).current = "tanda-opciones"
        self.query_one("#t-ver", Button).disabled = True
        self.cargar_archivos()

    @on(Button.Pressed, "#t-parar")
    def parar(self):
        if self.proceso not in (None, True) and self.proceso.poll() is None:
            self.proceso.terminate()
            self.notify(T("Parando la tanda (la canción en curso se pierde)", "Stopping the batch (the current song is lost)"))

    # ----- settings tab
    def cargar_ajustes(self):
        conf = c.leer_configuracion()
        for clave, tipo, opciones, _ in CAMPOS:
            v = conf.get(clave, "")
            w = self.query_one(f"#cfg-{clave}")
            if tipo == "bool":
                w.value = (v or "yes").lower() in SI
            elif tipo == "select":
                v = v.lower()
                if v in opciones:
                    w.value = v
                else:
                    w.clear()
            else:
                w.value = v

    @on(Button.Pressed, "#cfg-buscar-dlc")
    def buscar_dlc(self):
        self.query_one("#cfg-buscar-dlc", Button).disabled = True
        self.notify(T("Buscando instalaciones de Rocksmith (hasta medio minuto)…",
                      "Looking for Rocksmith installs (up to half a minute)…"))
        self._buscar_dlc()

    @work(thread=True)
    def _buscar_dlc(self):
        dlcs = c.carpetas_rocksmith()
        self.call_from_thread(self._dlc_encontradas, dlcs)

    def _dlc_encontradas(self, dlcs):
        self.query_one("#cfg-buscar-dlc", Button).disabled = False

        def elegida(r):
            if r is not None:
                self.query_one("#cfg-psarc_folder", Input).value = r
                self.notify(T("Pulsa Guardar para aplicarlo.", "Press Save to apply it."))
        self.push_screen(ElegirDlc(dlcs), elegida)

    @on(Button.Pressed, "#cfg-guardar")
    def guardar(self):
        conf = c.leer_configuracion()
        cambiadas = []
        for clave, tipo, opciones, _ in CAMPOS:
            w = self.query_one(f"#cfg-{clave}")
            if tipo == "bool":
                v = "yes" if w.value else "no"
            elif tipo == "select":
                v = "" if w.value is Select.BLANK else str(w.value)
            else:
                v = w.value.strip()
            if v != conf.get(clave, "") and not (tipo == "bool" and (conf.get(clave, "yes").lower() in SI) == w.value):
                c.poner_clave(clave, v)
                cambiadas.append(clave)
        if cambiadas:
            self.conf = c.entorno_basico()
            self.notify(T("Guardado: ", "Saved: ") + ", ".join(cambiadas) +
                        (T(" (el idioma cambia al volver a abrir)", " (the language changes when reopened)")
                         if "language" in cambiadas else ""))
        else:
            self.notify(T("No había cambios", "Nothing changed"))


def main():
    AutoCdlc().run()


if __name__ == "__main__":
    main()

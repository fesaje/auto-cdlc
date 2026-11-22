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
from textual.widgets import (Button, DataTable, Footer, Header, Input, Label, RichLog, Select, SelectionList,
                             Static, Switch, TabbedContent, TabPane)

import auto_cdlc as c

CONF = c.entorno_basico()        # language first: the labels below depend on it
T = c.T
TONOS = ["auto", "clean", "clean_pick", "overdrive", "distortion", "fuzz"]
SIMPLE = {"no": None, "bar": 0, "half": 1, "beat": 2, "eighth": 3}
SIMPLE_INV = {v: k for k, v in SIMPLE.items()}
NIVEL = {"alta": ("high", "green"), "media": ("medium", "yellow"), "baja": ("low", "red")}


def abrir(ruta):
    """Opens a file or folder with the system's default program."""
    try:
        if os.name == "nt":
            os.startfile(str(ruta))                                  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(ruta)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        filas.append({
            "carpeta": carpeta, "info": info,
            "nombre": carpeta.name,
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
    return sorted(filas, key=lambda f: f["fecha"], reverse=True)


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
    #tabla { width: 3fr; }
    #detalle { width: 2fr; border-left: solid $primary; padding: 0 1; }
    #registro, #tanda-log { height: 1fr; border-top: solid $primary; }
    #tanda-opciones { height: auto; }
    #tanda-opciones > Vertical { width: 1fr; height: auto; padding: 0 1; }
    #archivos { height: 1fr; min-height: 4; }
    #tanda-log { min-height: 6; }
    #ajustes Horizontal { height: auto; }
    #ajustes Label { width: 50; padding: 1 1 0 0; }
    #ajustes Input, #ajustes Select { width: 1fr; }
    Retocar { align: center middle; }
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
    ]

    def __init__(self):
        super().__init__()
        self.conf = CONF
        self.salida = c.AQUI / "output"
        self.filas = []
        self.proceso = None
        c.log = self._log_hilo           # messages from auto_cdlc go to the log panel, not to the terminal
        self.sub_title = f"{c.VERSION}"

    # ----- layout
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tab-canciones"):
            with TabPane(T("Canciones", "Songs"), id="tab-canciones"):
                with Vertical():
                    with Horizontal(id="canciones-panel"):
                        yield DataTable(id="tabla", cursor_type="row", zebra_stripes=True)
                        yield VerticalScroll(Static(id="informe"), id="detalle")
                    yield RichLog(id="registro", wrap=True, markup=True, max_lines=500)
            with TabPane(T("Tanda", "Batch"), id="tab-tanda"):
                with Vertical():
                    yield Label(T("Canciones de input (marca las que quieras procesar):",
                                  "Songs in input (tick the ones to process):"))
                    yield SelectionList(id="archivos")
                    with Horizontal(id="tanda-opciones"):
                        with Vertical():
                            yield Label(T("Dificultad inicial (%)", "Starting difficulty (%)"))
                            yield Input(id="t-dd")
                            yield Label(T("Arreglo simplificado", "Simplified arrangement"))
                            yield Select([(k, k) for k in SIMPLE], id="t-simple", allow_blank=False, value="beat")
                        with Vertical():
                            yield Label(T("Tono (todas)", "Tone (all songs)"))
                            yield Select([(T("el de cada disco / config", "each album's / config"), "")] +
                                         [(t, t) for t in TONOS], id="t-tono", allow_blank=False, value="")
                            yield Label(T("Púa (todas)", "Pick (all songs)"))
                            yield Select([(T("el de cada disco / detectar", "each album's / detect"), ""),
                                          (T("con púa", "pick"), "yes"), (T("con dedos", "fingers"), "no")],
                                         id="t-pua", allow_blank=False, value="")
                        with Vertical():
                            yield Label(T("Enviar resultados anónimos", "Send anonymous results"))
                            yield Switch(id="t-enviar", value=True)
                            yield Label(T("Repetir las ya procesadas", "Redo songs already processed"))
                            yield Switch(id="t-forzar", value=False)
                            with Horizontal():
                                yield Button(T("Empezar", "Start"), variant="primary", id="t-empezar")
                                yield Button(T("Parar", "Stop"), variant="error", id="t-parar", disabled=True)
                    yield RichLog(id="tanda-log", wrap=True, max_lines=5000)
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
                    yield Button(T("Guardar en config.txt", "Save to config.txt"), variant="primary", id="cfg-guardar")
        yield Footer()

    def on_mount(self):
        t = self.query_one("#tabla", DataTable)
        t.add_columns(T("Canción", "Song"), T("Fiab.", "Rel."), "BPM", T("Compás", "Time"), T("Afinación", "Tuning"),
                      T("Tono", "Tone"), T("Púa", "Pick"), "Scroll", T("Simpl.", "Simple"), T("Fecha", "Date"))
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
        elif os.name == "nt" and not c.WWISE:
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
        t = self.query_one("#tabla", DataTable)
        fila_actual = t.cursor_row if t.row_count else 0
        t.clear()
        self.filas = canciones(self.salida)
        for f in self.filas:
            nivel, color = NIVEL.get(f["fiabilidad"], ("?", "white"))
            nivel = T(f["fiabilidad"] or "?", nivel)
            t.add_row(f["nombre"], f"[{color}]{nivel}[/{color}]",
                      f"{f['bpm']:.0f}" if f["bpm"] else "?", f["metro"] or "?",
                      c.afin_txt(f["afinacion"]) if f["afinacion"] else "?",
                      c.NOMBRE_PRESET.get((f["tono"] or "?").split(" (")[0], (f["tono"] or "?").split(" (")[0]),
                      T("sí", "yes") if f["pua"] else "no",
                      f"{f['velocidad']}" if f["velocidad"] else "?",
                      SIMPLE_INV.get(f["simple"], "?") if f["completo"] else ("yes" if f["simple"] else "no"),
                      f["fecha"][:10], key=str(f["carpeta"]))
        if self.filas:
            t.move_cursor(row=min(fila_actual, len(self.filas) - 1))
            self.mostrar(self.filas[t.cursor_row])
        else:
            self.query_one("#informe", Static).update(T("Todavía no hay canciones procesadas en output.",
                                                        "No processed songs in output yet."))

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
        self.cargar_canciones()
        self.cargar_archivos()

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
        sl = self.query_one("#archivos", SelectionList)
        sl.clear_options()
        entrada = c.AQUI / "input"
        archivos = sorted(p for p in entrada.iterdir() if p.is_file() and p.suffix.lower() in c.EXTENSIONES) \
            if entrada.is_dir() else []
        for p in archivos:
            nombre, carpeta = c.destino(p, self.salida)[:2]
            hecha = (carpeta / f"{nombre}.gp5").exists()
            sl.add_option((p.name + ("  [dim](" + T("ya procesada", "already processed") + ")[/dim]" if hecha else ""),
                           str(p), not hecha))

    @on(Button.Pressed, "#t-empezar")
    def empezar(self):
        archivos = self.query_one("#archivos", SelectionList).selected
        if not archivos:
            self.notify(T("No hay canciones marcadas", "No songs ticked"), severity="warning")
            return
        orden = [sys.executable, str(c.AQUI / "auto_cdlc.py"), "--no-questions", "--no-update", *archivos]
        dd = self.query_one("#t-dd", Input).value.replace("%", "").strip()
        if dd:
            orden += ["--start-difficulty", dd]
        orden += ["--simple", self.query_one("#t-simple", Select).value]
        if self.query_one("#t-tono", Select).value:
            orden += ["--tone", self.query_one("#t-tono", Select).value]
        if self.query_one("#t-pua", Select).value:
            orden += ["--pick", self.query_one("#t-pua", Select).value]
        orden += ["--send", "yes" if self.query_one("#t-enviar", Switch).value else "no"]
        if self.query_one("#t-forzar", Switch).value:
            orden.append("--force")
        self.query_one("#t-empezar", Button).disabled = True
        self.query_one("#t-parar", Button).disabled = False
        self.query_one("#tanda-log", RichLog).clear()
        self.lanzar(orden)

    @work(thread=True, exclusive=True, group="tanda")
    def lanzar(self, orden):
        log = self.query_one("#tanda-log", RichLog)
        entorno = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.proceso = subprocess.Popen(orden, cwd=str(c.AQUI), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                        env=entorno, creationflags=flags)
        for linea in self.proceso.stdout:
            linea = linea.rstrip()
            # progress bars of the models would flood the log
            if linea and "it/s]" not in linea and "s/it]" not in linea and "Warning" not in linea:
                self.call_from_thread(log.write, linea)
        codigo = self.proceso.wait()
        self.proceso = None
        self.call_from_thread(log.write, T(f"--- terminado (código {codigo}) ---", f"--- finished (code {codigo}) ---"))
        self.call_from_thread(self._tanda_terminada)

    def _tanda_terminada(self):
        self.query_one("#t-empezar", Button).disabled = False
        self.query_one("#t-parar", Button).disabled = True
        self.cargar_canciones()
        self.cargar_archivos()

    @on(Button.Pressed, "#t-parar")
    def parar(self):
        if self.proceso and self.proceso.poll() is None:
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

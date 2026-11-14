"""
Widget Hora - Configuración
Ventana independiente para cambiar ubicación, fuente, tamaño, posición, sombra, etc.
Guarda todo en %APPDATA%\\WidgetHora\\config.json; el widget lo detecta y se actualiza al instante.
"""
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import colorchooser, messagebox, ttk

import common as C

POS_LABELS = {
    "custom": "Personalizada (usar X e Y)",
    "top-right": "Arriba a la derecha",
    "top-left": "Arriba a la izquierda",
    "bottom-right": "Abajo a la derecha",
    "bottom-left": "Abajo a la izquierda",
    "center": "Centro de la pantalla",
}
ALIGN_LABELS = {"left": "Izquierda", "center": "Centro", "right": "Derecha"}


class ConfigApp:
    def __init__(self):
        C.set_dpi_aware()
        self.root = tk.Tk()
        self.root.title(C.CONFIG_TITLE)
        self.root.resizable(False, False)
        try:
            ico = os.path.join(C.APP_DIR, "icon_config.ico")
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

        self.cfg = C.load_cfg()
        self.v = {}
        self.q = queue.Queue()
        self.results = []
        self.sel = {"city": self.cfg["city"], "lat": self.cfg["lat"], "lon": self.cfg["lon"]}

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        self.tabs = {}
        for key, title in (("loc", "Ubicación y clima"), ("look", "Apariencia"), ("shadow", "Sombra"),
                           ("pos", "Posición"), ("gen", "General")):
            f = ttk.Frame(nb, padding=14)
            nb.add(f, text=title)
            self.tabs[key] = f

        self._tab_location(self.tabs["loc"])
        self._tab_look(self.tabs["look"])
        self._tab_shadow(self.tabs["shadow"])
        self._tab_position(self.tabs["pos"])
        self._tab_general(self.tabs["gen"])

        self.status = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.status, foreground="#2b6f2b",
                  wraplength=520).pack(fill="x", pady=(8, 0))

        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Restaurar valores", command=self.restore).pack(side="left")
        ttk.Button(bar, text="Cancelar", command=self.root.destroy).pack(side="right")
        ttk.Button(bar, text="Aceptar", command=lambda: self.save(close=True)).pack(side="right", padx=6)
        ttk.Button(bar, text="Aplicar", command=self.save).pack(side="right")

        self._toggle_loc()
        self._refresh_running()
        self.root.after(200, self._poll)

    # ------------------------------------------------------------ utilidades UI
    def var(self, key, default=None):
        d = C.DEFAULTS[key] if default is None else default
        val = self.cfg[key]
        if isinstance(d, bool):
            v = tk.BooleanVar(value=val)
        elif isinstance(d, int):
            v = tk.IntVar(value=val)
        else:
            v = tk.StringVar(value="" if val is None else val)
        self.v[key] = v
        return v

    @staticmethod
    def row(parent, r, text, widget, span=1):
        ttk.Label(parent, text=text).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 10))
        widget.grid(row=r, column=1, columnspan=span, sticky="w", pady=4)

    def color_button(self, parent, key):
        btn = tk.Button(parent, width=10, relief="groove", bg=self.v[key].get(),
                        activebackground=self.v[key].get(), text="Elegir…")
        def pick():
            res = colorchooser.askcolor(color=self.v[key].get(), parent=self.root, title="Elegir color")
            if res and res[1]:
                self.v[key].set(res[1])
                btn.config(bg=res[1], activebackground=res[1])
        btn.config(command=pick)
        return btn

    def spin(self, parent, key, lo, hi, width=6):
        return ttk.Spinbox(parent, from_=lo, to=hi, width=width, textvariable=self.v[key])

    # ------------------------------------------------------------ pestaña: ubicación
    def _tab_location(self, f):
        self.mode = tk.StringVar(value=self.cfg["location_mode"])
        ttk.Radiobutton(f, text="Usar la ubicación de Windows (automática)", variable=self.mode,
                        value="windows", command=self._toggle_loc).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Si el servicio de ubicación está desactivado, se usa la IP como respaldo.",
                  foreground="#666").grid(row=1, column=0, columnspan=3, sticky="w", padx=(22, 0))
        self.btn_test = ttk.Button(f, text="Probar ubicación de Windows", command=self.test_windows)
        self.btn_test.grid(row=2, column=0, columnspan=2, sticky="w", padx=(22, 0), pady=6)
        self.lbl_test = ttk.Label(f, text="", wraplength=470, foreground="#444")
        self.lbl_test.grid(row=3, column=0, columnspan=3, sticky="w", padx=(22, 0))

        ttk.Separator(f).grid(row=4, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Radiobutton(f, text="Elegir una ciudad manualmente", variable=self.mode,
                        value="manual", command=self._toggle_loc).grid(row=5, column=0, columnspan=3, sticky="w")
        self.q_city = tk.StringVar()
        self.ent_city = ttk.Entry(f, textvariable=self.q_city, width=30)
        self.ent_city.grid(row=6, column=0, sticky="w", padx=(22, 6), pady=6)
        self.ent_city.bind("<Return>", lambda e: self.search_city())
        self.btn_search = ttk.Button(f, text="Buscar", command=self.search_city)
        self.btn_search.grid(row=6, column=1, sticky="w")
        self.cmb_city = ttk.Combobox(f, state="readonly", width=46)
        self.cmb_city.grid(row=7, column=0, columnspan=3, sticky="w", padx=(22, 0))
        self.cmb_city.bind("<<ComboboxSelected>>", self._city_selected)
        self.lbl_sel = ttk.Label(f, text=self._sel_text(), foreground="#2b6f2b")
        self.lbl_sel.grid(row=8, column=0, columnspan=3, sticky="w", padx=(22, 0), pady=4)

        ttk.Separator(f).grid(row=9, column=0, columnspan=3, sticky="ew", pady=12)

        self.v["units"] = tk.StringVar(value=self.cfg["units"])
        u = ttk.Frame(f)
        ttk.Radiobutton(u, text="°C", variable=self.v["units"], value="C").pack(side="left")
        ttk.Radiobutton(u, text="°F", variable=self.v["units"], value="F").pack(side="left", padx=10)
        self.row(f, 10, "Unidad de temperatura", u)
        self.var("update_minutes")
        self.row(f, 11, "Actualizar el clima cada (min)", self.spin(f, "update_minutes", 5, 180))

    def _sel_text(self):
        return f"Ciudad elegida: {self.sel['city']}" if self.sel["city"] else "Ninguna ciudad elegida todavía."

    def _toggle_loc(self):
        manual = self.mode.get() == "manual"
        st = "normal" if manual else "disabled"
        self.ent_city.config(state=st)
        self.btn_search.config(state=st)
        self.cmb_city.config(state="readonly" if manual else "disabled")
        self.btn_test.config(state="disabled" if manual else "normal")

    def search_city(self):
        q = self.q_city.get().strip()
        if not q:
            return
        self.lbl_sel.config(text="Buscando…", foreground="#444")
        def work():
            try:
                self.q.put(("search", C.geocode_search(q)))
            except Exception:
                self.q.put(("search", None))
        threading.Thread(target=work, daemon=True).start()

    def _city_selected(self, _e=None):
        i = self.cmb_city.current()
        if 0 <= i < len(self.results):
            r = self.results[i]
            self.sel = {"city": r["name"], "lat": r["lat"], "lon": r["lon"]}
            self.lbl_sel.config(text=self._sel_text(), foreground="#2b6f2b")

    def test_windows(self):
        self.lbl_test.config(text="Consultando a Windows… (puede tardar unos segundos)")
        self.btn_test.config(state="disabled")
        def work():
            loc = C.windows_location()
            if loc:
                name = C.reverse_name(*loc)
                self.q.put(("win", f"Windows detectó: {name}  ({loc[0]:.3f}, {loc[1]:.3f})"))
            else:
                ip = C.ip_location()
                extra = f" Se usará la ubicación por IP: {ip[2] or ip[0]}." if ip else ""
                self.q.put(("win", "Windows no devolvió una ubicación. Activa Configuración > Privacidad y "
                                   "seguridad > Ubicación (y 'Permitir que las aplicaciones de escritorio "
                                   "accedan a tu ubicación')." + extra))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "search":
                    if data is None:
                        self.lbl_sel.config(text="No se pudo buscar (¿sin conexión?).", foreground="#b33")
                    elif not data:
                        self.lbl_sel.config(text="Sin resultados para esa búsqueda.", foreground="#b33")
                    else:
                        self.results = data
                        self.cmb_city["values"] = [r["label"] for r in data]
                        self.cmb_city.current(0)
                        self._city_selected()
                elif kind == "win":
                    self.lbl_test.config(text=data)
                    if self.mode.get() == "windows":
                        self.btn_test.config(state="normal")
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    # ------------------------------------------------------------ pestaña: apariencia
    def _tab_look(self, f):
        fams = sorted({n for n in tkfont.families(self.root) if not n.startswith("@")}, key=str.lower)
        self.var("font")
        cmb = ttk.Combobox(f, textvariable=self.v["font"], values=fams, state="readonly", width=30)
        self.row(f, 0, "Fuente", cmb, span=2)
        self.var("bold")
        self.row(f, 1, "Negrita", ttk.Checkbutton(f, variable=self.v["bold"]))

        for r, (key, label) in enumerate((("size_time", "Tamaño de la hora"),
                                          ("size_date", "Tamaño de la fecha"),
                                          ("size_weather", "Tamaño del clima")), start=2):
            self.var(key)
            self.row(f, r, label, self.spin(f, key, 8, 300))

        self.var("color")
        self.row(f, 5, "Color del texto", self.color_button(f, "color"))

        self.var("opacity")
        self.row(f, 9, "Opacidad (%)", tk.Scale(f, from_=20, to=100, orient="horizontal", length=180,
                                                variable=self.v["opacity"]))

        self.align = tk.StringVar(value=ALIGN_LABELS[self.cfg["align"]])
        self.row(f, 10, "Alineación", ttk.Combobox(f, textvariable=self.align, values=list(ALIGN_LABELS.values()),
                                                   state="readonly", width=14))

        now = datetime.now()
        self.date_labels = {k: C.format_date(now, k) for k in C.DATE_FORMATS}
        self.date_fmt = tk.StringVar(value=self.date_labels.get(self.cfg["date_format"], self.date_labels["largo"]))
        self.row(f, 11, "Formato de fecha", ttk.Combobox(f, textvariable=self.date_fmt,
                                                         values=list(self.date_labels.values()),
                                                         state="readonly", width=32), span=2)

        opts = ttk.Frame(f)
        for key, text in (("h24", "Reloj de 24 horas"), ("show_seconds", "Mostrar segundos"),
                          ("show_date", "Mostrar fecha"), ("show_weather", "Mostrar clima"),
                          ("show_city", "Mostrar ciudad")):
            self.var(key)
        ttk.Checkbutton(opts, text="Reloj de 24 horas", variable=self.v["h24"]).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Mostrar segundos", variable=self.v["show_seconds"]).grid(row=0, column=1, sticky="w", padx=14)
        ttk.Checkbutton(opts, text="Mostrar fecha", variable=self.v["show_date"]).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Mostrar clima", variable=self.v["show_weather"]).grid(row=1, column=1, sticky="w", padx=14)
        ttk.Checkbutton(opts, text="Mostrar ciudad", variable=self.v["show_city"]).grid(row=2, column=0, sticky="w")
        opts.grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------ pestaña: sombra
    def _tab_shadow(self, f):
        self.var("shadow")
        ttk.Checkbutton(f, text="Activar sombra", variable=self.v["shadow"]).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=4)

        def scale(key, lo, hi):
            self.var(key)
            return tk.Scale(f, from_=lo, to=hi, orient="horizontal", length=240, variable=self.v[key])

        self.row(f, 1, "Desplazamiento (px)", scale("shadow_distance", 0, 20))
        self.row(f, 2, "Grosor (px)", scale("shadow_thickness", 0, 10))
        self.row(f, 3, "Difuminado (0 = dura)", scale("shadow_blur", 0, 30))
        self.row(f, 4, "Intensidad (%)", scale("shadow_opacity", 0, 100))
        self.var("shadow_color")
        self.row(f, 5, "Color de la sombra", self.color_button(f, "shadow_color"))
        ttk.Label(f, text="Consejo: para una sombra suave y natural prueba Difuminado 6-10, Grosor 1-2 e "
                          "Intensidad 70-90. Con Difuminado en 0 la sombra queda dura.",
                  foreground="#555", wraplength=440, justify="left").grid(
            row=6, column=0, columnspan=2, sticky="w", pady=14)

    # ------------------------------------------------------------ pestaña: posición
    def _tab_position(self, f):
        self.pos_label = tk.StringVar(value=POS_LABELS.get(self.cfg["pos_mode"], POS_LABELS["top-right"]))
        self.row(f, 0, "Ubicar el widget", ttk.Combobox(f, textvariable=self.pos_label,
                                                        values=list(POS_LABELS.values()), state="readonly", width=28))
        self.var("margin")
        self.row(f, 1, "Margen del borde (px)", self.spin(f, "margin", 0, 1000))
        self.var("x")
        self.row(f, 2, "X (solo en 'Personalizada')", self.spin(f, "x", -10000, 20000, 8))
        self.var("y")
        self.row(f, 3, "Y (solo en 'Personalizada')", self.spin(f, "y", -10000, 20000, 8))
        ttk.Label(f, text="Las posiciones de esquina respetan la barra de tareas.\n"
                          "También puedes arrastrar el widget con el ratón: la posición se guarda sola.",
                  foreground="#555", justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=14)

    # ------------------------------------------------------------ pestaña: general
    def _tab_general(self, f):
        self.autostart = tk.BooleanVar(value=C.get_autostart())
        ttk.Checkbutton(f, text="Iniciar el widget automáticamente con Windows",
                        variable=self.autostart).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        self.var("on_top")
        ttk.Checkbutton(f, text="Mostrar siempre por encima de otras ventanas",
                        variable=self.v["on_top"]).grid(row=1, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Separator(f).grid(row=2, column=0, columnspan=2, sticky="ew", pady=12)
        self.lbl_run = ttk.Label(f, text="")
        self.lbl_run.grid(row=3, column=0, columnspan=2, sticky="w")
        b = ttk.Frame(f)
        ttk.Button(b, text="Iniciar widget", command=self.start_widget).pack(side="left")
        ttk.Button(b, text="Reiniciar widget", command=self.restart_widget).pack(side="left", padx=8)
        ttk.Button(b, text="Cerrar widget", command=self.stop_widget).pack(side="left")
        b.grid(row=4, column=0, columnspan=2, sticky="w", pady=8)

        ttk.Separator(f).grid(row=5, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(f, text="Archivo de configuración:", foreground="#555").grid(row=6, column=0, sticky="w")
        ttk.Label(f, text=C.CFG_FILE, foreground="#555", wraplength=480).grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Button(f, text="Abrir carpeta", command=self.open_folder).grid(row=8, column=0, sticky="w", pady=8)

    def open_folder(self):
        os.makedirs(C.CFG_DIR, exist_ok=True)
        try:
            os.startfile(C.CFG_DIR)
        except Exception:
            pass

    def _refresh_running(self):
        running = C.mutex_exists(C.WIDGET_MUTEX)
        self.lbl_run.config(text="El widget está en ejecución." if running else "El widget no está en ejecución.")
        return running

    def start_widget(self):
        if not self._refresh_running():
            try:
                C.start_widget()
            except Exception as e:
                messagebox.showerror(C.CONFIG_TITLE, f"No se pudo iniciar el widget:\n{e}")
        self.root.after(1500, self._refresh_running)

    def stop_widget(self):
        C.stop_widget()
        self.root.after(800, self._refresh_running)

    def restart_widget(self):
        C.stop_widget()
        self.root.after(700, self.start_widget)

    # ------------------------------------------------------------ guardar / restaurar
    def save(self, close=False):
        try:
            cfg = dict(self.cfg)
            for key, var in self.v.items():
                cfg[key] = var.get()
            cfg["location_mode"] = self.mode.get()
            cfg["pos_mode"] = next(k for k, v in POS_LABELS.items() if v == self.pos_label.get())
            cfg["align"] = next(k for k, v in ALIGN_LABELS.items() if v == self.align.get())
            cfg["date_format"] = next((k for k, v in self.date_labels.items() if v == self.date_fmt.get()), "largo")
            cfg.update(self.sel)
        except (tk.TclError, StopIteration):
            messagebox.showerror(C.CONFIG_TITLE, "Hay un valor numérico no válido. Revísalo e inténtalo de nuevo.")
            return
        if cfg["location_mode"] == "manual" and cfg["lat"] is None:
            messagebox.showwarning(C.CONFIG_TITLE, "Busca y elige una ciudad, o cambia a la ubicación de Windows.")
            return

        for k, (lo, hi) in C.LIMITS.items():
            cfg[k] = max(lo, min(hi, int(cfg[k])))
        C.save_cfg(cfg)
        self.cfg = cfg
        ok_auto = C.set_autostart(self.autostart.get())

        msg = "Guardado. El widget aplica los cambios al instante." if self._refresh_running() \
            else "Guardado. El widget no está en ejecución: pulsa «Iniciar widget» en la pestaña General."
        if not ok_auto:
            msg += " (No se pudo cambiar el inicio automático.)"
        self.status.set(msg)
        if close:
            self.root.after(150, self.root.destroy)

    def restore(self):
        if not messagebox.askyesno(C.CONFIG_TITLE, "¿Restaurar todos los valores predeterminados?"):
            return
        d = C.DEFAULTS
        for key, var in self.v.items():
            var.set(d[key] if d[key] is not None else "")
        self.mode.set(d["location_mode"])
        self.pos_label.set(POS_LABELS[d["pos_mode"]])
        self.align.set(ALIGN_LABELS[d["align"]])
        self.date_fmt.set(self.date_labels[d["date_format"]])
        self.sel = {"city": "", "lat": None, "lon": None}
        self.lbl_sel.config(text=self._sel_text())
        self._toggle_loc()
        self.status.set("Valores restaurados. Pulsa «Aplicar» para guardarlos.")

    def run(self):
        self.root.mainloop()


def bring_existing_to_front():
    try:
        u = ctypes.windll.user32
        hwnd = u.FindWindowW(None, C.CONFIG_TITLE)
        if hwnd:
            u.ShowWindow(hwnd, 9)
            u.SetForegroundWindow(hwnd)
    except Exception:
        pass


if __name__ == "__main__":
    _h, already = C.create_mutex(C.CONFIG_MUTEX)
    if already:
        bring_existing_to_front()
        sys.exit(0)
    ConfigApp().run()

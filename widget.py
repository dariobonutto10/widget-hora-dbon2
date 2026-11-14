"""
Widget Hora: hora, fecha y clima sobre el escritorio de Windows 11.
Lee su configuración de %APPDATA%\\WidgetHora\\config.json y se actualiza solo
cuando la aplicación "Widget Hora Config" guarda cambios.
"""
import ctypes
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

import common as C

KEY = "#010101"  # color que se vuelve transparente
ORDER = ("time", "date", "weather", "city")


class Widget:
    def __init__(self):
        C.set_dpi_aware()
        self.cfg = C.load_cfg()
        self.cfg_mtime = C.cfg_mtime()

        self.root = tk.Tk()
        self.root.title(C.APP)
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)

        self.canvas = tk.Canvas(self.root, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.text = {"time": "", "date": "", "weather": "Cargando clima…", "city": ""}
        self.items = {n: (self.canvas.create_text(0, 0, text="", anchor="nw"),
                          self.canvas.create_text(0, 0, text="", anchor="nw")) for n in ORDER}
        self.fonts = {}
        self.size = (0, 0)
        self.min_w = 0

        # estado del clima
        self.wx_busy = False
        self.wx_result = None
        self.next_wx = 0.0
        self.force_loc = False

        self._build_menu()
        for ev, fn in (("<ButtonPress-1>", self._start_drag), ("<B1-Motion>", self._drag),
                       ("<ButtonRelease-1>", self._end_drag), ("<Button-3>", self._popup)):
            self.canvas.bind(ev, fn)

        self.apply_cfg()
        self.root.update_idletasks()
        self._apply_window_styles()
        self.keep_z_order()
        self.tick()

    # ------------------------------------------------------------ configuración
    def _loc_key(self):
        c = self.cfg
        return (c["location_mode"], c["lat"], c["lon"], c["city"], c["units"])

    def apply_cfg(self):
        c = self.cfg
        weight = "bold" if c["bold"] else "normal"
        fam = c["font"]
        self.fonts = {
            "time": tkfont.Font(family=fam, size=c["size_time"], weight=weight),
            "date": tkfont.Font(family=fam, size=c["size_date"], weight=weight),
            "weather": tkfont.Font(family=fam, size=c["size_weather"], weight=weight),
            "city": tkfont.Font(family=fam, size=max(8, round(c["size_weather"] * 0.7)), weight=weight),
        }
        self.root.attributes("-alpha", c["opacity"] / 100)
        self.min_w = 0
        self.last_text_time = None
        self.relayout(force=True)

    def reload_cfg_if_changed(self):
        m = C.cfg_mtime()
        if m == self.cfg_mtime:
            return
        self.cfg_mtime = m
        old_key = self._loc_key()
        self.cfg = C.load_cfg()
        self.apply_cfg()
        if self._loc_key() != old_key:
            self.force_loc = True
            self.next_wx = 0.0

    # ------------------------------------------------------------ dibujo
    def _visible(self, n):
        c = self.cfg
        if n == "time":
            return True
        if n == "date":
            return c["show_date"]
        if n == "weather":
            return c["show_weather"]
        return c["show_weather"] and c["show_city"] and bool(self.text["city"])

    def relayout(self, force=False):
        c = self.cfg
        d = c["shadow_distance"] if c["shadow"] else 0
        pad = 6 + d
        vis = [n for n in ORDER if self._visible(n)]

        width = max((self.fonts[n].measure(self.text[n]) for n in vis), default=40)
        W = max(width + 2 * pad, self.min_w)
        self.min_w = W

        align = c["align"]
        x = {"left": pad, "center": W / 2, "right": W - pad}.get(align, pad)
        anchor = {"left": "nw", "center": "n", "right": "ne"}.get(align, "nw")

        y = pad
        for n in ORDER:
            shadow, main = self.items[n]
            if n not in vis:
                self.canvas.itemconfig(shadow, state="hidden")
                self.canvas.itemconfig(main, state="hidden")
                continue
            font = self.fonts[n]
            self.canvas.itemconfig(main, text=self.text[n], font=font, fill=c["color"],
                                   anchor=anchor, state="normal")
            self.canvas.coords(main, x, y)
            self.canvas.itemconfig(shadow, text=self.text[n], font=font, fill=c["shadow_color"],
                                   anchor=anchor, state="normal" if c["shadow"] else "hidden")
            self.canvas.coords(shadow, x + d, y + d)
            lh = font.metrics("linespace")
            y += int(lh * 0.88) if n == "time" else lh + 2
        H = int(y + pad)

        if force or (W, H) != self.size:
            self.size = (W, H)
            self.canvas.config(width=W, height=H)
            self.place_window()

    def place_window(self):
        c = self.cfg
        W, H = self.size
        l, t, r, b = C.work_area(self.root)
        m = c["margin"]
        mode = c["pos_mode"]
        if mode == "top-left":
            x, y = l + m, t + m
        elif mode == "bottom-left":
            x, y = l + m, b - H - m
        elif mode == "bottom-right":
            x, y = r - W - m, b - H - m
        elif mode == "center":
            x, y = l + (r - l - W) // 2, t + (b - t - H) // 2
        elif mode == "custom":
            x, y = c["x"], c["y"]
        else:  # top-right
            x, y = r - W - m, t + m
        self.root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")

    # ------------------------------------------------------------ ventana
    def _hwnd(self):
        u = ctypes.windll.user32
        return u.GetParent(self.root.winfo_id()) or self.root.winfo_id()

    def _apply_window_styles(self):
        try:
            u = ctypes.windll.user32
            hwnd = self._hwnd()
            ex = u.GetWindowLongW(hwnd, -20)
            ex |= 0x80          # WS_EX_TOOLWINDOW
            ex &= ~0x40000      # sin WS_EX_APPWINDOW
            u.SetWindowLongW(hwnd, -20, ex)
        except Exception:
            pass

    def keep_z_order(self):
        try:
            u = ctypes.windll.user32
            insert_after = -1 if self.cfg["on_top"] else 1  # HWND_TOPMOST / HWND_BOTTOM
            u.SetWindowPos(self._hwnd(), insert_after, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        except Exception:
            pass
        self.root.after(3000, self.keep_z_order)

    def _start_drag(self, e):
        self._dx, self._dy = e.x, e.y

    def _drag(self, e):
        self.root.geometry(f"+{self.root.winfo_x() + e.x - self._dx}+{self.root.winfo_y() + e.y - self._dy}")

    def _end_drag(self, _e):
        self.cfg = C.update_cfg(pos_mode="custom", x=self.root.winfo_x(), y=self.root.winfo_y())
        self.cfg_mtime = C.cfg_mtime()
        self.keep_z_order()

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Configuración…", command=self.open_config)
        self.menu.add_command(label="Actualizar clima ahora", command=self.force_refresh)
        self.menu.add_separator()
        self.menu.add_command(label="Salir", command=self.root.destroy)

    def _popup(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def open_config(self):
        try:
            subprocess.Popen(C.config_cmd(), cwd=C.APP_DIR, close_fds=True)
        except Exception:
            pass

    def force_refresh(self):
        self.force_loc = True
        self.next_wx = 0.0

    # ------------------------------------------------------------ clima (hilo aparte)
    def _weather_worker(self, cfg, force):
        try:
            lat, lon, name, _src = C.resolve_location(cfg, force)
            temp, feels, code = C.fetch_weather(lat, lon, cfg["units"])
            desc, emoji = C.WMO.get(code, ("—", "🌡️"))
            u = "°F" if cfg["units"] == "F" else "°C"
            self.wx_result = (f"{emoji}  {round(temp)}{u}  ·  {desc}",
                              f"{name}  ·  Sensación {round(feels)}{u}", True)
        except Exception:
            self.wx_result = ("Sin conexión al clima", "Reintentando en un minuto…", False)

    def _start_weather(self):
        self.wx_busy = True
        force, self.force_loc = self.force_loc, False
        threading.Thread(target=self._weather_worker, args=(dict(self.cfg), force),
                         daemon=True).start()

    # ------------------------------------------------------------ bucle principal
    def tick(self):
        now = datetime.now()
        self.reload_cfg_if_changed()

        if self.wx_result is not None:
            line, sub, ok = self.wx_result
            self.wx_result = None
            self.wx_busy = False
            self.text["weather"], self.text["city"] = line, sub
            minutes = self.cfg["update_minutes"]
            self.next_wx = time.monotonic() + (minutes * 60 if ok else 60)
            self.relayout()
        elif not self.wx_busy and time.monotonic() >= self.next_wx:
            self._start_weather()

        t = C.format_time(now, self.cfg["h24"], self.cfg["show_seconds"])
        d = C.format_date(now, self.cfg["date_format"])
        if t != self.text["time"] or d != self.text["date"]:
            self.text["time"], self.text["date"] = t, d
            self.relayout()

        self.root.after(max(50, 1000 - now.microsecond // 1000), self.tick)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    _h, already = C.create_mutex(C.WIDGET_MUTEX)
    if already:
        sys.exit(0)
    Widget().run()

"""
Widget Hora: hora, fecha y clima sobre el escritorio de Windows 11.
Lee su configuración de %APPDATA%\\WidgetHora\\config.json y se actualiza solo
cuando la aplicación "Widget Hora Config" guarda cambios.
El dibujo (con sombra difuminada) lo hace render.py; la ventana usa transparencia por píxel.
"""
import ctypes
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime

import common as C
import render as R


class Widget:
    def __init__(self):
        C.set_dpi_aware()
        self.cfg = C.load_cfg()
        self.cfg_mtime = C.cfg_mtime()

        self.root = tk.Tk()
        self.root.title(C.APP)
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        self.root.withdraw()
        self.root.update_idletasks()

        u = ctypes.windll.user32
        self.hwnd = u.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        ex = u.GetWindowLongW(self.hwnd, -20)
        ex |= 0x80000 | 0x80       # WS_EX_LAYERED | WS_EX_TOOLWINDOW
        ex &= ~0x40000             # sin WS_EX_APPWINDOW
        u.SetWindowLongW(self.hwnd, -20, ex)

        try:
            dpi = int(u.GetDpiForSystem())
        except Exception:
            dpi = int(self.root.winfo_fpixels("1i"))
        self.scale = dpi / 72.0

        self.text = {"time": "", "date": "", "weather": "Cargando clima…", "city": ""}
        self.emoji = ""
        self.min_w = 0
        self.dragging = False

        # estado del clima
        self.wx_busy = False
        self.wx_result = None
        self.next_wx = 0.0
        self.force_loc = False

        self._build_menu()
        for ev, fn in (("<ButtonPress-1>", self._start_drag), ("<B1-Motion>", self._drag),
                       ("<ButtonRelease-1>", self._end_drag), ("<Button-3>", self._popup)):
            self.root.bind(ev, fn)

        self._update_clock_text(datetime.now())
        self.redraw()
        self.root.deiconify()
        self.redraw()
        self.keep_z_order()
        self.tick()

    # ------------------------------------------------------------ configuración
    def _loc_key(self):
        c = self.cfg
        return (c["location_mode"], c["lat"], c["lon"], c["city"], c["units"])

    def reload_cfg_if_changed(self):
        m = C.cfg_mtime()
        if m == self.cfg_mtime:
            return
        self.cfg_mtime = m
        old_key = self._loc_key()
        self.cfg = C.load_cfg()
        self.min_w = 0
        self.redraw()
        if self._loc_key() != old_key:
            self.force_loc = True
            self.next_wx = 0.0

    # ------------------------------------------------------------ dibujo
    def _position(self, W, H):
        c = self.cfg
        if self.dragging:
            return self.root.winfo_x(), self.root.winfo_y()
        l, t, r, b = C.work_area(self.root)
        m = c["margin"]
        mode = c["pos_mode"]
        if mode == "top-left":
            return l + m, t + m
        if mode == "bottom-left":
            return l + m, b - H - m
        if mode == "bottom-right":
            return r - W - m, b - H - m
        if mode == "center":
            return l + (r - l - W) // 2, t + (b - t - H) // 2
        if mode == "custom":
            return c["x"], c["y"]
        return r - W - m, t + m  # top-right

    def redraw(self):
        try:
            img = R.render(self.cfg, self.text, self.emoji, self.scale, self.min_w)
            self.min_w = img.width
            W, H = img.size
            x, y = self._position(W, H)
            self.root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")
            self.root.update_idletasks()
            R.present(self.hwnd, img)
        except Exception:
            C.log_error()

    def keep_z_order(self):
        try:
            u = ctypes.windll.user32
            insert_after = -1 if self.cfg["on_top"] else 1  # HWND_TOPMOST / HWND_BOTTOM
            u.SetWindowPos(self.hwnd, insert_after, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        except Exception:
            pass
        self.root.after(3000, self.keep_z_order)

    # ------------------------------------------------------------ arrastre y menú
    def _start_drag(self, e):
        self.dragging = True
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _end_drag(self, _e):
        self.dragging = False
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
            C.log_error()

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
            self.wx_result = (emoji, f"{round(temp)}{u}  ·  {desc}",
                              f"{name}  ·  Sensación {round(feels)}{u}", True)
        except Exception:
            self.wx_result = ("", "Sin conexión al clima", "Reintentando en un minuto…", False)

    def _start_weather(self):
        self.wx_busy = True
        force, self.force_loc = self.force_loc, False
        threading.Thread(target=self._weather_worker, args=(dict(self.cfg), force),
                         daemon=True).start()

    # ------------------------------------------------------------ bucle principal
    def _update_clock_text(self, now):
        t = C.format_time(now, self.cfg["h24"], self.cfg["show_seconds"])
        d = C.format_date(now, self.cfg["date_format"])
        changed = (t != self.text["time"] or d != self.text["date"])
        self.text["time"], self.text["date"] = t, d
        return changed

    def tick(self):
        now = datetime.now()
        self.reload_cfg_if_changed()
        dirty = False

        if self.wx_result is not None:
            icon, line, sub, ok = self.wx_result
            self.wx_result = None
            self.wx_busy = False
            self.emoji, self.text["weather"], self.text["city"] = icon, line, sub
            minutes = self.cfg["update_minutes"]
            self.next_wx = time.monotonic() + (minutes * 60 if ok else 60)
            dirty = True
        elif not self.wx_busy and time.monotonic() >= self.next_wx:
            self._start_weather()

        if self._update_clock_text(now):
            dirty = True
        if dirty:
            self.redraw()

        self.root.after(max(50, 1000 - now.microsecond // 1000), self.tick)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    _h, already = C.create_mutex(C.WIDGET_MUTEX)
    if already:
        sys.exit(0)
    try:
        Widget().run()
    except Exception:
        C.log_error()
        raise

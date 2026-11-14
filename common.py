"""
Código compartido entre el widget (widget.py) y la aplicación de configuración (config_app.py).
La configuración se guarda en:  %APPDATA%\\WidgetHora\\config.json
"""
import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

APP = "WidgetHora"
WIDGET_EXE = "Widget Hora.exe"
CONFIG_EXE = "Widget Hora Config.exe"
WIDGET_MUTEX = "Local\\WidgetHoraMutex"
CONFIG_MUTEX = "Local\\WidgetHoraConfigMutex"
CONFIG_TITLE = "Widget Hora - Configuración"

CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
CFG_FILE = os.path.join(CFG_DIR, "config.json")
CACHE_FILE = os.path.join(CFG_DIR, "location_cache.json")
NO_WINDOW = 0x08000000

FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

WMO = {
    0: ("Despejado", "☀️"), 1: ("Mayormente despejado", "🌤️"),
    2: ("Parcialmente nublado", "⛅"), 3: ("Nublado", "☁️"),
    45: ("Niebla", "🌫️"), 48: ("Niebla con escarcha", "🌫️"),
    51: ("Llovizna ligera", "🌦️"), 53: ("Llovizna", "🌦️"), 55: ("Llovizna intensa", "🌧️"),
    56: ("Llovizna helada", "🌧️"), 57: ("Llovizna helada", "🌧️"),
    61: ("Lluvia ligera", "🌦️"), 63: ("Lluvia", "🌧️"), 65: ("Lluvia fuerte", "🌧️"),
    66: ("Lluvia helada", "🌧️"), 67: ("Lluvia helada", "🌧️"),
    71: ("Nieve ligera", "🌨️"), 73: ("Nieve", "🌨️"), 75: ("Nieve fuerte", "❄️"),
    77: ("Granizo fino", "🌨️"),
    80: ("Chubascos ligeros", "🌦️"), 81: ("Chubascos", "🌧️"), 82: ("Chubascos fuertes", "⛈️"),
    85: ("Chubascos de nieve", "🌨️"), 86: ("Chubascos de nieve", "🌨️"),
    95: ("Tormenta", "⛈️"), 96: ("Tormenta con granizo", "⛈️"), 99: ("Tormenta con granizo", "⛈️"),
}

DEFAULTS = {
    # ubicación / clima
    "location_mode": "windows",   # "windows" | "manual"
    "city": "", "lat": None, "lon": None,   # solo se usan en modo manual
    "units": "C",                 # "C" | "F"
    "update_minutes": 15,
    # apariencia
    "font": "Segoe UI Light", "bold": False,
    "size_time": 66, "size_date": 20, "size_weather": 17,
    "color": "#FFFFFF",
    "shadow": True, "shadow_distance": 2, "shadow_color": "#101010",
    "shadow_thickness": 1,        # grosor (px)
    "shadow_blur": 6,             # difuminado (0 = sombra dura)
    "shadow_opacity": 85,         # intensidad (%)
    "opacity": 100,
    "align": "left",              # left | center | right
    "show_date": True, "show_weather": True, "show_city": True,
    "date_format": "largo", "h24": True, "show_seconds": False,
    # posición
    "pos_mode": "top-right",      # custom | top-left | top-right | bottom-left | bottom-right | center
    "margin": 40, "x": 100, "y": 60,
    # general
    "on_top": False,
}

LIMITS = {"size_time": (10, 300), "size_date": (8, 150), "size_weather": (8, 150),
          "shadow_distance": (0, 20), "shadow_thickness": (0, 10),
          "shadow_blur": (0, 30), "shadow_opacity": (0, 100), "opacity": (20, 100), "margin": (0, 1000),
          "update_minutes": (5, 180), "x": (-10000, 20000), "y": (-10000, 20000)}

DATE_FORMATS = ["largo", "corto", "medio", "numerico", "iso"]


# ------------------------------------------------------------ configuración
def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if k in DEFAULTS:
                cfg[k] = v
    except Exception:
        pass
    for k, d in DEFAULTS.items():
        if isinstance(d, bool):
            cfg[k] = bool(cfg[k])
        elif isinstance(d, int):
            try:
                cfg[k] = int(cfg[k])
            except Exception:
                cfg[k] = d
    for k, (lo, hi) in LIMITS.items():
        cfg[k] = max(lo, min(hi, cfg[k]))
    return cfg


def save_cfg(cfg):
    os.makedirs(CFG_DIR, exist_ok=True)
    tmp = CFG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CFG_FILE)


def update_cfg(**changes):
    cfg = load_cfg()
    cfg.update(changes)
    save_cfg(cfg)
    return cfg


def cfg_mtime():
    try:
        return os.path.getmtime(CFG_FILE)
    except OSError:
        return 0.0


def log_error():
    """Guarda el último error en %APPDATA%\\WidgetHora\\error.log (ayuda a diagnosticar)."""
    try:
        import traceback
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(os.path.join(CFG_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(datetime.now().isoformat() + "\n" + traceback.format_exc() + "\n")
    except Exception:
        pass


# ------------------------------------------------------------ formato
def format_time(now, h24=True, seconds=False):
    if h24:
        return now.strftime("%H:%M:%S" if seconds else "%H:%M")
    h = now.hour % 12 or 12
    s = f"{h}:{now.minute:02d}" + (f":{now.second:02d}" if seconds else "")
    return s + (" a. m." if now.hour < 12 else " p. m.")


def format_date(now, key="largo"):
    d, m = DIAS[now.weekday()], MESES[now.month - 1]
    if key == "corto":
        return f"{d.capitalize()} {now.day} de {m}"
    if key == "medio":
        return f"{d[:3].capitalize()} {now.day} {m[:3]} {now.year}"
    if key == "numerico":
        return now.strftime("%d/%m/%Y")
    if key == "iso":
        return now.strftime("%Y-%m-%d")
    return f"{d.capitalize()}, {now.day} de {m} de {now.year}"


# ------------------------------------------------------------ sistema Windows
def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def create_mutex(name):
    """Devuelve (handle, ya_existia)."""
    try:
        k = ctypes.windll.kernel32
        k.CreateMutexW.restype = ctypes.c_void_p
        h = k.CreateMutexW(None, False, name)
        return h, k.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return None, False


def mutex_exists(name):
    try:
        k = ctypes.windll.kernel32
        k.OpenMutexW.restype = ctypes.c_void_p
        h = k.OpenMutexW(0x00100000, False, name)  # SYNCHRONIZE
        if h:
            k.CloseHandle(ctypes.c_void_p(h))
            return True
    except Exception:
        pass
    return False


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def work_area(root):
    """Área de trabajo (pantalla sin la barra de tareas): left, top, right, bottom."""
    try:
        r = _RECT()
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0):  # SPI_GETWORKAREA
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def _pythonw():
    exe = sys.executable
    w = exe.replace("python.exe", "pythonw.exe")
    return w if os.path.exists(w) else exe


def widget_cmd():
    if FROZEN:
        return [os.path.join(APP_DIR, WIDGET_EXE)]
    return [_pythonw(), os.path.join(APP_DIR, "widget.py")]


def config_cmd():
    if FROZEN:
        return [os.path.join(APP_DIR, CONFIG_EXE)]
    return [_pythonw(), os.path.join(APP_DIR, "config_app.py")]


def start_widget():
    subprocess.Popen(widget_cmd(), cwd=APP_DIR, close_fds=True)


def stop_widget():
    subprocess.run(["taskkill", "/F", "/IM", WIDGET_EXE], creationflags=NO_WINDOW,
                   capture_output=True)


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_autostart():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except Exception:
        return False


def set_autostart(enable):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                cmd = " ".join(f'"{p}"' for p in widget_cmd())
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, APP)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


# ------------------------------------------------------------ red / ubicación / clima
def http_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP}/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


_PS_LOCATION = r"""
Add-Type -AssemblyName System.Device
$w = New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::Default)
$null = $w.TryStart($false, [TimeSpan]::FromSeconds(8))
$p = $w.Position.Location
if (-not $p.IsUnknown) {
  $c = [System.Globalization.CultureInfo]::InvariantCulture
  "{0};{1}" -f $p.Latitude.ToString($c), $p.Longitude.ToString($c)
}
"""


def windows_location():
    """Ubicación del servicio de ubicación de Windows. Devuelve (lat, lon) o None."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", _PS_LOCATION],
            capture_output=True, text=True, timeout=25, creationflags=NO_WINDOW)
        txt = out.stdout.strip()
        if ";" in txt:
            lat, lon = txt.splitlines()[-1].split(";")
            return float(lat), float(lon)
    except Exception:
        pass
    return None


def ip_location():
    try:
        d = http_json("https://ipapi.co/json/")
        return float(d["latitude"]), float(d["longitude"]), d.get("city", "")
    except Exception:
        return None


def reverse_name(lat, lon):
    try:
        d = http_json("https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10"
                      f"&accept-language=es&lat={lat}&lon={lon}")
        a = d.get("address", {})
        for k in ("city", "town", "village", "municipality", "county", "state"):
            if a.get(k):
                return a[k]
    except Exception:
        pass
    return f"{lat:.2f}, {lon:.2f}"


def geocode_search(query, count=6):
    q = urllib.parse.quote(query)
    d = http_json(f"https://geocoding-api.open-meteo.com/v1/search?count={count}&language=es&name={q}")
    res = []
    for r in d.get("results", []):
        parts = [r.get("name", ""), r.get("admin1", ""), r.get("country", "")]
        label = ", ".join(p for p in parts if p)
        res.append({"label": label, "name": r["name"],
                    "lat": float(r["latitude"]), "lon": float(r["longitude"])})
    return res


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(lat, lon, name, source):
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"lat": lat, "lon": lon, "name": name, "source": source,
                       "ts": time.time()}, f, ensure_ascii=False)
    except Exception:
        pass


def resolve_location(cfg, force=False):
    """Devuelve (lat, lon, nombre, origen). Lanza excepción si no hay ubicación."""
    if cfg["location_mode"] == "manual" and cfg["lat"] is not None:
        return cfg["lat"], cfg["lon"], cfg["city"], "manual"

    cache = _load_cache()
    if cache and not force and time.time() - cache.get("ts", 0) < 3600:
        return cache["lat"], cache["lon"], cache["name"], cache["source"]

    loc = windows_location()
    if loc:
        lat, lon = loc
        name = reverse_name(lat, lon)
        _save_cache(lat, lon, name, "windows")
        return lat, lon, name, "windows"

    ip = ip_location()
    if ip:
        lat, lon, city = ip
        name = city or reverse_name(lat, lon)
        _save_cache(lat, lon, name, "ip")
        return lat, lon, name, "ip"

    if cache:
        return cache["lat"], cache["lon"], cache["name"], cache["source"]
    raise RuntimeError("Sin ubicación")


def fetch_weather(lat, lon, units="C"):
    unit = "&temperature_unit=fahrenheit" if units == "F" else ""
    d = http_json("https://api.open-meteo.com/v1/forecast"
                  f"?latitude={lat}&longitude={lon}"
                  "&current=temperature_2m,apparent_temperature,weather_code"
                  f"&timezone=auto{unit}")
    c = d["current"]
    return c["temperature_2m"], c["apparent_temperature"], int(c["weather_code"])

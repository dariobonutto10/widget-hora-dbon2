"""
Dibujo del widget con Pillow y presentación en Windows con transparencia por píxel
(UpdateLayeredWindow). Esto permite una sombra realmente difuminada.
"""
import ctypes
import os
from ctypes import POINTER, Structure, byref, c_long, c_ubyte, c_uint, c_uint32, c_void_p, c_ushort, sizeof

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ------------------------------------------------------------ fuentes
_table = None
_cache = {}


def _fonts_dir():
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _load_table():
    """Lee del registro de Windows: nombre de fuente -> archivo."""
    global _table
    if _table is not None:
        return _table
    _table = {}
    try:
        import winreg
        sub = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key = winreg.OpenKey(root, sub)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    name, val, _t = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                base = name.replace(" (TrueType)", "").replace(" (OpenType)", "")
                path = val if os.path.isabs(val) else os.path.join(_fonts_dir(), val)
                for part in base.split(" & "):
                    _table[part.strip().lower()] = path
    except Exception:
        pass
    return _table


def find_font_file(family, bold):
    """Devuelve (ruta, es_variante_negrita)."""
    t = _load_table()
    fam = family.strip().lower()
    if bold and (fam + " bold") in t:
        return t[fam + " bold"], True
    if fam in t:
        return t[fam], False
    for fallback in ("segoe ui", "arial"):
        if fallback in t:
            return t[fallback], False
    return None, False


def get_font(path, size):
    key = (path, size)
    if key in _cache:
        return _cache[key]
    font = None
    if path:
        try:
            font = ImageFont.truetype(path, size)
        except Exception:
            font = None
    if font is None:
        for cand in ("DejaVuSans.ttf", "arial.ttf"):
            try:
                font = ImageFont.truetype(cand, size)
                break
            except Exception:
                pass
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except TypeError:
            font = ImageFont.load_default()
    _cache[key] = font
    return font


def _emoji_font_path():
    t = _load_table()
    p = t.get("segoe ui emoji") or os.path.join(_fonts_dir(), "seguiemj.ttf")
    return p if os.path.exists(p) else None


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    if len(h) != 6:
        return (255, 255, 255)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------ dibujo
def render(cfg, text, emoji, scale, min_w=0):
    """
    Devuelve una imagen RGBA con texto + sombra difuminada.
    scale = píxeles por punto (DPI / 72).
    """
    k = scale * 0.75                      # 1.0 a 100 % de escala de Windows
    px = lambda pt: max(6, round(pt * scale))
    path, has_bold = find_font_file(cfg["font"], cfg["bold"])
    faux = cfg["bold"] and not has_bold

    sizes = {"time": px(cfg["size_time"]), "date": px(cfg["size_date"]),
             "weather": px(cfg["size_weather"]), "city": px(max(8, cfg["size_weather"] * 0.7))}
    fonts = {n: get_font(path, s) for n, s in sizes.items()}

    emoji = (emoji or "").replace("\ufe0f", "")
    epath = _emoji_font_path() if emoji else None
    efont = get_font(epath, sizes["weather"]) if epath else None
    if not efont:
        emoji = ""

    shadow = cfg["shadow"]
    d = round(cfg["shadow_distance"] * k) if shadow else 0
    thick = round(cfg["shadow_thickness"] * k) if shadow else 0
    blur = cfg["shadow_blur"] * k if shadow else 0
    pad = round(6 * k) + (d + thick + int(3 * blur) if shadow else 0) + 2

    vis = ["time"]
    if cfg["show_date"]:
        vis.append("date")
    if cfg["show_weather"]:
        vis.append("weather")
        if cfg["show_city"] and text.get("city"):
            vis.append("city")

    gap = round(sizes["weather"] * 0.35)

    def line_w(n):
        w = fonts[n].getlength(text[n])
        if n == "weather" and emoji:
            w += efont.getlength(emoji) + gap
        return w

    widths = {n: line_w(n) for n in vis}
    W = max(int(max(widths.values()) + 2 * pad), min_w)

    # posición vertical de cada línea
    ys, y = {}, pad
    for n in vis:
        asc, desc = fonts[n].getmetrics()
        lh = asc + desc
        ys[n] = y + asc
        y += int(lh * 0.9) if n == "time" else lh + round(2 * k)
    H = int(y + pad)

    color = _rgb(cfg["color"])
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    sw = max(1, round(sizes["time"] / 45)) if faux else 0

    for n in vis:
        w = widths[n]
        x = {"left": pad, "center": (W - w) / 2, "right": W - pad - w}.get(cfg["align"], pad)
        base = ys[n]
        tx = x
        if n == "weather" and emoji:
            try:
                td.text((x, base), emoji, font=efont, anchor="ls", embedded_color=True)
            except Exception:
                pass
            if shadow:
                try:
                    md.text((x + d, base + d), emoji, font=efont, anchor="ls", fill=255, stroke_width=thick)
                except Exception:
                    pass
            tx = x + efont.getlength(emoji) + gap
        td.text((tx, base), text[n], font=fonts[n], anchor="ls", fill=color + (255,),
                stroke_width=sw, stroke_fill=color + (255,))
        if shadow:
            md.text((tx + d, base + d), text[n], font=fonts[n], anchor="ls", fill=255,
                    stroke_width=thick + sw, stroke_fill=255)

    if shadow:
        if blur > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        op = cfg["shadow_opacity"]
        mask = mask.point(lambda v: v * op // 100)
        layer = Image.new("RGBA", (W, H), _rgb(cfg["shadow_color"]) + (0,))
        layer.putalpha(mask)
        out = Image.alpha_composite(layer, text_layer)
    else:
        out = text_layer

    # opacidad general del widget
    if cfg["opacity"] < 100:
        a = out.getchannel("A").point(lambda v: v * cfg["opacity"] // 100)
        out.putalpha(a)
    return out


# ------------------------------------------------------------ presentación (Win32)
class _BIH(Structure):
    _fields_ = [("biSize", c_uint32), ("biWidth", c_long), ("biHeight", c_long),
                ("biPlanes", c_ushort), ("biBitCount", c_ushort), ("biCompression", c_uint32),
                ("biSizeImage", c_uint32), ("biXPelsPerMeter", c_long), ("biYPelsPerMeter", c_long),
                ("biClrUsed", c_uint32), ("biClrImportant", c_uint32)]


class _BMI(Structure):
    _fields_ = [("bmiHeader", _BIH), ("bmiColors", c_uint32 * 3)]


class _BLEND(Structure):
    _fields_ = [("BlendOp", c_ubyte), ("BlendFlags", c_ubyte),
                ("SourceConstantAlpha", c_ubyte), ("AlphaFormat", c_ubyte)]


class _POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]


class _SIZE(Structure):
    _fields_ = [("cx", c_long), ("cy", c_long)]


_ready = False


def _setup():
    global _ready
    if _ready:
        return
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.GetDC.argtypes = [c_void_p]
    u.GetDC.restype = c_void_p
    u.ReleaseDC.argtypes = [c_void_p, c_void_p]
    u.UpdateLayeredWindow.argtypes = [c_void_p, c_void_p, POINTER(_POINT), POINTER(_SIZE), c_void_p,
                                      POINTER(_POINT), c_uint32, POINTER(_BLEND), c_uint32]
    g.CreateCompatibleDC.argtypes = [c_void_p]
    g.CreateCompatibleDC.restype = c_void_p
    g.CreateDIBSection.argtypes = [c_void_p, POINTER(_BMI), c_uint, POINTER(c_void_p), c_void_p, c_uint32]
    g.CreateDIBSection.restype = c_void_p
    g.SelectObject.argtypes = [c_void_p, c_void_p]
    g.SelectObject.restype = c_void_p
    g.DeleteObject.argtypes = [c_void_p]
    g.DeleteDC.argtypes = [c_void_p]
    _ready = True


def _to_bgra_premultiplied(img):
    r, g, b, a = img.split()
    r, g, b = ImageChops.multiply(r, a), ImageChops.multiply(g, a), ImageChops.multiply(b, a)
    # alpha mínimo 1: así el fondo "invisible" sigue recibiendo clics para poder arrastrar
    a = a.point(lambda v: v if v else 1)
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


def present(hwnd, img):
    """Muestra la imagen RGBA en la ventana (que debe tener WS_EX_LAYERED)."""
    _setup()
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    W, H = img.size
    data = _to_bgra_premultiplied(img)

    hdc_screen = u.GetDC(None)
    hdc_mem = g.CreateCompatibleDC(hdc_screen)
    bmi = _BMI()
    bmi.bmiHeader.biSize = sizeof(_BIH)
    bmi.bmiHeader.biWidth = W
    bmi.bmiHeader.biHeight = -H            # imagen de arriba hacia abajo
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0        # BI_RGB
    bits = c_void_p()
    hbmp = g.CreateDIBSection(hdc_screen, byref(bmi), 0, byref(bits), None, 0)
    try:
        ctypes.memmove(bits.value, data, len(data))
        old = g.SelectObject(hdc_mem, hbmp)
        size, src = _SIZE(W, H), _POINT(0, 0)
        blend = _BLEND(0, 0, 255, 1)       # AC_SRC_OVER, alfa por píxel
        u.UpdateLayeredWindow(hwnd, hdc_screen, None, byref(size), hdc_mem, byref(src),
                              0, byref(blend), 2)  # ULW_ALPHA
        g.SelectObject(hdc_mem, old)
    finally:
        g.DeleteObject(hbmp)
        g.DeleteDC(hdc_mem)
        u.ReleaseDC(None, hdc_screen)

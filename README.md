# Widget Hora

Widget de escritorio para Windows 11 con **hora, fecha y clima**, pensado para usarse junto con tu fondo de pantalla.

- Se instala sin permisos de administrador y **se inicia solo con Windows**.
- No interfiere con el cambio de fondos de pantalla (se queda detrás de tus ventanas).
- El clima usa la **ubicación de Windows** (con respaldo por IP) o la ciudad que elijas.
- Aplicación de configuración aparte: fuente, tamaños, color, sombra, opacidad, alineación, posición, formato de fecha y más. Los cambios se aplican al instante.

## Descargar el instalador

1. Ve a la pestaña **Releases** y descarga `Widget_Hora_Setup.exe`
   (o, en **Actions**, abre la última ejecución verde y baja el artefacto *Widget_Hora_Setup*).
2. Ejecútalo. Si SmartScreen avisa: **Más información → Ejecutar de todos modos** (el programa no está firmado).
3. Para ajustar el widget: menú Inicio → **Widget Hora - Configuración**, o clic derecho sobre el widget → *Configuración…*

## Cómo se compila (automático)

GitHub Actions compila todo en un servidor Windows (`.github/workflows/build.yml`):
PyInstaller crea `Widget Hora.exe` y `Widget Hora Config.exe`, e Inno Setup crea el instalador.

- **Compilar a mano:** pestaña *Actions* → *Crear Widget Hora* → *Run workflow*.
- **Publicar una versión:** *Releases* → *Draft a new release* → crea la etiqueta `v2.0` → *Publish*.
  El instalador se adjunta solo a la Release en unos minutos.

## Compilar en tu PC (opcional)

Requisitos: Python 3 (con "Add to PATH") e Inno Setup 6. Ejecuta `build.bat`;
el instalador queda en `installer\Widget_Hora_Setup.exe`.

## Archivos

| Archivo | Función |
|---|---|
| `widget.py` | El widget |
| `config_app.py` | Ventana de configuración |
| `common.py` | Código compartido (configuración, ubicación, clima) |
| `installer.iss` | Script del instalador (Inno Setup) |
| `build.bat` | Compilación local |
| `icon.ico`, `icon_config.ico` | Iconos |

La configuración del usuario se guarda en `%APPDATA%\WidgetHora\config.json`.

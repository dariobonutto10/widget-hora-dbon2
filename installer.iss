[Setup]
AppName=Widget Hora
AppVersion=2.0
AppPublisher=Widget Hora
DefaultDirName={autopf}\Widget Hora
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=Widget_Hora_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayName=Widget Hora
UninstallDisplayIcon={app}\Widget Hora.exe
CloseApplications=force

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\Widget Hora.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Widget Hora Config.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon_config.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Widget Hora"; Filename: "{app}\Widget Hora.exe"
Name: "{userprograms}\Widget Hora - Configuración"; Filename: "{app}\Widget Hora Config.exe"; IconFilename: "{app}\icon_config.ico"

[Registry]
; Inicio automático con Windows (solo usuario actual, sin permisos de administrador)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "WidgetHora"; \
  ValueData: """{app}\Widget Hora.exe"""; Flags: uninsdeletevalue
; Limpia la entrada de la versión anterior, si existía
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueName: "ClockWidget"; Flags: deletevalue

[Run]
Filename: "{app}\Widget Hora.exe"; Description: "Iniciar el widget ahora"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Widget Hora Config.exe"; Description: "Abrir la configuración"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM ""Widget Hora.exe"""; Flags: runhidden; RunOnceId: "KillWidget"
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM ""Widget Hora Config.exe"""; Flags: runhidden; RunOnceId: "KillConfig"

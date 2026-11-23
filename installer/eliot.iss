; Installateur ELIOT (Inno Setup 6 : https://jrsoftware.org/isinfo.php)
; Compiler apres build_exe.bat : clic droit > Compile, ou iscc installer\eliot.iss
#define AppName "ELIOT"
#define AppVersion "1.0.0"

[Setup]
AppId={{6B0E7C5D-2E4B-4C1A-9E0E-E1107A55157A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ELIOT (projet prive)
DefaultDirName={localappdata}\Programs\ELIOT
DefaultGroupName=ELIOT
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ELIOT-Setup-{#AppVersion}
SetupIconFile=..\assets\eliot.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ELIOT.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"
Name: "startup"; Description: "Lancer ELIOT au demarrage de Windows (Hey Eliot et rappels toujours actifs)"; GroupDescription: "Demarrage :"

[Files]
Source: "..\dist\ELIOT\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\ELIOT"; Filename: "{app}\ELIOT.exe"
Name: "{autodesktop}\ELIOT"; Filename: "{app}\ELIOT.exe"; Tasks: desktopicon
Name: "{userstartup}\ELIOT"; Filename: "{app}\ELIOT.exe"; Tasks: startup

[Run]
Filename: "{app}\ELIOT.exe"; Description: "Lancer ELIOT"; Flags: nowait postinstall skipifsilent

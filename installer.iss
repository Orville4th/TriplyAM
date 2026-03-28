[Setup]
AppName=Triply
AppVersion=0.1-beta
AppPublisher=Orville Wright IV
DefaultDirName={autopf}\Triply
DefaultGroupName=Triply
OutputBaseFilename=Triply-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "dist\Triply\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Triply"; Filename: "{app}\Triply.exe"
Name: "{commondesktop}\Triply"; Filename: "{app}\Triply.exe"

[Run]
Filename: "{app}\Triply.exe"; Description: "Launch Triply"; Flags: nowait postinstall skipifsilent

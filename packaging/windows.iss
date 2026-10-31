#define MyAppName "GeCo Desktop"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Zachary Lim"
#define MyAppExeName "GeCo Desktop.exe"

[Setup]
AppId={{A10BE3CF-2DB1-4C1B-A512-778AE98A6261}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\GeCo Desktop
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\native-installers
OutputBaseFilename=GeCoDesktop-Windows-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
Name: "fileassoc"; Description: "Associate GeCo project descriptors (.gecod) with GeCo Desktop"; Flags: unchecked

[Files]
Source: "..\dist-native\GeCo Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Classes\.gecod"; ValueType: string; ValueName: ""; ValueData: "GeCoDesktop.Project"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\GeCoDesktop.Project"; ValueType: string; ValueName: ""; ValueData: "GeCo Desktop project"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\GeCoDesktop.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

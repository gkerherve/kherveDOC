; Inno Setup script for KherveTeX
; Produces a single Setup_KherveTeX.exe installer.
;
; Build steps:
;   1. pyinstaller KherveTeX.spec --noconfirm
;   2. Copy dist\, icon.ico, and this file to a short path (e.g. C:\tmp\kt_build)
;      to avoid Windows MAX_PATH issues with the OneDrive project path.
;   3. Run: ISCC.exe KherveTeX_setup.iss

#define MyAppName "KherveTeX"
#define MyAppPublisher "Gwilherm Kerherve"
#define MyAppURL "https://github.com/gkerherve/kherveDOC"
#define MyAppExeName "KherveTeX.exe"
#define MyAppVersion "0.146"

[Setup]
AppId={{B8A3F2E1-7C4D-4E5F-9A1B-3D6E8F0C2A47}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=Setup_KherveTeX_{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc_ktexz"; Description: "Associate .ktexz files with {#MyAppName}"; GroupDescription: "File associations:"
Name: "fileassoc_kdocz"; Description: "Associate .kdocz files with {#MyAppName}"; GroupDescription: "File associations:"

[Files]
Source: "dist\KherveTeX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; .ktexz file association
Root: HKA; Subkey: "Software\Classes\.ktexz"; ValueType: string; ValueData: "KherveTeX.Document"; Flags: uninsdeletevalue; Tasks: fileassoc_ktexz
Root: HKA; Subkey: "Software\Classes\KherveTeX.Document"; ValueType: string; ValueData: "KherveTeX Document"; Flags: uninsdeletekey; Tasks: fileassoc_ktexz
Root: HKA; Subkey: "Software\Classes\KherveTeX.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: fileassoc_ktexz
Root: HKA; Subkey: "Software\Classes\KherveTeX.Document\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc_ktexz
; .kdocz file association
Root: HKA; Subkey: "Software\Classes\.kdocz"; ValueType: string; ValueData: "KherveTeX.Document"; Flags: uninsdeletevalue; Tasks: fileassoc_kdocz
Root: HKA; Subkey: "Software\Classes\KherveTeX.Document\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc_kdocz

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

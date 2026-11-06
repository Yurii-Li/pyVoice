; Script generated for Inno Setup Compiler
; PyVoice AI - Windows Installer Script

#define MyAppName "PyVoice AI"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "Yurii Liubuskyi"
#define MyAppURL "https://github.com/Yurii-Li/pyVoice"
#define MyAppExeName "PyVoiceAI.exe"

[Setup]
; Унікальний ідентифікатор додатку
AppId={{D37F8E24-8D82-4B6A-98C3-B7C418931234}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Встановлення в папку користувача (НЕ потребує прав адміністратора!)
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

OutputBaseFilename=PyVoiceAI-Setup
OutputDir=dist
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

; Автоматичне закриття попередньої версії під час оновлення
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Без прапорця skipifsilent, щоб нова версія запускалася автоматично навіть при тихому фоновому оновленні!
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall

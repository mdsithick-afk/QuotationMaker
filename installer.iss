[Setup]
AppName=Quotation Maker
AppVersion=1.0
AppPublisher=Quotation Maker
DefaultDirName={autopf}\Quotation Maker
DefaultGroupName=Quotation Maker
OutputDir=Output
OutputBaseFilename=QuotationMaker_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\QuotationMaker.exe

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\QuotationMaker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Quotation Maker"; Filename: "{app}\QuotationMaker.exe"
Name: "{autodesktop}\Quotation Maker"; Filename: "{app}\QuotationMaker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QuotationMaker.exe"; Description: "Launch Quotation Maker"; Flags: nowait postinstall skipifsilent

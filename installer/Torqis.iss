; Instalador do Torqis (Inno Setup 6). Criado pelo build_release.bat.
; Leva tudo o que o programa precisa (Python, Qt, runtime do Visual C++, pontes): o PC da oficina não precisa de
; instalar mais nada nem de internet.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
; Driver FTDI opcional: só entra se o build_release.bat o encontrar em installer\drivers\ftdi
#define FtdiDriver FileExists(AddBackslash(SourcePath) + "drivers\ftdi\ftdibus.inf")

[Setup]
; O AppId fica o mesmo das versões com o nome antigo: o instalador do Torqis actualiza essas instalações (na mesma
; pasta) em vez de instalar um segundo programa ao lado. Os atalhos passam para o grupo novo (UsePreviousGroup=no).
AppId={{6B1E2C3A-9F44-4C1B-A7D2-5E0C8B9A7F10}
AppName=Torqis
AppVersion={#AppVersion}
AppVerName=Torqis {#AppVersion}
AppPublisher=Torqis
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Torqis
DefaultDirName={autopf}\Torqis
DefaultGroupName=Torqis
UsePreviousGroup=no
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Torqis.exe
UninstallDisplayName=Torqis
OutputDir=..\dist
OutputBaseFilename=Setup_Torqis_{#AppVersion}
SetupIconFile=..\rad\assets\icon.ico
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; Só Windows 10/11 de 64 bits: noutros sistemas o instalador explica porquê, em vez de instalar um programa
; que não abriria.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
; Por omissão instala só para o utilizador actual (sem pedir administrador): assim as actualizações automáticas
; correm em silêncio. "Para todos os utilizadores" continua disponível na primeira página (e instala o driver FTDI).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
; Fecha o programa se estiver aberto durante uma actualização.
CloseApplications=yes
SetupLogging=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
pt.DriverStatus=A preparar o Windows para os cabos de diagnóstico...
en.DriverStatus=Preparing Windows for the diagnostic cables...
pt.UninstallLink=Desinstalar Torqis
en.UninstallLink=Uninstall Torqis

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\build\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#if FtdiDriver
; Driver oficial dos cabos com chip FTDI (ver drivers\LEIA-ME.txt). Fica guardado no Windows para que um cabo
; novo seja reconhecido mesmo sem internet; os cabos que já funcionam não são alterados.
Source: "drivers\ftdi\*"; DestDir: "{app}\drivers\ftdi"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

[InstallDelete]
; Instalações com o nome antigo (até à versão 1.21): sai o programa antigo e os seus atalhos, para não ficarem dois
; ícones nem um executável desactualizado na pasta.
Type: files; Name: "{app}\RootsAutoDoctor.exe"
Type: files; Name: "{autodesktop}\Roots Auto Doctor.lnk"
Type: files; Name: "{autoprograms}\Roots Auto Doctor\Roots Auto Doctor.lnk"
Type: files; Name: "{autoprograms}\Roots Auto Doctor\Desinstalar Roots Auto Doctor.lnk"
Type: files; Name: "{autoprograms}\Roots Auto Doctor\Uninstall Roots Auto Doctor.lnk"
Type: dirifempty; Name: "{autoprograms}\Roots Auto Doctor"

[Icons]
Name: "{group}\Torqis"; Filename: "{app}\Torqis.exe"
Name: "{group}\{cm:UninstallLink}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Torqis"; Filename: "{app}\Torqis.exe"; Tasks: desktopicon

[Run]
#if FtdiDriver
; /add-driver sem /install: o driver entra no "armazém de drivers" do Windows e só é usado por cabos que ainda
; não têm driver. Precisa de administrador (instalação para todos os utilizadores).
Filename: "{sys}\pnputil.exe"; Parameters: "/add-driver ""{app}\drivers\ftdi\*.inf"" /subdirs"; Flags: runhidden waituntilterminated; StatusMsg: "{cm:DriverStatus}"; Check: IsAdminInstallMode
#endif
Filename: "{app}\Torqis.exe"; Description: "{cm:LaunchProgram,Torqis}"; Flags: nowait postinstall skipifsilent
; Actualização automática com "Actualizar agora" (/RELAUNCH=1): o programa volta a abrir já actualizado.
Filename: "{app}\Torqis.exe"; Flags: nowait postinstall runasoriginaluser; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;

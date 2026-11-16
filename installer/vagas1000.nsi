; Instalador do vagas1000 (NSIS), por usuário e sem administrador — mesmo desenho do CAM.
; Uso:  makensis /DVERSION=1.0.0 installer\vagas1000.nsi   (depois de `pyinstaller vagas1000.spec`)
; Saída: dist\vagas1000-Setup-<versão>.exe
;
; - Instala em %LOCALAPPDATA%\Programs\vagas1000 (a pasta pode ser trocada no assistente).
; - Atalhos na Área de Trabalho e no Menu Iniciar.
; - Desinstalar NUNCA apaga %APPDATA%\vagas1000 (banco, painel, logs e configuração).

Unicode true
!ifndef VERSION
  !define VERSION "0.0.0"
!endif

!define APPNAME "vagas1000"
!define APPEXE "vagas1000.exe"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\vagas1000"

Name "${APPNAME}"
OutFile "..\dist\vagas1000-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APPNAME}"
InstallDirRegKey HKCU "Software\vagas1000" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"
!define MUI_ICON "..\assets\icon.ico"
!define MUI_UNICON "..\assets\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APPEXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o ${APPNAME}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "PortugueseBR"

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "ProductName" "${APPNAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileDescription" "Instalador do ${APPNAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "LegalCopyright" "Copyright (c) 2026 Natalia Tobias"

Section "Instalar"
  SetOutPath "$INSTDIR"
  File /r "..\dist\vagas1000\*.*"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPEXE}" "" "$INSTDIR\${APPEXE}" 0
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPEXE}" "" "$INSTDIR\${APPEXE}" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Desinstalar.lnk" "$INSTDIR\Desinstalar.exe"

  WriteRegStr HKCU "Software\vagas1000" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "Natalia Tobias"
  WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\${APPEXE}"
  WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "${UNINSTKEY}" "URLInfoAbout" "https://github.com/nataliatobiasdev/vagas-1000"
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTKEY}"
  DeleteRegKey HKCU "Software\vagas1000"
  ; %APPDATA%\vagas1000 fica intacta de propósito: os dados são seus.
SectionEnd

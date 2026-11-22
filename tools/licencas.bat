@echo off
REM Abre a janela das licencas do Torqis (so no PC do fornecedor, onde esta a chave privada).
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" tools\licencas.py

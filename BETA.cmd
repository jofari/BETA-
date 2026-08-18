@echo off
chcp 65001 > nul
title BETA - banc d'essai d'edges
cd /d "%~dp0"
rem Le venv n'est pas force d'etre actif dans le shell : on appelle son interpreteur
rem directement, avec repli sur le python du PATH s'il a demenage.
set BETA_PY=C:\Users\jofar\venvs\arit\Scripts\python.exe
if not exist "%BETA_PY%" set BETA_PY=python
"%BETA_PY%" beta.py serve %*
pause

@echo off
REM Script para iniciar el scheduler de Datakinga
REM Este archivo mantiene el proceso corriendo para ejecutar en horarios programados

echo ===============================================
echo   DATAKINGA - INICIANDO SCHEDULER
echo ===============================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Ejecutar el script en modo scheduler
python run_daily_update.py --schedule

pause

@echo off
title LeadHunter - Extrator de Leads e WhatsApp
cd /d "%~dp0"
echo ========================================================
echo   LEADHUNTER - EXTRATOR DE LEADS GOOGLE MAPS + ZAP
echo ========================================================
echo.
echo Abrindo o painel interativo no seu navegador...
echo.
python -m streamlit run "app.py" --server.headless=false --server.port=8501
pause

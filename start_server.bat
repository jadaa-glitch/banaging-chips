@echo off
title Banaging Chips BI Dashboard Server
cd /d "c:\Users\ADMIN\OneDrive\문서\banaging_chips"
echo Starting Banaging Chips Server...
echo Opening http://localhost:5000 in your browser...
start http://localhost:5000
.\venv\Scripts\python.exe run.py
pause

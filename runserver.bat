@echo off
cd /d C:\IGDP

venv\Scripts\python.exe manage.py runserver 0.0.0.0:8001

pause
@echo off
pip install -r requirements.txt && pip install pyinstaller && pyinstaller -F -y --add-data "config;." gui.py
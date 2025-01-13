#!/bin/bash
pip3 install -r requirements.txt && pip3 install pyinstaller && pyinstaller -F -y --add-data "config:." gui.py
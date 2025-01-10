#!/bin/bash
pip3 install pyinstaller && pyinstaller -F -y --add-data "config:." gui.py
#!/bin/bash
# Start/stop Shark Girl listening from anywhere. Wayland only sends keys to the focused
# window, so for a global Alt+F10 bind this script to it in
# COSMIC Settings > Keyboard > Keyboard shortcuts > Custom shortcuts.
pkill -USR1 -f -- "python -I viewer.py$" || echo "Shark Girl is not running" >&2

#!/bin/bash
# Turn the PC off. Shark Girl runs this for "apaga la pc" / "shut down the pc" once you
# confirm (say "yes"/"sí", or press Run). It waits a few seconds first so she can say
# goodbye. No sudo needed: logind lets the logged-in user power off.
#   poweroff.sh [seconds]    default 5
sleep "${1:-5}"
exec systemctl poweroff

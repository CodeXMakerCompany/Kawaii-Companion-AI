#!/bin/bash
# Launch the transparent Shark Girl overlay. Extra args go to viewer.py (see --help).
#
# She runs detached from the terminal (her own session, no controlling tty), so closing
# the terminal, or a tool that runs this and then ends, cannot take her down with it.
# Starting her again replaces the running copy. Esc on her quits.
# --foreground keeps her attached to this terminal instead (for debugging).
cd "$(dirname "$0")" || exit 1
if [ "$1" = "--foreground" ]; then
    shift
    exec .venv/bin/python -I viewer.py "$@"
fi
log="${XDG_STATE_HOME:-$HOME/.local/state}/shark-viewer.log"
mkdir -p "$(dirname "$log")"
setsid .venv/bin/python -I viewer.py "$@" >>"$log" 2>&1 </dev/null &
echo "Shark Girl is starting (errors go to $log)"

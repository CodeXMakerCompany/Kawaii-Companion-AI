"""Entry point: run.sh starts this file (and voice-toggle.sh finds it by name).
The app itself lives in the kawaii package; see kawaii/cli.py for the controls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run.sh uses python -I, which leaves the script dir off sys.path

from kawaii.cli import parse_args  # noqa: E402


def main():
    args = parse_args()
    from kawaii.app import App  # after argparse, so --help needs no GL or Wayland

    App(args).run()


if __name__ == "__main__":
    main()

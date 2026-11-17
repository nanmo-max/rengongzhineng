"""Official fixed entrypoint copied to ``/app/harness.py``."""
import sys

from contest_harness.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

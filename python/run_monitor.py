"""Run the full exposure monitor: py -3 python/run_monitor.py [--update-readme]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hfexposure.run import main  # noqa: E402

if __name__ == "__main__":
    main()

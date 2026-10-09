import os
import sys

# Vendored tests import their sample-book helper as a top-level module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

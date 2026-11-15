"""Makes data/synthetic/generators.py importable in tests as `generators`."""

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "generators.py"
_spec = importlib.util.spec_from_file_location("generators", _PATH)
generators = importlib.util.module_from_spec(_spec)
sys.modules["generators"] = generators
_spec.loader.exec_module(generators)

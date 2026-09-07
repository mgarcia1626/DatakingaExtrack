"""Compatibility wrapper for legacy entrypoint."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_module("datakinga.apps.pipelines.render_pipeline", run_name="__main__")

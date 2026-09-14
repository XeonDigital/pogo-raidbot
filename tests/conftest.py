import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
formats_py = ROOT / "data" / "formats.py"
formats_example = ROOT / "data" / ".formats.py"
if not formats_py.exists() and formats_example.exists() and "data.formats" not in sys.modules:
    spec = importlib.util.spec_from_file_location("data.formats", formats_example)
    module = importlib.util.module_from_spec(spec)
    sys.modules["data.formats"] = module
    spec.loader.exec_module(module)

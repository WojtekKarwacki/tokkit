import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "py"))
sys.path.insert(0, str(Path(__file__).parent))  # for e2e.benchmark imports

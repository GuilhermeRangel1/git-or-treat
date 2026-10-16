import sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / ".hooks"))
import antigravity_bridge
sys.argv = ["bridge", sys.argv[1] if len(sys.argv) > 1 else ""]
raise SystemExit(antigravity_bridge.main())

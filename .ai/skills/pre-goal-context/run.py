import json
import os
from pathlib import Path

context = json.loads(os.environ["AI_GOAL_CONTEXT"])
root = Path(os.environ["AI_GOAL_ROOT"])

summary = {
    "project": root.name,
    "goal": context.get("goal"),
    "detected": {
        "hasFrontend": (root / "frontend").exists(),
        "hasBackend": (root / "backend").exists(),
        "hasDocs": (root / "docs").exists(),
    }
}

output = Path(__file__).parent / "output.json"
output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print("runtime context prepared")

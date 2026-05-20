import json
import os
import time
from pathlib import Path

context = json.loads(os.environ["AI_GOAL_CONTEXT"])

summary = {
    "goalId": context.get("goalId"),
    "goal": context.get("goal"),
    "status": "running",
    "timestamp": int(time.time() * 1000)
}

output = Path(__file__).parent / "output.json"
output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print("runtime progress captured")

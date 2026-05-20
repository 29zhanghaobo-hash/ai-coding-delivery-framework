#!/usr/bin/env python3
"""
ai-goal: minimal runtime skill wrapper for AI Coding.

MVP scope:
- capture three lifecycle events: pre, run, post
- auto-discover skills from .ai/skills/*/manifest.json
- execute matched skills without manually specifying them during goal execution
- write runtime state into .ai/runtime/events.jsonl and .ai/runtime/goal-context.json

Usage:
  python scripts/ai_goal.py "实现节点批量编辑"
  python scripts/ai_goal.py "实现节点批量编辑" --executor "echo call-cc-or-codex-here"
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AI_DIR = ROOT / ".ai"
SKILLS_DIR = AI_DIR / "skills"
RUNTIME_DIR = AI_DIR / "runtime"
EVENTS_FILE = RUNTIME_DIR / "events.jsonl"
GOAL_CONTEXT_FILE = RUNTIME_DIR / "goal-context.json"

EVENT_PRE = "goal:pre"
EVENT_RUN = "goal:run"
EVENT_POST = "goal:post"


@dataclass
class Skill:
    name: str
    path: Path
    manifest: dict[str, Any]

    @property
    def priority(self) -> int:
        return int(self.manifest.get("priority", 100))

    @property
    def triggers(self) -> list[str]:
        return list(self.manifest.get("triggers", []))

    @property
    def runner(self) -> str:
        return str(self.manifest.get("runner", ""))


def ensure_runtime_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def now_ms() -> int:
    return int(time.time() * 1000)


def append_event(event: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    ensure_runtime_dirs()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def discover_skills() -> list[Skill]:
    skills: list[Skill] = []
    if not SKILLS_DIR.exists():
        return skills

    for manifest_path in SKILLS_DIR.glob("*/manifest.json"):
        try:
            manifest = load_json(manifest_path, {})
            name = str(manifest.get("name") or manifest_path.parent.name)
            skills.append(Skill(name=name, path=manifest_path.parent, manifest=manifest))
        except Exception as exc:  # keep the runtime robust
            append_event({
                "ts": now_ms(),
                "event": "skill:manifest-error",
                "skillPath": str(manifest_path),
                "error": str(exc),
            })
    return sorted(skills, key=lambda s: s.priority)


def get_matched_skills(event_name: str) -> list[Skill]:
    return [skill for skill in discover_skills() if event_name in skill.triggers]


def run_skill(skill: Skill, event_name: str, context: dict[str, Any]) -> dict[str, Any]:
    runner = skill.runner
    if not runner:
        return {"status": "skipped", "reason": "missing runner"}

    runner_path = skill.path / runner
    if not runner_path.exists():
        return {"status": "failed", "reason": f"runner not found: {runner}"}

    env = os.environ.copy()
    env["AI_GOAL_CONTEXT"] = json.dumps(context, ensure_ascii=False)
    env["AI_GOAL_EVENT"] = event_name
    env["AI_GOAL_CONTEXT_FILE"] = str(GOAL_CONTEXT_FILE)
    env["AI_GOAL_EVENTS_FILE"] = str(EVENTS_FILE)
    env["AI_GOAL_ROOT"] = str(ROOT)

    if runner_path.suffix == ".py":
        command = [sys.executable, str(runner_path)]
    elif runner_path.suffix in {".sh", ".bash"}:
        command = ["bash", str(runner_path)]
    else:
        command = shlex.split(str(runner_path))

    started = now_ms()
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    result: dict[str, Any] = {
        "status": "passed" if proc.returncode == 0 else "failed",
        "returnCode": proc.returncode,
        "durationMs": now_ms() - started,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }

    output_file = skill.path / "output.json"
    if output_file.exists():
        try:
            result["output"] = load_json(output_file, {})
        except Exception as exc:
            result["outputReadError"] = str(exc)

    return result


def dispatch_event(event_name: str, context: dict[str, Any]) -> dict[str, Any]:
    matched = get_matched_skills(event_name)
    append_event({
        "ts": now_ms(),
        "goalId": context["goalId"],
        "event": event_name,
        "matchedSkills": [skill.name for skill in matched],
    })

    skill_results: list[dict[str, Any]] = []
    for skill in matched:
        append_event({
            "ts": now_ms(),
            "goalId": context["goalId"],
            "event": "skill:start",
            "lifecycleEvent": event_name,
            "skill": skill.name,
        })
        result = run_skill(skill, event_name, context)
        skill_results.append({"skill": skill.name, "result": result})
        append_event({
            "ts": now_ms(),
            "goalId": context["goalId"],
            "event": "skill:finish",
            "lifecycleEvent": event_name,
            "skill": skill.name,
            "result": result,
        })

    context.setdefault("skillResults", {}).setdefault(event_name, []).extend(skill_results)
    save_json(GOAL_CONTEXT_FILE, context)
    return context


def run_executor(executor: str | None, goal: str, context: dict[str, Any]) -> dict[str, Any]:
    if not executor:
        message = "未配置真实 cc/codex executor；MVP 仅完成 goal:run 事件捕捉。"
        print(message)
        return {"status": "skipped", "reason": message}

    command = shlex.split(executor) + [goal]
    started = now_ms()
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "AI_GOAL_CONTEXT_FILE": str(GOAL_CONTEXT_FILE)},
    )
    result = {
        "status": "passed" if proc.returncode == 0 else "failed",
        "returnCode": proc.returncode,
        "durationMs": now_ms() - started,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    context["executorResult"] = result
    save_json(GOAL_CONTEXT_FILE, context)
    return result


def build_initial_context(goal: str, executor: str | None) -> dict[str, Any]:
    return {
        "goalId": str(uuid.uuid4()),
        "goal": goal,
        "executor": executor,
        "root": str(ROOT),
        "startedAtMs": now_ms(),
        "events": [EVENT_PRE, EVENT_RUN, EVENT_POST],
        "skillResults": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Coding Runtime Skill MVP")
    parser.add_argument("goal", help="目标描述，例如：实现节点批量编辑")
    parser.add_argument("--executor", default=None, help="真实 cc/codex 命令，例如：codex 或 claude")
    args = parser.parse_args()

    ensure_runtime_dirs()
    context = build_initial_context(args.goal, args.executor)
    save_json(GOAL_CONTEXT_FILE, context)

    print(f"[ai-goal] goalId={context['goalId']}")
    print("[ai-goal] dispatch goal:pre")
    context = dispatch_event(EVENT_PRE, context)

    print("[ai-goal] dispatch goal:run")
    context = dispatch_event(EVENT_RUN, context)
    executor_result = run_executor(args.executor, args.goal, context)
    append_event({
        "ts": now_ms(),
        "goalId": context["goalId"],
        "event": "executor:finish",
        "result": executor_result,
    })

    print("[ai-goal] dispatch goal:post")
    context = load_json(GOAL_CONTEXT_FILE, context)
    context = dispatch_event(EVENT_POST, context)
    context["finishedAtMs"] = now_ms()
    save_json(GOAL_CONTEXT_FILE, context)

    failed = []
    for event_results in context.get("skillResults", {}).values():
        for item in event_results:
            if item.get("result", {}).get("status") == "failed":
                failed.append(item.get("skill"))

    print(f"[ai-goal] done. context={GOAL_CONTEXT_FILE}")
    if failed:
        print(f"[ai-goal] failed skills: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

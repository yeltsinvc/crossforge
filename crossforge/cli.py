"""
CrossForge CLI wrapper for agent skills.

Provides a simple interface that agents can call:
  crossforge-run "task description"

Returns a clean summary instead of raw JSON.
"""

import json
import sys
from pathlib import Path

from crossforge.core.orchestrator import Orchestrator


def run():
    """Simple entry point: crossforge-run 'task description'"""
    if len(sys.argv) < 2:
        print("Usage: crossforge-run <task description> [target_dir]")
        print("Example: crossforge-run 'Add unit tests' .")
        sys.exit(1)

    task = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else "."
    target = str(Path(target).resolve())

    config_candidates = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "crossforge.yaml",
        Path.home() / ".crossforge" / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
    ]

    config_path = "config.yaml"
    for candidate in config_candidates:
        if candidate.exists():
            config_path = str(candidate)
            break

    orchestrator = Orchestrator(config_path)
    result = orchestrator.run_task(task, target)

    _print_summary(result)


def _print_summary(result: dict) -> None:
    """Print a human-readable summary."""
    rounds = result.get("rounds", [])
    skills = result.get("skills_created", [])

    for r in rounds:
        print(f"=== Round {r['round'] + 1} ===")
        print(f"Executor: {r['executor']}  |  Reviewer: {r['reviewer']}")
        print()

        print("-- Execution Summary --")
        print(r.get("execution_summary", "N/A"))
        print()

        review = r.get("review", {})
        print(f"-- Review: {review.get('score', '?')}/10 --")
        print(review.get("summary", ""))
        print()

        strengths = review.get("strengths", [])
        if strengths:
            print("Strengths:")
            for s in strengths:
                print(f"  + {s}")
            print()

        issues = review.get("issues", [])
        if issues:
            print("Issues:")
            for i in issues:
                print(f"  - {i}")
            print()

        suggestions = review.get("suggestions", [])
        if suggestions:
            print("Suggestions:")
            for s in suggestions:
                print(f"  > {s}")
            print()

    if skills:
        print("=== New Skills Extracted ===")
        for s in skills:
            print(f"  * {s}")
    else:
        print("=== No new skills extracted ===")


if __name__ == "__main__":
    run()

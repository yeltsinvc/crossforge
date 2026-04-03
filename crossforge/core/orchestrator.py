"""
CrossForge Orchestrator

Main coordinator that manages the dual-agent loop:
  Task → Agent A executes → Agent B reviews → Skills extracted → Loop
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from crossforge.adapters.base import AgentAdapter
from crossforge.adapters.claude_adapter import ClaudeAdapter
from crossforge.adapters.codex_adapter import CodexAdapter
from crossforge.core.queue import TaskQueue, Task, TaskStatus
from crossforge.core.reviewer import CrossReviewer
from crossforge.skills.manager import SkillManager

logger = logging.getLogger("crossforge")


class Orchestrator:
    """Coordinates two agents in a build-review-learn loop."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.queue = TaskQueue(self.config.get("queue_dir", "queue"))
        self.skill_manager = SkillManager(self.config.get("skills_dir", "skills"))
        self.reviewer = CrossReviewer(self.skill_manager)

        self.agents: dict[str, AgentAdapter] = {
            "claude": ClaudeAdapter(self.config.get("agents", {}).get("claude", {})),
            "codex": CodexAdapter(self.config.get("agents", {}).get("codex", {})),
        }

    def _load_config(self, path: str) -> dict:
        config_file = Path(path)
        if config_file.exists():
            import yaml
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def get_opponent(self, agent_name: str) -> str:
        """Return the other agent's name."""
        return "codex" if agent_name == "claude" else "claude"

    def run_task(
        self,
        description: str,
        target: str,
        first_agent: str = "claude",
        max_rounds: int = 1,
    ) -> dict:
        """
        Execute the full CrossForge loop:
        1. Create task
        2. Agent A executes
        3. Agent B reviews
        4. Extract skills from the review
        5. Optionally iterate for more rounds
        """
        task = self.queue.create_task(description, target)
        skills_context = self.skill_manager.get_relevant_skills(description)

        results = {
            "task_id": task.id,
            "rounds": [],
            "skills_created": [],
        }

        current_agent = first_agent

        for round_num in range(max_rounds):
            logger.info(
                "Round %d/%d - executor: %s, reviewer: %s",
                round_num + 1,
                max_rounds,
                current_agent,
                self.get_opponent(current_agent),
            )

            round_result = self._execute_round(
                task, current_agent, skills_context, round_num
            )
            results["rounds"].append(round_result)

            if round_result.get("skills_extracted"):
                results["skills_created"].extend(round_result["skills_extracted"])
                skills_context = self.skill_manager.get_relevant_skills(description)

            current_agent = self.get_opponent(current_agent)

        self.queue.update_status(task.id, TaskStatus.COMPLETED)
        self._save_result(results)
        return results

    def _execute_round(
        self,
        task: Task,
        executor_name: str,
        skills_context: list[dict],
        round_num: int,
    ) -> dict:
        """Run one execute-review cycle."""
        reviewer_name = self.get_opponent(executor_name)
        executor = self.agents[executor_name]
        reviewer = self.agents[reviewer_name]

        self.queue.update_status(task.id, TaskStatus.EXECUTING)
        logger.info("Agent '%s' executing task: %s", executor_name, task.description)

        execution_prompt = self._build_execution_prompt(task, skills_context, round_num)
        execution_result = executor.execute(execution_prompt, task.target)

        self.queue.update_status(task.id, TaskStatus.REVIEWING)
        logger.info("Agent '%s' reviewing output...", reviewer_name)

        review_prompt = self._build_review_prompt(
            task, execution_result, skills_context
        )
        review_result = reviewer.execute(review_prompt, task.target)

        review_data = self.reviewer.parse_review(review_result)

        skills_extracted = self.skill_manager.extract_from_review(
            review_data, task.description, executor_name, reviewer_name
        )

        self._save_review(task.id, round_num, executor_name, review_data)

        return {
            "round": round_num,
            "executor": executor_name,
            "reviewer": reviewer_name,
            "execution_summary": execution_result[:500],
            "review": review_data,
            "skills_extracted": skills_extracted,
        }

    def _build_execution_prompt(
        self, task: Task, skills: list[dict], round_num: int
    ) -> str:
        """Build the prompt sent to the executing agent."""
        parts = [
            f"# Task\n{task.description}\n",
            f"# Target Directory\n{task.target}\n",
        ]

        if skills:
            parts.append("# Shared Skills (best practices from prior reviews)\n")
            for skill in skills:
                parts.append(
                    f"- **{skill['name']}** (confidence: {skill.get('confidence', 'N/A')}): "
                    f"{skill['description']}\n"
                )

        if round_num > 0:
            parts.append(
                "\n# Note\n"
                "This is a refinement round. A previous agent already worked on this. "
                "Review the current state and improve it based on the skills above.\n"
            )

        parts.append(
            "\n# Instructions\n"
            "Execute the task. When done, output a summary of what you did "
            "and any decisions you made.\n"
        )

        return "\n".join(parts)

    def _build_review_prompt(
        self, task: Task, execution_output: str, skills: list[dict]
    ) -> str:
        """Build the prompt sent to the reviewing agent."""
        parts = [
            "# Cross-Review Request\n",
            f"## Original Task\n{task.description}\n",
            f"## Execution Output\n```\n{execution_output}\n```\n",
        ]

        if skills:
            parts.append("## Known Skills (best practices)\n")
            for skill in skills:
                parts.append(f"- {skill['name']}: {skill['description']}\n")

        parts.append(
            "\n## Review Instructions\n"
            "Review the work above. Respond in this exact JSON format:\n"
            "```json\n"
            "{\n"
            '  "score": 0-10,\n'
            '  "summary": "Brief review summary",\n'
            '  "strengths": ["list of things done well"],\n'
            '  "issues": ["list of problems found"],\n'
            '  "suggestions": ["list of improvements"],\n'
            '  "new_patterns": [\n'
            "    {\n"
            '      "name": "pattern-name",\n'
            '      "category": "category",\n'
            '      "description": "What this best practice is",\n'
            '      "example": "Code example if applicable"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n"
        )

        return "\n".join(parts)

    def _save_review(
        self, task_id: str, round_num: int, executor: str, review: dict
    ) -> None:
        """Save review to the reviews directory."""
        reviews_dir = Path(self.config.get("reviews_dir", "reviews"))
        reviews_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{task_id}_round{round_num}_{executor}.json"
        with open(reviews_dir / filename, "w") as f:
            json.dump(
                {
                    "task_id": task_id,
                    "round": round_num,
                    "executor": executor,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "review": review,
                },
                f,
                indent=2,
            )

    def _save_result(self, results: dict) -> None:
        """Save full run results."""
        reviews_dir = Path(self.config.get("reviews_dir", "reviews"))
        reviews_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{results['task_id']}_final.json"
        with open(reviews_dir / filename, "w") as f:
            json.dump(results, f, indent=2)

    def review_only(self, target: str, reviewer_agent: str = "claude") -> dict:
        """Run a review-only pass on existing code."""
        skills_context = self.skill_manager.get_relevant_skills("general code review")
        reviewer = self.agents[reviewer_agent]

        prompt = (
            "# Code Review Request\n"
            f"Review all code in: {target}\n"
            "Focus on quality, patterns, and potential improvements.\n"
            "Output your findings as JSON with: score, strengths, issues, suggestions, new_patterns.\n"
        )

        if skills_context:
            prompt += "\n# Known best practices:\n"
            for skill in skills_context:
                prompt += f"- {skill['name']}: {skill['description']}\n"

        result = reviewer.execute(prompt, target)
        review_data = self.reviewer.parse_review(result)

        skills = self.skill_manager.extract_from_review(
            review_data, "code review", reviewer_agent, "none"
        )

        return {"review": review_data, "skills_created": skills}


def main():
    parser = argparse.ArgumentParser(
        description="CrossForge - Dual-agent orchestration with shared skills"
    )
    parser.add_argument("--task", type=str, help="Task description")
    parser.add_argument("--target", type=str, default=".", help="Target directory")
    parser.add_argument(
        "--first",
        choices=["claude", "codex"],
        default="claude",
        help="Which agent executes first",
    )
    parser.add_argument(
        "--rounds", type=int, default=1, help="Number of execute-review rounds"
    )
    parser.add_argument(
        "--review-only", action="store_true", help="Only review existing code"
    )
    parser.add_argument(
        "--reviewer",
        choices=["claude", "codex"],
        default="claude",
        help="Agent for review-only mode",
    )
    parser.add_argument("--config", type=str, default="config.yaml", help="Config path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    orchestrator = Orchestrator(args.config)

    if args.review_only:
        result = orchestrator.review_only(args.target, args.reviewer)
    elif args.task:
        result = orchestrator.run_task(
            args.task, args.target, args.first, args.rounds
        )
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

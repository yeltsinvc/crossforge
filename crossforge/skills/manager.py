"""
Skill Manager

Manages the shared skill repository. Skills are best practices
extracted from cross-reviews that both agents consume as context.
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger("crossforge.skills")


class SkillManager:
    """Manages shared skills extracted from cross-reviews."""

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def get_all_skills(self) -> list[dict]:
        """Load all skills from disk."""
        skills = []
        for skill_file in self.skills_dir.glob("*.yaml"):
            with open(skill_file) as f:
                skill = yaml.safe_load(f)
                if skill:
                    skill["_file"] = str(skill_file)
                    skills.append(skill)
        return sorted(skills, key=lambda s: s.get("confidence", 0), reverse=True)

    def get_relevant_skills(
        self, task_description: str, max_skills: int = 10
    ) -> list[dict]:
        """
        Return skills relevant to a task.

        Uses simple keyword matching. A future version could use
        embeddings for semantic similarity.
        """
        all_skills = self.get_all_skills()
        task_words = set(task_description.lower().split())

        scored = []
        for skill in all_skills:
            skill_text = (
                f"{skill.get('name', '')} {skill.get('description', '')} "
                f"{skill.get('category', '')}"
            ).lower()
            skill_words = set(skill_text.split())

            overlap = len(task_words & skill_words)
            confidence = skill.get("confidence", 0.5)
            score = overlap + confidence

            scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:max_skills]]

    def extract_from_review(
        self,
        review: dict,
        task_description: str,
        executor: str,
        reviewer: str,
    ) -> list[str]:
        """
        Extract new skills from a review's new_patterns field.
        Returns list of created skill filenames.
        """
        new_patterns = review.get("new_patterns", [])
        if not new_patterns:
            return []

        created = []
        for pattern in new_patterns:
            if not isinstance(pattern, dict):
                continue

            name = pattern.get("name", "").strip()
            if not name:
                continue

            slug = self._slugify(name)
            existing = self._find_skill(slug)

            if existing:
                self._reinforce_skill(existing, review.get("score", 5))
                logger.info("Reinforced existing skill: %s", slug)
            else:
                filename = self._create_skill(
                    name=name,
                    category=pattern.get("category", "general"),
                    description=pattern.get("description", ""),
                    example=pattern.get("example", ""),
                    source_task=task_description,
                    executor=executor,
                    reviewer=reviewer,
                )
                created.append(filename)
                logger.info("Created new skill: %s", filename)

        return created

    def _create_skill(
        self,
        name: str,
        category: str,
        description: str,
        example: str,
        source_task: str,
        executor: str,
        reviewer: str,
    ) -> str:
        """Create a new skill YAML file."""
        slug = self._slugify(name)
        filename = f"{slug}.yaml"

        skill = {
            "name": name,
            "slug": slug,
            "category": category,
            "confidence": 0.6,
            "times_reinforced": 0,
            "times_challenged": 0,
            "description": description,
            "source": {
                "task": source_task,
                "executor": executor,
                "reviewer": reviewer,
                "date": datetime.now(timezone.utc).isoformat(),
            },
        }

        if example:
            skill["example"] = example

        with open(self.skills_dir / filename, "w") as f:
            yaml.dump(skill, f, default_flow_style=False, sort_keys=False)

        return filename

    def _find_skill(self, slug: str) -> Path | None:
        """Find an existing skill by slug."""
        path = self.skills_dir / f"{slug}.yaml"
        return path if path.exists() else None

    def _reinforce_skill(self, skill_path: Path, review_score: int) -> None:
        """Increase confidence of an existing skill."""
        with open(skill_path) as f:
            skill = yaml.safe_load(f)

        skill["times_reinforced"] = skill.get("times_reinforced", 0) + 1
        current = skill.get("confidence", 0.5)
        boost = 0.02 * (review_score / 10)
        skill["confidence"] = min(1.0, current + boost)

        with open(skill_path, "w") as f:
            yaml.dump(skill, f, default_flow_style=False, sort_keys=False)

    def challenge_skill(self, slug: str, reason: str) -> None:
        """Lower confidence of a skill when an agent disagrees with it."""
        skill_path = self._find_skill(slug)
        if not skill_path:
            return

        with open(skill_path) as f:
            skill = yaml.safe_load(f)

        skill["times_challenged"] = skill.get("times_challenged", 0) + 1
        current = skill.get("confidence", 0.5)
        skill["confidence"] = max(0.0, current - 0.05)

        if skill["confidence"] < 0.2:
            deprecated_dir = self.skills_dir / "deprecated"
            deprecated_dir.mkdir(exist_ok=True)
            skill_path.rename(deprecated_dir / skill_path.name)
            logger.info("Deprecated skill '%s': confidence too low", slug)
        else:
            with open(skill_path, "w") as f:
                yaml.dump(skill, f, default_flow_style=False, sort_keys=False)

    def _slugify(self, name: str) -> str:
        """Convert a name to a filesystem-safe slug."""
        slug = name.lower().strip()
        slug = slug.replace(" ", "-")
        return "".join(c for c in slug if c.isalnum() or c == "-")

    def print_skills(self) -> None:
        """Print all skills to stdout."""
        skills = self.get_all_skills()
        if not skills:
            print("No skills found.")
            return

        for skill in skills:
            conf = skill.get("confidence", 0)
            reinforced = skill.get("times_reinforced", 0)
            challenged = skill.get("times_challenged", 0)
            print(
                f"  [{conf:.0%}] {skill['name']} "
                f"(+{reinforced}/-{challenged}) - {skill.get('description', '')[:80]}"
            )


def main():
    parser = argparse.ArgumentParser(description="CrossForge Skill Manager")
    parser.add_argument("--list", action="store_true", help="List all skills")
    parser.add_argument(
        "--dir", type=str, default="skills", help="Skills directory"
    )
    args = parser.parse_args()

    manager = SkillManager(args.dir)

    if args.list:
        manager.print_skills()


if __name__ == "__main__":
    main()

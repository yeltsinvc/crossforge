"""
Cross-Reviewer

Parses and validates review output from agents, normalizing it
into a structured format the skill extractor can consume.
"""

import json
import logging
import re

from crossforge.skills.manager import SkillManager

logger = logging.getLogger("crossforge.reviewer")


class CrossReviewer:
    """Handles parsing and validation of agent review outputs."""

    def __init__(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def parse_review(self, raw_output: str) -> dict:
        """
        Parse agent review output into structured format.

        Tries to extract JSON from the output. Falls back to
        a best-effort text parse if JSON extraction fails.
        """
        json_data = self._extract_json(raw_output)
        if json_data:
            return self._validate_review(json_data)

        logger.warning("Could not extract JSON from review, using text fallback")
        return self._text_fallback(raw_output)

    def _extract_json(self, text: str) -> dict | None:
        """Extract JSON block from agent output."""
        patterns = [
            r"```json\s*\n(.*?)\n\s*```",
            r"```\s*\n(\{.*?\})\n\s*```",
            r"(\{[^{}]*\"score\"[^{}]*\})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _validate_review(self, data: dict) -> dict:
        """Ensure review has all required fields with defaults."""
        return {
            "score": min(10, max(0, data.get("score", 5))),
            "summary": data.get("summary", "No summary provided"),
            "strengths": data.get("strengths", []),
            "issues": data.get("issues", []),
            "suggestions": data.get("suggestions", []),
            "new_patterns": data.get("new_patterns", []),
        }

    def _text_fallback(self, text: str) -> dict:
        """Best-effort parse when JSON extraction fails."""
        return {
            "score": 5,
            "summary": text[:500] if text else "Review could not be parsed",
            "strengths": [],
            "issues": [],
            "suggestions": [],
            "new_patterns": [],
            "_parse_warning": "Fell back to text parsing - JSON not found in output",
        }

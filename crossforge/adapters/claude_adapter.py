"""
Claude Code Adapter

Wraps the Claude Code CLI (`claude`) so the orchestrator
can send prompts and receive structured output.
"""

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from crossforge.adapters.base import AgentAdapter

logger = logging.getLogger("crossforge.adapters.claude")


class ClaudeAdapter(AgentAdapter):
    """Adapter for the Claude Code CLI."""

    @property
    def name(self) -> str:
        return "claude-code"

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def execute(self, prompt: str, working_dir: str) -> str:
        """
        Run Claude Code with a prompt in the given directory.

        Uses `claude -p` (print mode) for non-interactive execution.
        The prompt is passed via a temp file to avoid shell escaping issues.
        """
        if not self.is_available():
            raise RuntimeError(
                "Claude Code CLI not found. Install it: https://docs.anthropic.com/en/docs/claude-code"
            )

        target = Path(working_dir).resolve()
        if not target.is_dir():
            raise RuntimeError(f"Target directory does not exist: {target}")

        prompt_file = Path(tempfile.mktemp(suffix=".md"))
        try:
            prompt_file.write_text(prompt, encoding="utf-8")

            cmd = ["claude", "-p", "--output-format", "text", "--effort", "high"]

            model = self.config.get("model")
            if model:
                cmd.extend(["--model", model])

            max_turns = self.config.get("max_turns")
            if max_turns:
                cmd.extend(["--max-turns", str(max_turns)])

            cmd.append(prompt_file.read_text(encoding="utf-8"))

            logger.debug("Running Claude Code: %s", " ".join(cmd[:4]) + " ...")

            result = subprocess.run(
                cmd,
                cwd=str(target),
                capture_output=True,
                text=True,
                timeout=self.config.get("timeout", 300),
            )

            if result.returncode != 0:
                logger.error("Claude Code stderr: %s", result.stderr)
                return f"ERROR: Claude Code exited with code {result.returncode}\n{result.stderr}"

            return result.stdout

        finally:
            prompt_file.unlink(missing_ok=True)

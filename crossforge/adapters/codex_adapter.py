"""
Codex CLI Adapter

Wraps OpenAI's Codex CLI so the orchestrator can send
prompts and receive structured output.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from crossforge.adapters.base import AgentAdapter

logger = logging.getLogger("crossforge.adapters.codex")


class CodexAdapter(AgentAdapter):
    """Adapter for the OpenAI Codex CLI."""

    @property
    def name(self) -> str:
        return "codex"

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def execute(self, prompt: str, working_dir: str) -> str:
        """
        Run Codex CLI with a prompt in the given directory.

        Uses `codex exec` (non-interactive mode) with
        --full-auto for autonomous sandboxed execution.
        """
        if not self.is_available():
            raise RuntimeError(
                "Codex CLI not found. Install it: https://github.com/openai/codex"
            )

        target = Path(working_dir).resolve()
        if not target.is_dir():
            raise RuntimeError(f"Target directory does not exist: {target}")

        prompt_file = Path(tempfile.mktemp(suffix=".md"))
        try:
            prompt_file.write_text(prompt, encoding="utf-8")

            cmd = ["codex", "exec", "--full-auto"]

            model = self.config.get("model")
            if model:
                cmd.extend(["-m", model])

            reasoning_effort = self.config.get("reasoning_effort")
            if reasoning_effort:
                cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])

            cmd.extend(["-C", str(target)])
            cmd.append(prompt)

            logger.debug("Running Codex: %s", " ".join(cmd[:4]) + " ...")

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=self.config.get("timeout", 300),
            )

            if result.returncode != 0:
                logger.error("Codex stderr: %s", result.stderr)
                return f"ERROR: Codex exited with code {result.returncode}\n{result.stderr}"

            return result.stdout

        finally:
            prompt_file.unlink(missing_ok=True)

"""
Base Agent Adapter

Abstract interface that all agent adapters must implement.
This allows the orchestrator to work with any CLI-based agent.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("crossforge.adapters")


class AgentAdapter(ABC):
    """Abstract base class for agent adapters."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def execute(self, prompt: str, working_dir: str) -> str:
        """
        Send a prompt to the agent and return its output.

        Args:
            prompt: The full prompt to send to the agent.
            working_dir: The directory the agent should work in.

        Returns:
            The agent's text output.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this agent's CLI is installed and accessible."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this agent."""

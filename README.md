# CrossForge

**A dual-agent orchestration system where Claude Code and Codex collaborate, review each other's work, and forge shared skills through continuous mutual improvement.**

```
  Claude Code ──┐          ┌── Codex
       │        ▼          ▼      │
       │    ┌──────────────────┐  │
       │    │   Orchestrator   │  │
       │    └────────┬─────────┘  │
       │             │            │
       ▼             ▼            ▼
  ┌─────────┐  ┌──────────┐  ┌─────────┐
  │  Queue   │  │  Skills  │  │ Reviews │
  └─────────┘  └──────────┘  └─────────┘
```

## How It Works

1. **Task Assignment** - The orchestrator receives a task and assigns it to an agent (Claude Code or Codex)
2. **Execution** - The assigned agent completes the task and outputs the result
3. **Cross-Review** - The *other* agent reviews the work, scoring quality, suggesting improvements
4. **Skill Extraction** - Best practices discovered during review are extracted and saved as shared skills
5. **Mutual Improvement** - Both agents load shared skills on every new task, getting better over time

## Architecture

```
crossforge/
├── crossforge/           # Core library
│   ├── core/             # Orchestrator, queue, reviewer
│   ├── adapters/         # Agent adapters (Claude Code, Codex)
│   └── skills/           # Skill manager and extractor
├── skills/               # Shared skill files (auto-generated)
├── queue/                # Task queue (JSON files)
├── reviews/              # Cross-review results
├── agents/               # Agent-specific configs
├── examples/             # Example workflows
└── config.yaml           # Main configuration
```

## Quick Start

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- [Codex CLI](https://github.com/openai/codex) installed and authenticated

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/crossforge.git
cd crossforge
pip install -r requirements.txt
```

### Configuration

Edit `config.yaml` with your preferences:

```yaml
agents:
  claude:
    command: "claude"
    model: "opus"
  codex:
    command: "codex"
    model: "o4-mini"
```

### Usage

```bash
# Submit a task for the dual-agent loop
python -m crossforge.core.orchestrator --task "Refactor auth module" --target ./my-project

# Run with a specific first agent
python -m crossforge.core.orchestrator --task "Add unit tests" --first claude --target ./my-project

# List extracted skills
python -m crossforge.skills.manager --list

# Run only the review step on existing code
python -m crossforge.core.orchestrator --review-only --target ./my-project
```

## The Skill Loop

Skills are the core innovation of CrossForge. Every cross-review can produce new skills:

```
Task → Agent A executes → Agent B reviews → Skill extracted
                                                  │
                                                  ▼
                                          skills/python_error_handling.yaml
                                          skills/api_design_patterns.yaml
                                          skills/test_coverage_rules.yaml
```

Skills are YAML files that both agents receive as context for future tasks:

```yaml
name: consistent-error-handling
category: python
confidence: 0.92
source: review-2024-001
description: Always use custom exception classes instead of bare exceptions
pattern: |
  # Bad
  try:
      do_something()
  except Exception:
      pass

  # Good
  try:
      do_something()
  except SpecificError as e:
      logger.error(f"Operation failed: {e}")
      raise
```

## How Skills Improve Over Time

- **Reinforced**: When both agents independently follow the same pattern, the skill's confidence increases
- **Challenged**: When an agent proposes an alternative, a debate is triggered and the skill is updated or replaced
- **Deprecated**: Skills that are consistently overridden get automatically archived

## License

MIT

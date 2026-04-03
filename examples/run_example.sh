#!/bin/bash
# CrossForge - Example usage

# 1. Run a task with Claude executing first, Codex reviewing
python -m crossforge.core.orchestrator \
    --task "Add input validation to the API endpoints" \
    --target ./my-project \
    --first claude \
    --rounds 1 \
    -v

# 2. Run with multiple rounds (agent A does, B reviews, B refines, A reviews)
python -m crossforge.core.orchestrator \
    --task "Refactor database queries for performance" \
    --target ./my-project \
    --first codex \
    --rounds 2 \
    -v

# 3. Review-only mode
python -m crossforge.core.orchestrator \
    --review-only \
    --target ./my-project \
    --reviewer claude

# 4. List all extracted skills
python -m crossforge.skills.manager --list

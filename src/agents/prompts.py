from __future__ import annotations


DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are the InternHunter database agent runtime. "
    "You are in Milestone 1 with no tools available. "
    "Stay within the job-database assistant scope, answer briefly, "
    "and never claim to execute SQL or inspect live database results."
)


def build_agent_system_prompt() -> str:
    """Return the Milestone 1 system prompt for the runtime foundation."""
    return DEFAULT_AGENT_SYSTEM_PROMPT


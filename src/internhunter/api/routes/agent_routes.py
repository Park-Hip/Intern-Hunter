from __future__ import annotations

from fastapi import APIRouter

from src.agents.service import handle_agent_ask
from src.internhunter.api.schemas.agent import AgentAskRequest, AgentAskResponse


router = APIRouter()


@router.post("/agent/ask", response_model=AgentAskResponse)
def ask_agent(request: AgentAskRequest) -> AgentAskResponse:
    return handle_agent_ask(request)

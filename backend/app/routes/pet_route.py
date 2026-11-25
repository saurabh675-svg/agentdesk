from fastapi import APIRouter
from pydantic import BaseModel

from ..tools.observer import get_pet_status, toggle_pet, toggle_sleep, get_foreground_window_info
from ..engine.gateways import GATEWAY_ENDPOINTS, GATEWAY_MODELS
from ..config import load_settings

router = APIRouter()


class AskBody(BaseModel):
    prompt: str = ""


class ExpertBody(BaseModel):
    question: str = ""
    use_web: bool = True
    use_knowledge: bool = True
    mcp_tool: str | None = None
    mcp_arguments: dict | None = None


@router.get("/status")
def status_endpoint() -> dict:
    return get_pet_status()


@router.post("/toggle")
def toggle_endpoint() -> dict:
    return toggle_pet()


@router.post("/sleep")
def sleep_endpoint() -> dict:
    return toggle_sleep()


@router.get("/expert/capabilities")
def expert_capabilities() -> dict:
    """What the DeskPet expert can do right now (web, knowledge, MCP skills)."""
    from .. import pet_expert
    return pet_expert.capabilities()


@router.post("/expert")
async def expert_endpoint(body: ExpertBody) -> dict:
    """Answer a question with web search + the knowledge database + MCP skills."""
    from .. import pet_expert
    return await pet_expert.answer(
        body.question,
        use_web=body.use_web,
        use_knowledge=body.use_knowledge,
        mcp_tool=body.mcp_tool,
        mcp_arguments=body.mcp_arguments,
    )


@router.get("/expert/brief")
async def expert_brief() -> dict:
    """A short sourced briefing of the user's current work (used by the schedule)."""
    from .. import pet_expert
    return await pet_expert.daily_brief()


@router.post("/ask")
async def ask_endpoint(body: AskBody) -> dict:
    status = get_pet_status()
    info = get_foreground_window_info()
    prompt = body.prompt.strip() or "What am I working on right now and how can you help?"
    
    reply = (
        f"🐾 **DeskPet Observation:**\n"
        f"- **Active Window:** `{info['title']}`\n"
        f"- **Application:** `{info['process']}`\n"
        f"- **Observed Habit:** {status['insights'][-1] if status['insights'] else 'Deep focus work'}\n\n"
        f"**My suggestion:** Based on your current activity in `{info['process']}`, "
        f"I can automate tasks, run tests, or search code references. Just ask in the chat!"
    )
    return {"reply": reply, "app": info["process"], "title": info["title"]}

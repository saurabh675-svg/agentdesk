from fastapi import APIRouter

from ..tools.computer import computer

router = APIRouter()


@router.get("/state")
async def get_computer_state() -> dict:
    return {"frame": computer.last_frame}


@router.post("/capture")
async def capture_screen() -> dict:
    return await computer.screenshot()


@router.get("/size")
async def screen_size() -> dict:
    return await computer.size()

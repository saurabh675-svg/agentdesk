"""Global earnings API: radar, ventures, tasks, income, learning, autopilot."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import earnings

router = APIRouter()


class RadarBody(BaseModel):
    query: str | None = None
    category: str | None = None
    limit: int = 8


class LaunchBody(BaseModel):
    opportunity_id: str
    name: str | None = None
    currency: str | None = None


class CompleteBody(BaseModel):
    result: str = ""
    income: float = 0
    currency: str | None = None
    lesson: str | None = None


class IncomeBody(BaseModel):
    amount: float
    source: str = ""
    notes: str = ""
    currency: str | None = None
    venture_id: int | None = None


class LearningBody(BaseModel):
    lesson: str
    tags: list[str] = []
    venture_id: int | None = None


class SettingsBody(BaseModel):
    currency: str | None = None
    skills: list[str] | str | None = None
    weekly_hours: int | None = None
    starting_capital: float | None = None
    autopilot: bool | None = None
    country: str | None = None


@router.get("/overview")
def get_overview() -> dict:
    return earnings.overview()


@router.get("/opportunities")
def get_opportunities(query: str | None = None, category: str | None = None, limit: int = 30) -> list[dict]:
    return earnings.opportunities(query=query, category=category, limit=limit)


@router.post("/radar")
async def post_radar(body: RadarBody | None = None) -> dict:
    body = body or RadarBody()
    return await earnings.radar(query=body.query, category=body.category, limit=body.limit)


@router.get("/radar/last")
def get_last_radar() -> dict:
    return earnings.last_scan() or {}


@router.post("/launch")
def post_launch(body: LaunchBody) -> dict:
    try:
        return earnings.create_venture(body.opportunity_id, body.name, body.currency)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/ventures")
def get_ventures() -> list[dict]:
    return earnings.list_ventures()


@router.get("/ventures/{venture_id}")
def get_venture(venture_id: int) -> dict:
    venture = earnings.get_venture(venture_id)
    if not venture:
        raise HTTPException(status_code=404, detail="Venture not found")
    return venture


@router.post("/ventures/{venture_id}/tasks/{task_id}/complete")
def post_complete(venture_id: int, task_id: int, body: CompleteBody | None = None) -> dict:
    body = body or CompleteBody()
    try:
        return earnings.complete_task(
            venture_id,
            task_id,
            result=body.result,
            income=body.income,
            currency=body.currency,
            lesson=body.lesson,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/brief")
def get_brief(venture_id: int | None = None) -> dict:
    return earnings.brief(venture_id)


@router.get("/income")
def get_income() -> dict:
    return {"totals": earnings.income_totals(), "events": earnings.recent_income(50)}


@router.post("/income")
def post_income(body: IncomeBody) -> dict:
    return earnings.log_income(
        body.amount,
        source=body.source,
        notes=body.notes,
        currency=body.currency,
        venture_id=body.venture_id,
    )


class CsvImportBody(BaseModel):
    csv_text: str
    venture_id: int | None = None


@router.post("/income/import-csv")
def import_csv(body: CsvImportBody) -> dict:
    return earnings.import_income_csv(body.csv_text, venture_id=body.venture_id)


@router.get("/learning")
def get_learning(limit: int = 20) -> list[dict]:
    return earnings.list_learning(limit)


@router.post("/learning")
def post_learning(body: LearningBody) -> dict:
    return earnings.add_learning(body.lesson, tags=body.tags, venture_id=body.venture_id)


@router.get("/settings")
def get_settings() -> dict:
    return earnings.get_settings()


@router.put("/settings")
def put_settings(body: SettingsBody) -> dict:
    return earnings.set_settings(body.model_dump(exclude_none=True))


@router.post("/autopilot/tick")
def post_autopilot_tick() -> dict:
    return earnings.autopilot_tick()

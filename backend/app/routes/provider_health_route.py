from fastapi import APIRouter

from .. import provider_health

router = APIRouter()


@router.get("")
def get_provider_health() -> dict:
    return provider_health.summary()


@router.get("/metrics")
def get_metrics() -> dict:
    summary = provider_health.summary()
    total_ok = sum(v.get("ok", 0) for v in summary.values())
    total_fail = sum(v.get("fail", 0) for v in summary.values())
    total_tokens = sum(v.get("tokens", 0) for v in summary.values())
    return {"providers": summary, "totals": {"ok": total_ok, "fail": total_fail, "tokens": total_tokens}}
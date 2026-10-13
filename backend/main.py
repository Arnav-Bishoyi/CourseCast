from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from backend.demo import load_sections, load_forecasts

app = FastAPI(title="CourseCast demo API", version="0.1.0")

class ForecastRequest(BaseModel):
    term: str = Field(min_length=1)
    crn: str = Field(min_length=1)
    ticket_at: datetime

    @field_validator("ticket_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ticket_at must include a UTC offset, e.g. -05:00 or Z")
        return value.astimezone(timezone.utc)

class CurvePoint(BaseModel):
    at: datetime
    probability: float = Field(ge=0, le=1)

class ForecastResponse(BaseModel):
    term: str
    crn: str
    ticket_at: datetime
    forecast_status: Literal["available", "unavailable"]
    probability: float | None = Field(default=None, ge=0, le=1)
    curve: list[CurvePoint] = Field(default_factory=list)
    observed_at: datetime | None = None
    observation_age_seconds: float | None = None
    is_stale: bool | None = None
    demo: bool = True
    source: str = "synthetic_fixture"
    message: str

def parse_at(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo"}

@app.get("/sections")
def sections(term: str = Query(default="2027-spring")):
    return {"sections": [s for s in load_sections() if s["term"] == term],
            "demo": True, "source": "synthetic_fixture"}

@app.post("/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    section = next((s for s in load_sections()
                    if (s["term"], s["crn"]) == (request.term, request.crn)), None)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found in demo fixtures")
    observed = parse_at(section["observed_at"])
    if request.ticket_at < observed:
        raise HTTPException(status_code=422, detail="Ticket precedes the demo observation")
    age = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
    common = dict(term=request.term, crn=request.crn, ticket_at=request.ticket_at,
                  observed_at=observed, observation_age_seconds=age,
                  is_stale=age > 7200)
    fixture = load_forecasts().get(request.crn)
    if fixture is None or section["status"] != "open":
        return ForecastResponse(**common, forecast_status="unavailable",
                                message="No demo forecast for this section; no reopening model exists.")
    points = [CurvePoint(at=parse_at(p["at"]), probability=p["probability"])
              for p in fixture["curve"]]
    if request.ticket_at > points[-1].at:
        return ForecastResponse(**common, forecast_status="unavailable",
                                message="Ticket is outside the demo curve; choose a time within the fixture window.")
    # Piecewise-linear display interpolation of fixed synthetic points, NOT inference.
    probability = points[0].probability
    shown = []
    for left, right in zip(points, points[1:]):
        if request.ticket_at <= right.at:
            weight = (request.ticket_at - left.at).total_seconds() / (right.at - left.at).total_seconds()
            probability = left.probability + weight * (right.probability - left.probability)
            break
    shown = [p for p in points if p.at < request.ticket_at]
    shown.append(CurvePoint(at=request.ticket_at, probability=probability))
    return ForecastResponse(**common, forecast_status="available", probability=probability,
                            curve=shown, message="DEMO DATA - fixed synthetic curve, not a real forecast.")

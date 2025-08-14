"""Pydantic models for API-Sports responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Team(BaseModel):
    """Team model."""

    id: int
    name: str
    code: str | None = None
    country: str | None = None
    founded: int | None = None
    national: bool = False
    logo: str | None = None


class Venue(BaseModel):
    """Venue model."""

    id: int | None = None
    name: str
    address: str | None = None
    city: str | None = None
    capacity: int | None = None
    surface: str | None = None
    image: str | None = None


class League(BaseModel):
    """League model."""

    id: int
    name: str
    country: str
    logo: str | None = None
    flag: str | None = None
    season: int | None = None
    round: str | None = None


class Season(BaseModel):
    """Season model."""

    year: int
    start: str
    end: str
    current: bool
    coverage: dict[str, Any] | None = None


class FixtureStatus(BaseModel):
    """Fixture status model."""

    long: str
    short: str
    elapsed: int | None = None


class Score(BaseModel):
    """Score details."""

    home: int | None = None
    away: int | None = None


class Goals(BaseModel):
    """Goals statistics."""

    home: int | None = None
    away: int | None = None


class Fixture(BaseModel):
    """Fixture (match) model."""

    id: int
    referee: str | None = None
    timezone: str
    date: datetime
    timestamp: int
    periods: dict[str, int | None] | None = None
    venue: Venue | None = None
    status: FixtureStatus
    league: League
    teams: dict[str, Team]
    goals: Goals
    score: dict[str, Score]


class TeamStatistics(BaseModel):
    """Team statistics model."""

    league: League
    team: Team
    form: str | None = None
    fixtures: dict[str, dict[str, int]]
    goals: dict[str, dict[str, Any]]
    biggest: dict[str, Any]
    clean_sheet: dict[str, int]
    failed_to_score: dict[str, int]
    penalty: dict[str, Any]
    lineups: list[dict[str, Any]] | None = None
    cards: dict[str, dict[str, Any]]


class Standing(BaseModel):
    """League standing model."""

    rank: int
    team: Team
    points: int
    goalsDiff: int
    group: str | None = None
    form: str | None = None
    status: str | None = None
    description: str | None = None
    all: dict[str, int]
    home: dict[str, int]
    away: dict[str, int]
    update: datetime


class StatisticValue(BaseModel):
    """Statistic value for fixture statistics."""

    type: str
    value: int | float | str | None


class FixtureStatistics(BaseModel):
    """Fixture statistics model."""

    team: Team
    statistics: list[StatisticValue]


class Event(BaseModel):
    """Match event model."""

    time: dict[str, int | None]
    team: Team
    player: dict[str, Any]
    assist: dict[str, Any] | None = None
    type: str
    detail: str
    comments: str | None = None


class Player(BaseModel):
    """Player model."""

    id: int
    name: str
    number: int | None = None
    pos: str | None = None
    grid: str | None = None


class LineupTeam(BaseModel):
    """Team lineup model."""

    team: Team
    coach: dict[str, Any] | None = None
    formation: str | None = None
    startXI: list[dict[str, Player]] | None = None
    substitutes: list[dict[str, Player]] | None = None


class Lineup(BaseModel):
    """Match lineup model."""

    team: Team
    coach: dict[str, Any] | None = None
    formation: str | None = None
    startXI: list[dict[str, Player]] | None = None
    substitutes: list[dict[str, Player]] | None = None


class PredictionData(BaseModel):
    """Prediction data model."""

    winner: dict[str, Any] | None = None
    win_or_draw: bool | None = None
    under_over: str | None = None
    goals: dict[str, Any] | None = None
    advice: str | None = None
    percent: dict[str, str] | None = None


class Prediction(BaseModel):
    """Match prediction model."""

    predictions: PredictionData
    league: League
    teams: dict[str, Team]
    comparison: dict[str, Any] | None = None
    h2h: list[Fixture] | None = None


class Paging(BaseModel):
    """Pagination information."""

    current: int
    total: int


class ApiResponse(BaseModel):
    """Standard API response wrapper."""

    get: str
    parameters: dict[str, Any]
    errors: list[str] | dict[str, Any]
    results: int
    paging: Paging | None = None
    response: list[Any]

"""Pydantic models for API-Sports responses."""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class Team(BaseModel):
    """Team model."""
    
    id: int
    name: str
    code: Optional[str] = None
    country: Optional[str] = None
    founded: Optional[int] = None
    national: bool = False
    logo: Optional[str] = None


class Venue(BaseModel):
    """Venue model."""
    
    id: Optional[int] = None
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    capacity: Optional[int] = None
    surface: Optional[str] = None
    image: Optional[str] = None


class League(BaseModel):
    """League model."""
    
    id: int
    name: str
    country: str
    logo: Optional[str] = None
    flag: Optional[str] = None
    season: Optional[int] = None
    round: Optional[str] = None


class Season(BaseModel):
    """Season model."""
    
    year: int
    start: str
    end: str
    current: bool
    coverage: Optional[Dict[str, Any]] = None


class FixtureStatus(BaseModel):
    """Fixture status model."""
    
    long: str
    short: str
    elapsed: Optional[int] = None


class Score(BaseModel):
    """Score details."""
    
    home: Optional[int] = None
    away: Optional[int] = None


class Goals(BaseModel):
    """Goals statistics."""
    
    home: Optional[int] = None
    away: Optional[int] = None


class Fixture(BaseModel):
    """Fixture (match) model."""
    
    id: int
    referee: Optional[str] = None
    timezone: str
    date: datetime
    timestamp: int
    periods: Optional[Dict[str, Optional[int]]] = None
    venue: Optional[Venue] = None
    status: FixtureStatus
    league: League
    teams: Dict[str, Team]
    goals: Goals
    score: Dict[str, Score]


class TeamStatistics(BaseModel):
    """Team statistics model."""
    
    league: League
    team: Team
    form: Optional[str] = None
    fixtures: Dict[str, Dict[str, int]]
    goals: Dict[str, Dict[str, Any]]
    biggest: Dict[str, Any]
    clean_sheet: Dict[str, int]
    failed_to_score: Dict[str, int]
    penalty: Dict[str, Any]
    lineups: Optional[List[Dict[str, Any]]] = None
    cards: Dict[str, Dict[str, Any]]


class Standing(BaseModel):
    """League standing model."""
    
    rank: int
    team: Team
    points: int
    goalsDiff: int
    group: Optional[str] = None
    form: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    all: Dict[str, int]
    home: Dict[str, int]
    away: Dict[str, int]
    update: datetime


class StatisticValue(BaseModel):
    """Statistic value for fixture statistics."""
    
    type: str
    value: Union[int, float, str, None]


class FixtureStatistics(BaseModel):
    """Fixture statistics model."""
    
    team: Team
    statistics: List[StatisticValue]


class Event(BaseModel):
    """Match event model."""
    
    time: Dict[str, Optional[int]]
    team: Team
    player: Dict[str, Any]
    assist: Optional[Dict[str, Any]] = None
    type: str
    detail: str
    comments: Optional[str] = None


class Player(BaseModel):
    """Player model."""
    
    id: int
    name: str
    number: Optional[int] = None
    pos: Optional[str] = None
    grid: Optional[str] = None


class LineupTeam(BaseModel):
    """Team lineup model."""
    
    team: Team
    coach: Optional[Dict[str, Any]] = None
    formation: Optional[str] = None
    startXI: Optional[List[Dict[str, Player]]] = None
    substitutes: Optional[List[Dict[str, Player]]] = None


class Lineup(BaseModel):
    """Match lineup model."""
    
    team: Team
    coach: Optional[Dict[str, Any]] = None
    formation: Optional[str] = None
    startXI: Optional[List[Dict[str, Player]]] = None
    substitutes: Optional[List[Dict[str, Player]]] = None


class PredictionData(BaseModel):
    """Prediction data model."""
    
    winner: Optional[Dict[str, Any]] = None
    win_or_draw: Optional[bool] = None
    under_over: Optional[str] = None
    goals: Optional[Dict[str, Any]] = None
    advice: Optional[str] = None
    percent: Optional[Dict[str, str]] = None


class Prediction(BaseModel):
    """Match prediction model."""
    
    predictions: PredictionData
    league: League
    teams: Dict[str, Team]
    comparison: Optional[Dict[str, Any]] = None
    h2h: Optional[List[Fixture]] = None


class Paging(BaseModel):
    """Pagination information."""
    
    current: int
    total: int


class ApiResponse(BaseModel):
    """Standard API response wrapper."""
    
    get: str
    parameters: Dict[str, Any]
    errors: Union[List[str], Dict[str, Any]]
    results: int
    paging: Optional[Paging] = None
    response: List[Any]
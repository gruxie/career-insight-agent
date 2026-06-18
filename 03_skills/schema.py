"""Pydantic models for structured Connect review data."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Accomplishment(BaseModel):
    title: str = Field(description="Short title or topic of the accomplishment")
    description: str = Field(description="Full description of what was done and its impact")


class CorePriority(BaseModel):
    name: str = Field(description="Name of the core priority or competency")
    evidence: str = Field(description="Description of how this priority was demonstrated")


class Goal(BaseModel):
    title: str = Field(description="Short title of the goal or priority")
    description: str = Field(description="Details about the goal and how it will be pursued")


class PeerFeedback(BaseModel):
    quote: str = Field(description="The feedback quote text")
    attribution: str | None = Field(
        default=None, description="Name and title of the person giving feedback"
    )


class ManagerFeedback(BaseModel):
    reflect_past_comments: str | None = Field(
        default=None, description="Manager's comments on past performance"
    )
    look_ahead_comments: str | None = Field(
        default=None, description="Manager's comments on future goals"
    )
    impact_rating: str | None = Field(
        default=None, description="Impact rating if provided (e.g., 'Exceptional', 'Strong')"
    )
    peer_feedback: list[PeerFeedback] = Field(
        default_factory=list,
        description="Peer/stakeholder quotes with attribution when available",
    )


class ReflectOnPast(BaseModel):
    results_delivered: list[Accomplishment] = Field(
        default_factory=list,
        description="List of accomplishments and results delivered during the period",
    )
    core_priorities_demonstrated: list[CorePriority] = Field(
        default_factory=list,
        description="Core priorities or competencies demonstrated with evidence",
    )


class LookAhead(BaseModel):
    priorities: list[Goal] = Field(
        default_factory=list,
        description="Goals and priorities for the upcoming period",
    )


class ConnectReview(BaseModel):
    """Structured representation of a single Microsoft Connect review."""

    # Metadata
    employee_name: str = Field(description="Employee's full name")
    job_title: str = Field(description="Employee's job title at time of review")
    manager_name: str | None = Field(default=None, description="Manager's name")
    connect_period: str = Field(description="Connect period label (e.g., 'Apr 2026')")
    reflection_period: str | None = Field(
        default=None, description="Reflection period date range"
    )
    status: str | None = Field(default=None, description="Document status (e.g., 'Posted')")

    # Content sections
    reflect_on_past: ReflectOnPast = Field(default_factory=ReflectOnPast)
    look_ahead: LookAhead = Field(default_factory=LookAhead)
    manager_feedback: ManagerFeedback = Field(default_factory=ManagerFeedback)
    connect_conversation: str | None = Field(
        default=None, description="Notes from the connect conversation if present"
    )

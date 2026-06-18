"""Pydantic models for the aggregated career timeline profile."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoleEntry(BaseModel):
    job_title: str
    manager_name: str | None = None
    period_start: str = Field(description="Earliest review period in this role")
    period_end: str = Field(description="Latest review period in this role")
    organization: str | None = Field(default=None, description="Team or org if identifiable")


class ProjectEntry(BaseModel):
    title: str
    description: str
    connect_period: str = Field(description="Which review period this appeared in")
    themes: list[str] = Field(default_factory=list, description="Thematic tags for this project")


class StrengthEntry(BaseModel):
    name: str = Field(description="Name of the recurring strength or competency")
    evidence_periods: list[str] = Field(description="Which review periods demonstrate this")
    summary: str = Field(description="Synthesized description across periods")


class GrowthArea(BaseModel):
    name: str = Field(description="Area of growth or development")
    evidence_periods: list[str] = Field(description="Which periods reference this")
    trajectory: str = Field(description="How this evolved over time - improved, ongoing, resolved, etc.")
    summary: str


class PeerEndorsement(BaseModel):
    quote: str
    attribution: str | None = None
    connect_period: str


class ThemeArc(BaseModel):
    theme: str = Field(description="A recurring theme across the career")
    first_seen: str = Field(description="Earliest period where this appears")
    last_seen: str = Field(description="Most recent period where this appears")
    evolution: str = Field(description="How this theme evolved over time")


class CareerTimeline(BaseModel):
    """Aggregated longitudinal career profile synthesized from multiple Connect reviews."""

    employee_name: str
    current_title: str
    career_span: str = Field(description="Date range of all reviews, e.g. 'May 2021 - Apr 2026'")

    # Career progression
    roles: list[RoleEntry] = Field(description="Roles held across the timeline")

    # All projects/accomplishments organized chronologically
    projects: list[ProjectEntry] = Field(
        description="All significant projects/accomplishments across all reviews"
    )

    # Synthesized patterns
    recurring_strengths: list[StrengthEntry] = Field(
        description="Strengths that appear across multiple review periods"
    )
    growth_areas: list[GrowthArea] = Field(
        description="Areas of growth with trajectory over time"
    )
    theme_arcs: list[ThemeArc] = Field(
        description="Major themes that span multiple periods"
    )

    # Collected endorsements
    peer_endorsements: list[PeerEndorsement] = Field(
        default_factory=list,
        description="All peer/stakeholder quotes across reviews"
    )

    # Impact ratings over time
    impact_ratings: list[dict] = Field(
        default_factory=list,
        description="List of {period, rating} entries when ratings are available"
    )

    # Narrative summary
    career_narrative: str = Field(
        description="A 2-3 paragraph narrative summary of the career arc, growth, and trajectory"
    )

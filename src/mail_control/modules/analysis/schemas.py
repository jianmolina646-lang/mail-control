from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from mail_control.modules.analysis.models import AlertType, RiskLevel


class Category(StrEnum):
    NETFLIX = "Netflix"
    DISNEY = "Disney+"
    PRIME_VIDEO = "Prime Video"
    SPOTIFY = "Spotify"
    ADOBE = "Adobe"
    MICROSOFT = "Microsoft"
    APPLE = "Apple"
    STEAM = "Steam"
    GOOGLE = "Google"
    SECURITY = "Seguridad"
    PAYMENTS = "Pagos"
    RENEWALS = "Renovaciones"
    INVOICES = "Facturas"
    MARKETING = "Marketing"
    PROMOTIONS = "Promociones"
    OTHER = "Otros"


class AnalysisResult(BaseModel):
    service: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, max_length=120)
    amount: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=12)
    country: str | None = Field(default=None, max_length=80)
    language: str = Field(max_length=16)
    priority: str = Field(max_length=32)
    email_type: str = Field(max_length=80)
    category: Category
    action_required: str | None = Field(default=None, max_length=500)
    risk_level: RiskLevel
    alert_types: list[AlertType] = Field(default_factory=list)

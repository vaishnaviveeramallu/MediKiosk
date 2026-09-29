from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class IntegrationStatusEnum(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    AVAILABLE = "AVAILABLE"
    ERROR = "ERROR"
    LOCAL_ONLY = "LOCAL_ONLY"


class IntegrationComponentStatus(BaseModel):
    name: str = Field(..., description="System or adapter component name")
    status: IntegrationStatusEnum = Field(..., description="Status of the integration component")
    configured: bool = Field(False, description="Whether required credentials or endpoints are set")
    message: str = Field(..., description="Human-readable status or guidance message")
    endpoint_url: Optional[str] = Field(None, description="Configured endpoint URL, if any")
    details: Optional[Dict[str, Any]] = Field(None, description="Safe metadata (no credentials)")


class SystemIntegrationsStatusResponse(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    system_version: str = "1.0.0"
    components: Dict[str, IntegrationComponentStatus] = Field(
        ...,
        description="Health and integration status of all architectural boundaries"
    )

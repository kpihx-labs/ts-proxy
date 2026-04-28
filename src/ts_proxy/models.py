from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


# --- Strong Typing Models ---


class DeviceIDPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")


class DeviceUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")
    tags: List[str] = Field(
        ..., description="List of tags to assign (e.g., ['tag:server'])."
    )


class SubnetRoutesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")
    routes: List[str] = Field(
        ..., description="List of CIDR strings (e.g., ['10.0.0.0/24'])."
    )


class ACLUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hujson_payload: str = Field(
        ..., description="The raw HuJSON text content of the policy."
    )


class DNSPreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    magicDNS: bool = Field(..., description="Whether to enable MagicDNS.")


class NameserversPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nameservers: List[str] = Field(
        ..., description="List of DNS nameserver IP addresses."
    )


class SearchPathsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paths: List[str] = Field(..., description="List of DNS search paths.")


class AuthKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: Dict[str, Any] = Field(
        ...,
        description="Key capabilities (e.g., {'devices': {'create': {'reusable': true, 'preauthorized': true}}}).",
    )
    expirySeconds: Optional[int] = Field(
        None, description="Key expiry time in seconds."
    )


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpointUrl: str = Field(..., description="The destination URL for webhook events.")
    subscriptions: List[str] = Field(
        ..., description="List of event types to subscribe to."
    )

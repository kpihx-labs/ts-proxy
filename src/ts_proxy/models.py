from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


# --- Strong Typing Models ---


class DeviceIDPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")


class DeviceNamePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")
    name: str = Field(..., description="The new name for the device.")


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


class UserIDPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(..., description="The unique identifier (ID) of the user.")


class UserRolePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(..., description="The unique identifier (ID) of the user.")
    role: str = Field(
        ..., description="New role for the user (e.g., 'admin', 'member')."
    )


class DeviceExpiryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")
    expiry: str = Field(..., description="Expiry date in RFC3339 format.")


class DeviceKeyExpiryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: str = Field(..., description="The unique identifier (ID) of the device.")
    keyExpiryDisabled: bool = Field(..., description="Whether key expiry is disabled.")


class PostureCheckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[str] = Field(
        None, description="The ID of the posture check (for updates)."
    )
    type: str = Field(..., description="Type of posture check.")
    description: str = Field(..., description="Description of the check.")
    value: Any = Field(..., description="Value for the check.")


class ContactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account: Optional[Dict[str, str]] = Field(None, description="Account contact info.")
    support: Optional[Dict[str, str]] = Field(None, description="Support contact info.")
    security: Optional[Dict[str, str]] = Field(
        None, description="Security contact info."
    )


class SettingsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")  # Flexible for global settings


class InvitationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., description="Email of the invited user.")
    role: str = Field("member", description="Role for the invited user.")

"""Pydantic models for device management and OTA updates"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID


# ==================== Device Models ====================

class DeviceMetadata(BaseModel):
    """Metadata about a Pi device"""
    hardware_model: Optional[str] = None
    os_version: Optional[str] = None
    python_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    hostname: Optional[str] = None


class DeviceRegisterRequest(BaseModel):
    """Request model for device registration"""
    device_uuid: str = Field(..., description="UUID7 identifier for the device")
    timezone: str = Field(default="UTC", description="Device timezone (e.g., 'America/Los_Angeles')")
    device_name: Optional[str] = Field(None, description="Optional friendly name for the device")
    metadata: Optional[DeviceMetadata] = Field(default_factory=DeviceMetadata, description="Device metadata")


class DeviceHeartbeatRequest(BaseModel):
    """Request model for device heartbeat"""
    current_version: str = Field(..., description="Current software version running on device")
    status: str = Field(default="online", description="Device status: online, offline, updating")
    metadata: Optional[DeviceMetadata] = Field(default_factory=DeviceMetadata, description="Updated device metadata")


class DeviceResponse(BaseModel):
    """Response model for device information"""
    id: UUID
    device_uuid: str
    device_name: Optional[str]
    registered_at: datetime
    last_seen: datetime
    current_version: str
    timezone: str
    status: str
    metadata: Dict[str, Any]


# ==================== Update Models ====================

class CreateUpdateRequest(BaseModel):
    """Request model for creating a new update"""
    version: str = Field(..., description="Version string (e.g., 'v1.2.3')")
    description: str = Field(..., description="Description of what's in this update")
    requires_system_packages: bool = Field(default=False, description="Whether this update requires apt packages")
    system_packages: List[str] = Field(default_factory=list, description="List of apt packages to install")
    target_devices: Optional[List[str]] = Field(None, description="Optional list of device UUIDs to target (None = all devices)")


class UpdateResponse(BaseModel):
    """Response model for update information"""
    id: UUID
    version: str
    created_at: datetime
    description: str
    package_url: Optional[str]
    requires_system_packages: bool
    system_packages: List[str]


# ==================== Device Update Models ====================

class DeviceUpdateStatusRequest(BaseModel):
    """Request model for updating device update status"""
    device_uuid: str = Field(..., description="Device UUID reporting status")
    status: str = Field(..., description="Update status: pending, downloading, installing, completed, failed")
    error_message: Optional[str] = Field(None, description="Error message if status is 'failed'")


class DeviceUpdateResponse(BaseModel):
    """Response model for device update status"""
    id: UUID
    device_id: UUID
    update_id: UUID
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    # Include related update info for convenience
    update_version: Optional[str] = None


class UpdateCheckResponse(BaseModel):
    """Response model for device checking for updates"""
    update_available: bool
    current_version: str
    latest_version: Optional[str] = None
    update_info: Optional[UpdateResponse] = None
    device_update: Optional[DeviceUpdateResponse] = None


# ==================== Admin Models ====================

class DeviceListResponse(BaseModel):
    """Response model for listing devices"""
    devices: List[DeviceResponse]
    total: int


class UpdateListResponse(BaseModel):
    """Response model for listing updates"""
    updates: List[UpdateResponse]
    total: int


class DeviceUpdateListResponse(BaseModel):
    """Response model for listing device updates"""
    device_updates: List[DeviceUpdateResponse]
    total: int


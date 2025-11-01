"""Device management service for Pi client registration and tracking"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from utils.supabase_client import get_supabase_admin_client
from models.devices import (
    DeviceRegisterRequest,
    DeviceHeartbeatRequest,
    DeviceResponse,
    DeviceListResponse
)

logger = logging.getLogger(__name__)


class DeviceServiceError(Exception):
    """Base exception for device service errors"""
    pass


async def register_device(request: DeviceRegisterRequest) -> DeviceResponse:
    """
    Register a new device or update existing device registration.
    
    Args:
        request: Device registration request
        
    Returns:
        DeviceResponse with device information
        
    Raises:
        DeviceServiceError: If registration fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Convert metadata to dict for JSONB storage
        metadata_dict = request.metadata.model_dump() if request.metadata else {}
        
        # Check if device already exists
        result = supabase.table("devices").select("*").eq("device_uuid", request.device_uuid).execute()
        
        if result.data:
            # Update existing device
            device_id = result.data[0]["id"]
            update_data = {
                "device_name": request.device_name,
                "timezone": request.timezone,
                "metadata": metadata_dict,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "status": "online"
            }
            
            updated = supabase.table("devices").update(update_data).eq("id", device_id).execute()
            logger.info(f"Updated existing device: {request.device_uuid}")
            device_data = updated.data[0]
        else:
            # Create new device
            insert_data = {
                "device_uuid": request.device_uuid,
                "device_name": request.device_name,
                "timezone": request.timezone,
                "metadata": metadata_dict,
                "status": "online",
                "current_version": "v0.0.0"
            }
            
            created = supabase.table("devices").insert(insert_data).execute()
            logger.info(f"Registered new device: {request.device_uuid}")
            device_data = created.data[0]
        
        return DeviceResponse(**device_data)
        
    except Exception as e:
        logger.error(f"Failed to register device: {e}")
        raise DeviceServiceError(f"Device registration failed: {str(e)}")


async def update_device_heartbeat(
    device_uuid: str,
    request: DeviceHeartbeatRequest
) -> DeviceResponse:
    """
    Update device heartbeat and status.
    
    Args:
        device_uuid: Device UUID
        request: Heartbeat request with current version and status
        
    Returns:
        Updated DeviceResponse
        
    Raises:
        DeviceServiceError: If update fails or device not found
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Find device
        result = supabase.table("devices").select("*").eq("device_uuid", device_uuid).execute()
        
        if not result.data:
            raise DeviceServiceError(f"Device not found: {device_uuid}")
        
        # Convert metadata to dict for JSONB storage
        metadata_dict = request.metadata.model_dump() if request.metadata else result.data[0].get("metadata", {})
        
        # Update device
        device_id = result.data[0]["id"]
        update_data = {
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "current_version": request.current_version,
            "status": request.status,
            "metadata": metadata_dict
        }
        
        updated = supabase.table("devices").update(update_data).eq("id", device_id).execute()
        logger.debug(f"Updated heartbeat for device: {device_uuid}")
        
        return DeviceResponse(**updated.data[0])
        
    except DeviceServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to update device heartbeat: {e}")
        raise DeviceServiceError(f"Heartbeat update failed: {str(e)}")


async def get_device_by_uuid(device_uuid: str) -> Optional[DeviceResponse]:
    """
    Get device by UUID.
    
    Args:
        device_uuid: Device UUID
        
    Returns:
        DeviceResponse if found, None otherwise
    """
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("devices").select("*").eq("device_uuid", device_uuid).execute()
        
        if result.data:
            return DeviceResponse(**result.data[0])
        return None
        
    except Exception as e:
        logger.error(f"Failed to get device: {e}")
        return None


async def list_devices(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> DeviceListResponse:
    """
    List all devices with optional filtering.
    
    Args:
        status: Optional status filter (online, offline, updating)
        limit: Maximum number of devices to return
        offset: Offset for pagination
        
    Returns:
        DeviceListResponse with list of devices
    """
    try:
        supabase = get_supabase_admin_client()
        
        query = supabase.table("devices").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        
        query = query.order("last_seen", desc=True).range(offset, offset + limit - 1)
        result = query.execute()
        
        devices = [DeviceResponse(**device) for device in result.data]
        total = result.count or 0
        
        return DeviceListResponse(devices=devices, total=total)
        
    except Exception as e:
        logger.error(f"Failed to list devices: {e}")
        raise DeviceServiceError(f"Failed to list devices: {str(e)}")


async def update_device_status(device_uuid: str, status: str) -> DeviceResponse:
    """
    Update device status.
    
    Args:
        device_uuid: Device UUID
        status: New status (online, offline, updating)
        
    Returns:
        Updated DeviceResponse
        
    Raises:
        DeviceServiceError: If update fails or device not found
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Find device
        result = supabase.table("devices").select("*").eq("device_uuid", device_uuid).execute()
        
        if not result.data:
            raise DeviceServiceError(f"Device not found: {device_uuid}")
        
        device_id = result.data[0]["id"]
        update_data = {
            "status": status,
            "last_seen": datetime.now(timezone.utc).isoformat()
        }
        
        updated = supabase.table("devices").update(update_data).eq("id", device_id).execute()
        logger.info(f"Updated device status: {device_uuid} -> {status}")
        
        return DeviceResponse(**updated.data[0])
        
    except DeviceServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to update device status: {e}")
        raise DeviceServiceError(f"Status update failed: {str(e)}")


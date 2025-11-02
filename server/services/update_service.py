"""Update management service for OTA updates"""
import logging
import zipfile
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import UUID
import tempfile

from utils.supabase_client import get_supabase_admin_client
from models.devices import (
    CreateUpdateRequest,
    UpdateResponse,
    DeviceUpdateResponse,
    DeviceUpdateStatusRequest,
    UpdateCheckResponse,
    UpdateListResponse
)

logger = logging.getLogger(__name__)


class UpdateServiceError(Exception):
    """Base exception for update service errors"""
    pass


async def create_update(
    request: CreateUpdateRequest,
    package_path: Optional[Path] = None
) -> UpdateResponse:
    """
    Create a new update and schedule it for devices.
    
    Args:
        request: Update creation request
        package_path: Optional path to update package ZIP file
        
    Returns:
        UpdateResponse with update information
        
    Raises:
        UpdateServiceError: If creation fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if version already exists
        existing = supabase.table("updates").select("*").eq("version", request.version).execute()
        if existing.data:
            raise UpdateServiceError(f"Update version {request.version} already exists")
        
        # Upload package to Supabase Storage if provided
        package_url = None
        if package_path and package_path.exists():
            try:
                # Read file
                with open(package_path, 'rb') as f:
                    file_content = f.read()
                
                # Upload to Supabase Storage
                storage_path = f"updates/{request.version}.zip"
                supabase.storage.from_("update-packages").upload(
                    storage_path,
                    file_content,
                    file_options={"content-type": "application/zip"}
                )
                
                # Get public URL (note: bucket is private, so this needs authentication)
                package_url = f"{supabase.storage.from_('update-packages').get_public_url(storage_path)}"
                logger.info(f"Uploaded update package: {storage_path}")
            except Exception as e:
                logger.error(f"Failed to upload package: {e}")
                raise UpdateServiceError(f"Package upload failed: {str(e)}")
        
        # Create update record
        insert_data = {
            "version": request.version,
            "description": request.description,
            "update_type": request.update_type,
            "package_url": package_url,
            "requires_system_packages": request.requires_system_packages,
            "system_packages": request.system_packages
        }
        
        created = supabase.table("updates").insert(insert_data).execute()
        update_data = created.data[0]
        logger.info(f"Created update: {request.version} (type: {request.update_type})")
        
        # Schedule update for devices
        await schedule_update_for_devices(
            update_id=update_data["id"],
            update_type=request.update_type,
            target_devices=request.target_devices
        )
        
        return UpdateResponse(**update_data)
        
    except UpdateServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to create update: {e}")
        raise UpdateServiceError(f"Update creation failed: {str(e)}")


async def schedule_update_for_devices(
    update_id: str,
    update_type: str,
    target_devices: Optional[List[str]] = None
) -> int:
    """
    Schedule an update for devices.
    
    Args:
        update_id: Update UUID
        update_type: Type of update (scheduled, urgent, or instant)
        target_devices: Optional list of device UUIDs to target (None = all devices)
        
    Returns:
        Number of device_updates created
        
    Raises:
        UpdateServiceError: If scheduling fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get target devices
        if target_devices:
            devices_query = supabase.table("devices").select("id, device_uuid, timezone, last_seen").in_("device_uuid", target_devices)
        else:
            devices_query = supabase.table("devices").select("id, device_uuid, timezone, last_seen")
        
        devices_result = devices_query.execute()
        
        if not devices_result.data:
            logger.warning("No devices found to schedule update for")
            return 0
        
        # Calculate scheduled_for time based on update type
        device_updates = []
        now = datetime.now(timezone.utc)
        
        for device in devices_result.data:
            # For instant updates, only include devices that were online in the last 5 minutes
            if update_type == "instant":
                last_seen_str = device.get("last_seen")
                if last_seen_str:
                    last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    time_since_seen = (now - last_seen).total_seconds()
                    
                    # Skip devices not seen in the last 5 minutes
                    if time_since_seen > 300:  # 300 seconds = 5 minutes
                        logger.debug(f"Skipping device {device['device_uuid']} for instant update (last seen {time_since_seen:.0f}s ago)")
                        continue
                else:
                    # No last_seen timestamp, skip this device
                    logger.debug(f"Skipping device {device['device_uuid']} for instant update (no last_seen)")
                    continue
                
                # Instant update: schedule immediately
                scheduled_for = now
            elif update_type == "urgent":
                # Urgent updates: schedule for 1 hour from now (device will apply after inactivity)
                scheduled_for = now + timedelta(hours=1)
            else:
                # Scheduled updates: schedule for 2 AM in device's timezone (next occurrence)
                # For simplicity, we'll schedule for 2 AM UTC today/tomorrow
                # The device will handle timezone conversion locally
                scheduled_for = now.replace(hour=2, minute=0, second=0, microsecond=0)
                
                # If 2 AM has already passed today, schedule for tomorrow
                if scheduled_for <= now:
                    scheduled_for += timedelta(days=1)
            
            device_updates.append({
                "device_id": device["id"],
                "update_id": update_id,
                "status": "pending",
                "scheduled_for": scheduled_for.isoformat()
            })
        
        # Insert device_updates
        if device_updates:
            supabase.table("device_updates").insert(device_updates).execute()
            logger.info(f"Scheduled {update_type} update for {len(device_updates)} devices")
        else:
            logger.warning(f"No eligible devices for {update_type} update")
        
        return len(device_updates)
        
    except Exception as e:
        logger.error(f"Failed to schedule update: {e}")
        raise UpdateServiceError(f"Update scheduling failed: {str(e)}")


async def update_device_update_status(
    update_id: str,
    request: DeviceUpdateStatusRequest
) -> DeviceUpdateResponse:
    """
    Update the status of a device update.
    
    Args:
        update_id: Update UUID
        request: Status update request
        
    Returns:
        Updated DeviceUpdateResponse
        
    Raises:
        UpdateServiceError: If update fails
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Find device
        device_result = supabase.table("devices").select("id").eq("device_uuid", request.device_uuid).execute()
        if not device_result.data:
            raise UpdateServiceError(f"Device not found: {request.device_uuid}")
        
        device_id = device_result.data[0]["id"]
        
        # Find device_update record
        device_update_result = supabase.table("device_updates").select("*").eq("device_id", device_id).eq("update_id", update_id).execute()
        
        if not device_update_result.data:
            raise UpdateServiceError(f"Device update record not found")
        
        device_update_id = device_update_result.data[0]["id"]
        
        # Prepare update data
        update_data = {
            "status": request.status
        }
        
        # Set timestamps based on status
        now = datetime.now(timezone.utc).isoformat()
        if request.status == "downloading" and not device_update_result.data[0].get("started_at"):
            update_data["started_at"] = now
        elif request.status in ["completed", "failed"]:
            update_data["completed_at"] = now
            if request.error_message:
                update_data["error_message"] = request.error_message
            
            # If completed, update device's current_version
            if request.status == "completed":
                update_info = supabase.table("updates").select("version").eq("id", update_id).execute()
                if update_info.data:
                    supabase.table("devices").update({"current_version": update_info.data[0]["version"]}).eq("id", device_id).execute()
        
        # Update device_update record
        updated = supabase.table("device_updates").update(update_data).eq("id", device_update_id).execute()
        logger.info(f"Updated device_update status: {request.device_uuid} -> {request.status}")
        
        return DeviceUpdateResponse(**updated.data[0])
        
    except UpdateServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to update device_update status: {e}")
        raise UpdateServiceError(f"Status update failed: {str(e)}")


async def check_for_updates(device_uuid: str) -> UpdateCheckResponse:
    """
    Check if there are pending updates for a device.
    
    Args:
        device_uuid: Device UUID
        
    Returns:
        UpdateCheckResponse with update information
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Find device
        device_result = supabase.table("devices").select("*").eq("device_uuid", device_uuid).execute()
        if not device_result.data:
            raise UpdateServiceError(f"Device not found: {device_uuid}")
        
        device = device_result.data[0]
        device_id = device["id"]
        current_version = device["current_version"]
        
        # Find pending updates for this device
        device_updates_result = supabase.table("device_updates").select("*, updates(*)").eq("device_id", device_id).eq("status", "pending").order("created_at", desc=True).limit(1).execute()
        
        if device_updates_result.data:
            device_update = device_updates_result.data[0]
            update_info = device_update["updates"]
            
            return UpdateCheckResponse(
                update_available=True,
                current_version=current_version,
                latest_version=update_info["version"],
                update_info=UpdateResponse(**update_info),
                device_update=DeviceUpdateResponse(
                    **{k: v for k, v in device_update.items() if k != "updates"},
                    update_version=update_info["version"],
                    update_type=update_info["update_type"]
                )
            )
        else:
            return UpdateCheckResponse(
                update_available=False,
                current_version=current_version
            )
        
    except UpdateServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        raise UpdateServiceError(f"Update check failed: {str(e)}")


async def get_update_download_url(update_id: str) -> str:
    """
    Get the download URL for an update package.
    
    Args:
        update_id: Update UUID
        
    Returns:
        Download URL for the update package
        
    Raises:
        UpdateServiceError: If update not found or has no package
    """
    try:
        supabase = get_supabase_admin_client()
        
        result = supabase.table("updates").select("*").eq("id", update_id).execute()
        
        if not result.data:
            raise UpdateServiceError(f"Update not found: {update_id}")
        
        update = result.data[0]
        package_url = update.get("package_url")
        
        if not package_url:
            raise UpdateServiceError(f"Update has no package URL: {update_id}")
        
        return package_url
        
    except UpdateServiceError:
        raise
    except Exception as e:
        logger.error(f"Failed to get download URL: {e}")
        raise UpdateServiceError(f"Failed to get download URL: {str(e)}")


async def list_updates(limit: int = 100, offset: int = 0) -> UpdateListResponse:
    """
    List all updates.
    
    Args:
        limit: Maximum number of updates to return
        offset: Offset for pagination
        
    Returns:
        UpdateListResponse with list of updates
    """
    try:
        supabase = get_supabase_admin_client()
        
        result = supabase.table("updates").select("*", count="exact").order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        updates = [UpdateResponse(**update) for update in result.data]
        total = result.count or 0
        
        return UpdateListResponse(updates=updates, total=total)
        
    except Exception as e:
        logger.error(f"Failed to list updates: {e}")
        raise UpdateServiceError(f"Failed to list updates: {str(e)}")


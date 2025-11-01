"""Device management API endpoints"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from middleware.auth import verify_api_key
from models.devices import (
    DeviceRegisterRequest,
    DeviceHeartbeatRequest,
    DeviceResponse,
    DeviceListResponse,
    UpdateCheckResponse
)
from services.device_service import (
    register_device,
    update_device_heartbeat,
    get_device_by_uuid,
    list_devices,
    update_device_status,
    DeviceServiceError
)
from services.update_service import check_for_updates, UpdateServiceError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/devices",
    tags=["devices"],
    dependencies=[Depends(verify_api_key)]
)


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_200_OK)
async def register_device_endpoint(request: DeviceRegisterRequest):
    """
    Register a new device or update existing device registration.
    
    This endpoint is called by Pi clients on first boot to register with the server.
    If the device UUID already exists, it updates the registration information.
    
    **Authentication**: Requires valid API key
    
    **Request Body**:
    - `device_uuid`: UUID7 identifier for the device
    - `timezone`: Device timezone (e.g., 'America/Los_Angeles')
    - `device_name`: Optional friendly name for the device
    - `metadata`: Optional device metadata (hardware info, OS version, etc.)
    
    **Returns**: Device information including ID and registration timestamp
    """
    try:
        device = await register_device(request)
        logger.info(f"Device registered: {request.device_uuid}")
        return device
    except DeviceServiceError as e:
        logger.error(f"Device registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{device_uuid}/heartbeat", response_model=DeviceResponse)
async def heartbeat_endpoint(device_uuid: str, request: DeviceHeartbeatRequest):
    """
    Update device heartbeat and status.
    
    This endpoint should be called periodically by Pi clients to update their
    last_seen timestamp and current software version.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `device_uuid`: Device UUID
    
    **Request Body**:
    - `current_version`: Current software version running on device
    - `status`: Device status (online, offline, updating)
    - `metadata`: Optional updated device metadata
    
    **Returns**: Updated device information
    """
    try:
        device = await update_device_heartbeat(device_uuid, request)
        logger.debug(f"Heartbeat updated: {device_uuid}")
        return device
    except DeviceServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        logger.error(f"Heartbeat update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{device_uuid}", response_model=DeviceResponse)
async def get_device_endpoint(device_uuid: str):
    """
    Get device information by UUID.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `device_uuid`: Device UUID
    
    **Returns**: Device information
    """
    device = await get_device_by_uuid(device_uuid)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found: {device_uuid}"
        )
    return device


@router.get("/", response_model=DeviceListResponse)
async def list_devices_endpoint(
    status: str = None,
    limit: int = 100,
    offset: int = 0
):
    """
    List all registered devices with optional filtering.
    
    **Authentication**: Requires valid API key
    
    **Query Parameters**:
    - `status`: Optional status filter (online, offline, updating)
    - `limit`: Maximum number of devices to return (default: 100)
    - `offset`: Offset for pagination (default: 0)
    
    **Returns**: List of devices and total count
    """
    try:
        return await list_devices(status=status, limit=limit, offset=offset)
    except DeviceServiceError as e:
        logger.error(f"Failed to list devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{device_uuid}/updates/check", response_model=UpdateCheckResponse)
async def check_for_updates_endpoint(device_uuid: str):
    """
    Check if there are pending updates for a device.
    
    This endpoint is called by Pi clients to check if they have any pending updates.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `device_uuid`: Device UUID
    
    **Returns**: Update check response with available update information
    """
    try:
        return await check_for_updates(device_uuid)
    except UpdateServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        logger.error(f"Failed to check for updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{device_uuid}/status")
async def update_device_status_endpoint(device_uuid: str, status: str):
    """
    Update device status.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `device_uuid`: Device UUID
    
    **Query Parameters**:
    - `status`: New status (online, offline, updating)
    
    **Returns**: Updated device information
    """
    try:
        return await update_device_status(device_uuid, status)
    except DeviceServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        logger.error(f"Failed to update device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


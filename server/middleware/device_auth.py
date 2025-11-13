"""Device-based authentication middleware for UUID verification"""
import logging
import re
from fastapi import HTTPException, Header, status

from utils.supabase_client import get_supabase_admin_client
from utils.device_cache import device_cache
from models.devices import DeviceResponse

logger = logging.getLogger(__name__)

# UUID pattern for validation (UUID4/UUID7 format)
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


async def verify_device_uuid(
    x_device_uuid: str = Header(..., alias="X-Device-UUID")
) -> DeviceResponse:
    """
    Verify device UUID from request header and check database registration.
    
    This middleware ensures that:
    1. The device UUID is provided in the request header
    2. The UUID format is valid
    3. The device is registered in the database
    4. The device status allows making requests
    
    Args:
        x_device_uuid: Device UUID from X-Device-UUID header
        
    Returns:
        DeviceResponse with device information
        
    Raises:
        HTTPException 400: If UUID is missing or malformed
        HTTPException 403: If device is not registered or not authorized
        HTTPException 500: If database query fails
    """
    
    # Validate UUID format
    if not x_device_uuid:
        logger.warning("Request received without device UUID")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing device UUID. Please provide X-Device-UUID header.",
        )
    
    if not UUID_PATTERN.match(x_device_uuid):
        logger.warning(f"Invalid UUID format received: {x_device_uuid}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format: {x_device_uuid}",
        )

    # PERFORMANCE OPTIMIZATION: Check cache before database query
    cached_device_data = device_cache.get(x_device_uuid)
    if cached_device_data:
        # Cache hit - but SECURITY: Always verify status is still valid in database
        # This ensures status changes (active -> disabled/offline) take effect immediately
        device = DeviceResponse(**cached_device_data)
        
        # SECURITY: Verify status hasn't changed in database (lightweight query)
        try:
            supabase = get_supabase_admin_client()
            status_result = supabase.table("devices").select("status").eq("device_uuid", x_device_uuid).execute()
            
            if not status_result.data:
                # Device was deleted - invalidate cache and reject
                device_cache.invalidate(x_device_uuid)
                logger.warning(f"Device {x_device_uuid} was deleted from database")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Device not registered: {x_device_uuid}. "
                        "Please register this device on the server using: "
                        f"./register_device.sh {x_device_uuid}"
                    ),
                )
            
            current_status = status_result.data[0].get("status")
            
            # Check if status changed to invalid
            if current_status not in ["online", "active"]:
                # Status changed to invalid - invalidate cache and reject
                device_cache.invalidate(x_device_uuid)
                logger.warning(f"Device {x_device_uuid} status changed to: {current_status}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Device not authorized. Current status: {current_status}",
                )
            
            # Status is still valid - return cached device
            logger.debug(f"Device authenticated from cache: {x_device_uuid} ({device.device_name})")
            return device
            
        except HTTPException:
            # Re-raise HTTP exceptions (status check failed)
            raise
        except Exception as e:
            # If status verification fails, fall through to full database query
            logger.warning(f"Status verification failed for cached device {x_device_uuid}: {e}, falling back to full query")
            # Fall through to cache miss path below

    # Cache miss - query database for device
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("devices").select("*").eq("device_uuid", x_device_uuid).execute()

        if not result.data:
            logger.warning(f"Unregistered device attempted to connect: {x_device_uuid}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Device not registered: {x_device_uuid}. "
                    "Please register this device on the server using: "
                    f"./register_device.sh {x_device_uuid}"
                ),
            )

        device_data = result.data[0]
        device = DeviceResponse(**device_data)

        # Check device status
        if device.status not in ["online", "active"]:
            logger.warning(f"Device {x_device_uuid} attempted to connect with status: {device.status}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Device not authorized. Current status: {device.status}",
            )

        # PERFORMANCE OPTIMIZATION: Cache the validated device for 10 minutes
        device_cache.set(x_device_uuid, device_data)

        logger.debug(f"Device authenticated successfully: {x_device_uuid} ({device.device_name})")
        return device
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to verify device UUID {x_device_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify device authentication",
        )


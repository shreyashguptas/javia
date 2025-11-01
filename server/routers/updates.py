"""Update management API endpoints"""
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse

from middleware.auth import verify_api_key
from models.devices import (
    CreateUpdateRequest,
    UpdateResponse,
    DeviceUpdateStatusRequest,
    DeviceUpdateResponse,
    UpdateListResponse
)
from services.update_service import (
    create_update,
    update_device_update_status,
    get_update_download_url,
    list_updates,
    UpdateServiceError
)
from utils.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/updates",
    tags=["updates"],
    dependencies=[Depends(verify_api_key)]
)


@router.post("/create", response_model=UpdateResponse, status_code=status.HTTP_201_CREATED)
async def create_update_endpoint(
    version: str = Form(...),
    description: str = Form(...),
    update_type: str = Form("scheduled"),
    requires_system_packages: bool = Form(False),
    system_packages: str = Form("[]"),  # JSON string array
    target_devices: Optional[str] = Form(None),  # JSON string array or None
    package: Optional[UploadFile] = File(None)
):
    """
    Create a new update and schedule it for devices.
    
    This is an admin endpoint used to push new updates to devices.
    The update package (ZIP file) should contain the updated Pi client code.
    
    **Authentication**: Requires valid API key
    
    **Form Data**:
    - `version`: Version string (e.g., 'v1.2.3')
    - `description`: Description of what's in this update
    - `update_type`: Update type ('scheduled' or 'urgent')
    - `requires_system_packages`: Whether this update requires apt packages
    - `system_packages`: JSON string array of apt packages to install
    - `target_devices`: Optional JSON string array of device UUIDs (None = all devices)
    - `package`: ZIP file containing the update
    
    **Returns**: Update information including ID and version
    """
    try:
        import json
        import tempfile
        
        # Parse JSON strings
        system_packages_list = json.loads(system_packages) if system_packages else []
        target_devices_list = json.loads(target_devices) if target_devices else None
        
        # Create request object
        request = CreateUpdateRequest(
            version=version,
            description=description,
            update_type=update_type,
            requires_system_packages=requires_system_packages,
            system_packages=system_packages_list,
            target_devices=target_devices_list
        )
        
        # Save package to temporary file if provided
        package_path = None
        if package:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
            content = await package.read()
            temp_file.write(content)
            temp_file.close()
            package_path = Path(temp_file.name)
        
        # Create update
        update = await create_update(request, package_path=package_path)
        
        # Clean up temp file
        if package_path and package_path.exists():
            package_path.unlink()
        
        logger.info(f"Update created: {version} ({update_type})")
        return update
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON in system_packages or target_devices: {str(e)}"
        )
    except UpdateServiceError as e:
        logger.error(f"Failed to create update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{update_id}/download")
async def download_update_endpoint(update_id: str):
    """
    Download an update package.
    
    This endpoint is called by Pi clients to download update packages.
    The package is retrieved from Supabase Storage.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `update_id`: Update UUID
    
    **Returns**: ZIP file containing the update
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get update info
        result = supabase.table("updates").select("*").eq("id", update_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Update not found: {update_id}"
            )
        
        update = result.data[0]
        version = update["version"]
        
        # Download from Supabase Storage
        storage_path = f"updates/{version}.zip"
        
        try:
            # Download file from storage
            file_data = supabase.storage.from_("update-packages").download(storage_path)
            
            # Return as streaming response
            from io import BytesIO
            return StreamingResponse(
                BytesIO(file_data),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={version}.zip"
                }
            )
        except Exception as storage_error:
            logger.error(f"Failed to download from storage: {storage_error}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Update package not found in storage"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{update_id}/status", response_model=DeviceUpdateResponse)
async def update_status_endpoint(update_id: str, request: DeviceUpdateStatusRequest):
    """
    Update the status of a device update.
    
    This endpoint is called by Pi clients to report progress on update installation.
    
    **Authentication**: Requires valid API key
    
    **Path Parameters**:
    - `update_id`: Update UUID
    
    **Request Body**:
    - `device_uuid`: Device UUID reporting status
    - `status`: Update status (pending, downloading, installing, completed, failed)
    - `error_message`: Optional error message if status is 'failed'
    
    **Returns**: Updated device_update information
    """
    try:
        device_update = await update_device_update_status(update_id, request)
        logger.info(f"Update status updated: {request.device_uuid} -> {request.status}")
        return device_update
    except UpdateServiceError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        logger.error(f"Failed to update status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=UpdateListResponse)
async def list_updates_endpoint(limit: int = 100, offset: int = 0):
    """
    List all updates.
    
    **Authentication**: Requires valid API key
    
    **Query Parameters**:
    - `limit`: Maximum number of updates to return (default: 100)
    - `offset`: Offset for pagination (default: 0)
    
    **Returns**: List of updates and total count
    """
    try:
        return await list_updates(limit=limit, offset=offset)
    except UpdateServiceError as e:
        logger.error(f"Failed to list updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


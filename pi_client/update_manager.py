"""Update manager for OTA updates - simplified for immediate updates"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import config

logger = logging.getLogger(__name__)

# Installation directory
INSTALL_DIR = Path.home() / "javia_client"


class UpdateManager:
    """Manages OTA updates - applies updates immediately when detected"""
    
    def __init__(
        self,
        server_url: str,
        api_key: Optional[str],
        device_uuid: str
    ):
        """
        Initialize update manager.
        
        Args:
            server_url: Server URL
            api_key: Optional API key for admin operations (not used for device auth)
            device_uuid: Device UUID
        """
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key  # Optional - only needed for admin operations
        self.device_uuid = device_uuid
        
        # Update state
        self.update_in_progress = False
        
        logger.info("Update manager initialized")
    
    def check_for_update(self) -> Optional[Dict[str, Any]]:
        """
        Check if there's a pending update for this device using device UUID authentication.
        Called on-demand (before processing queries).
        
        Returns:
            Update info dict if update available, None otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/devices/{self.device_uuid}/updates/check"
            headers = {"X-Device-UUID": self.device_uuid}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    logger.info(f"Update available: {data.get('latest_version')}")
                    return data
                else:
                    return None
            else:
                logger.warning(f"Update check failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            return None
    
    def apply_update_if_available(self) -> bool:
        """
        Check for updates and apply immediately if available.
        
        Returns:
            True if update was applied (device will restart), False otherwise
        """
        update_data = self.check_for_update()
        if update_data:
            logger.info("Applying update immediately...")
            self._apply_update(update_data)
            return True  # Note: This won't actually return as device will restart
        return False
    
    def _apply_update(self, update_data: Dict[str, Any]):
        """
        Download and apply the update immediately.
        
        Args:
            update_data: Update information from check_for_update()
        """
        if self.update_in_progress:
            logger.warning("Update already in progress")
            return
        
        try:
            self.update_in_progress = True
            logger.info(f"Applying update...")

            update_info = update_data.get("update_info", {})

            update_id = update_info.get("id")
            version = update_info.get("version")
            requires_system_packages = update_info.get("requires_system_packages", False)
            system_packages = update_info.get("system_packages", [])

            # Report status: downloading
            self._report_status(update_id, "downloading")

            # Download update package
            update_file = self._download_update(update_id, version)

            if not update_file:
                raise Exception("Failed to download update")

            # Report status: installing
            self._report_status(update_id, "installing")

            # Extract and install update
            self._install_update(update_file, requires_system_packages, system_packages)

            # Report status: completed
            self._report_status(update_id, "completed")

            logger.info(f"Update {version} completed successfully")
            
            # Restart service after successful update
            self._restart_service()
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            # Report failure
            if update_data:
                update_id = update_data.get("update_info", {}).get("id")
                self._report_status(update_id, "failed", error_message=str(e))
            
            self.update_in_progress = False
    
    def _download_update(self, update_id: str, version: str) -> Optional[Path]:
        """
        Download update package from server using device UUID authentication.
        
        Args:
            update_id: Update UUID
            version: Update version
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            url = f"{self.server_url}/api/v1/updates/{update_id}/download"
            headers = {"X-Device-UUID": self.device_uuid}
            
            response = requests.get(url, headers=headers, stream=True, timeout=300)

            if response.status_code != 200:
                logger.error(f"Download failed: {response.status_code}")
                return None

            # Save to temporary file
            temp_file = Path(tempfile.gettempdir()) / f"javia_update_{version}.zip"

            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = temp_file.stat().st_size
            if config.VERBOSE_OUTPUT:
                logger.info(f"Downloaded {file_size} bytes")
            
            return temp_file
            
        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None
    
    def _install_update(self, update_file: Path, requires_system_packages: bool, system_packages: list):
        """
        Install update from ZIP file.
        
        Args:
            update_file: Path to update ZIP file
            requires_system_packages: Whether to install system packages
            system_packages: List of apt packages to install
        """
        try:
            # Extract to temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix="javia_update_"))
            
            logger.info(f"Extracting update to {temp_dir}...")
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Read update metadata if available
            metadata_file = temp_dir / "update_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                logger.info(f"Update metadata: {metadata}")
            
            # Install system packages if required
            if requires_system_packages and system_packages:
                logger.info(f"Installing system packages: {system_packages}")
                try:
                    subprocess.run(
                        ["sudo", "apt-get", "update"],
                        check=True,
                        capture_output=True,
                        timeout=300
                    )
                    subprocess.run(
                        ["sudo", "apt-get", "install", "-y"] + system_packages,
                        check=True,
                        capture_output=True,
                        timeout=600
                    )
                    logger.info("System packages installed successfully")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to install system packages: {e}")
                    raise
            
            # Copy updated files to installation directory
            logger.info(f"Installing files to {INSTALL_DIR}...")
            
            # Find the pi_client directory in the extracted files
            client_src = temp_dir / "pi_client"
            if not client_src.exists():
                # Maybe files are at root level
                client_src = temp_dir
            
            # Copy Python files
            for py_file in client_src.glob("*.py"):
                dest = INSTALL_DIR / py_file.name
                shutil.copy2(py_file, dest)
                logger.info(f"Installed: {py_file.name}")
            
            # Copy requirements.txt if present
            requirements_src = client_src / "requirements.txt"
            if requirements_src.exists():
                shutil.copy2(requirements_src, INSTALL_DIR / "requirements.txt")
                
                # Install updated Python dependencies
                logger.info("Updating Python dependencies...")
                venv_pip = Path.home() / "venvs" / "pi_client" / "bin" / "pip"
                if venv_pip.exists():
                    subprocess.run(
                        [str(venv_pip), "install", "-r", str(INSTALL_DIR / "requirements.txt")],
                        check=True,
                        capture_output=True,
                        timeout=300
                    )
                    logger.info("Python dependencies updated")
            
            # Copy VERSION file if present
            version_src = client_src / "VERSION"
            if version_src.exists():
                shutil.copy2(version_src, INSTALL_DIR / "VERSION")
                logger.info("VERSION file updated")
            
            # Clean up
            shutil.rmtree(temp_dir)
            update_file.unlink()
            
            logger.info("Update installation completed")
            
        except Exception as e:
            logger.error(f"Failed to install update: {e}")
            raise
    
    def _report_status(self, update_id: str, status: str, error_message: Optional[str] = None):
        """
        Report update status to server using device UUID authentication.
        
        Args:
            update_id: Update UUID
            status: Status (downloading, installing, completed, failed)
            error_message: Optional error message if failed
        """
        try:
            url = f"{self.server_url}/api/v1/updates/{update_id}/status"
            headers = {
                "X-Device-UUID": self.device_uuid,
                "Content-Type": "application/json"
            }
            
            data = {
                "device_uuid": self.device_uuid,
                "status": status
            }
            
            if error_message:
                data["error_message"] = error_message
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Reported status: {status}")
            else:
                logger.warning(f"Failed to report status: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Failed to report status: {e}")
    
    def _restart_service(self):
        """Restart the voice assistant service"""
        try:
            logger.info("Restarting service after update...")
            
            # Use subprocess to restart the systemd service
            # This will terminate the current process
            subprocess.Popen(
                ["sudo", "systemctl", "restart", "voice-assistant-client.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Give the command time to execute
            time.sleep(2)
            
            # Exit current process (systemd will restart us)
            logger.info("Exiting for restart...")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
            # Continue running on old version
            self.update_in_progress = False


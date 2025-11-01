"""Update manager for OTA updates with Supabase real-time listener"""
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import tempfile
import zipfile
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import requests
import pytz
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Installation directory
INSTALL_DIR = Path.home() / "javia_client"


class UpdateManager:
    """Manages OTA updates with Supabase real-time subscription"""
    
    def __init__(
        self,
        server_url: str,
        api_key: str,
        device_uuid: str,
        timezone_str: str,
        activity_tracker,
        supabase_url: str,
        supabase_key: str
    ):
        """
        Initialize update manager.
        
        Args:
            server_url: Server URL
            api_key: API key for authentication
            device_uuid: Device UUID
            timezone_str: Device timezone string
            activity_tracker: ActivityTracker instance
            supabase_url: Supabase project URL
            supabase_key: Supabase anon key
        """
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.device_uuid = device_uuid
        self.timezone_str = timezone_str
        self.activity_tracker = activity_tracker
        
        # Initialize Supabase client
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Update state
        self.pending_update: Optional[Dict[str, Any]] = None
        self.update_in_progress = False
        
        # Background thread
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        logger.info("Update manager initialized")
    
    def start(self):
        """Start the update manager background thread"""
        if self._running:
            logger.warning("Update manager already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_update_loop, daemon=True)
        self._thread.start()
        logger.info("Update manager started")
    
    def stop(self):
        """Stop the update manager"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Update manager stopped")
    
    def _run_update_loop(self):
        """Background thread that checks for updates and applies them"""
        # Subscribe to device_updates table changes
        self._setup_realtime_subscription()
        
        while self._running:
            try:
                # Check if we have a pending update
                if self.pending_update and not self.update_in_progress:
                    self._process_pending_update()
                
                # Sleep for a bit
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _setup_realtime_subscription(self):
        """Set up Supabase real-time subscription for device updates"""
        try:
            # Get device_id from device_uuid
            device_result = self.supabase.table("devices").select("id").eq("device_uuid", self.device_uuid).execute()
            
            if not device_result.data:
                logger.warning(f"Device not found in database: {self.device_uuid}")
                return
            
            device_id = device_result.data[0]["id"]
            
            # Subscribe to device_updates table
            def handle_update(payload):
                """Handle real-time update notification"""
                try:
                    logger.info(f"Received real-time update: {payload}")
                    
                    # Check if this is for our device and status is pending
                    data = payload.get("record", {})
                    if data.get("device_id") == device_id and data.get("status") == "pending":
                        # Fetch full update details
                        self._fetch_pending_update()
                except Exception as e:
                    logger.error(f"Error handling real-time update: {e}")
            
            # Set up subscription
            # Note: The realtime library API may vary. This is a simplified version.
            # In production, you may need to use the actual Supabase realtime API
            logger.info(f"Setting up real-time subscription for device_id: {device_id}")
            
            # For now, we'll use polling as a fallback
            # The Supabase Python client's realtime is still evolving
            self._start_polling_for_updates()
            
        except Exception as e:
            logger.error(f"Failed to setup real-time subscription: {e}")
            # Fall back to polling
            self._start_polling_for_updates()
    
    def _start_polling_for_updates(self):
        """Poll server for updates (fallback if real-time doesn't work)"""
        def poll_loop():
            while self._running:
                try:
                    # Check for updates every 5 minutes
                    time.sleep(300)
                    if not self.pending_update:
                        self._fetch_pending_update()
                except Exception as e:
                    logger.error(f"Error in polling loop: {e}")
        
        poll_thread = threading.Thread(target=poll_loop, daemon=True)
        poll_thread.start()
        logger.info("Started polling for updates (fallback mode)")
    
    def _fetch_pending_update(self):
        """Fetch pending update from server"""
        try:
            url = f"{self.server_url}/api/v1/devices/{self.device_uuid}/updates/check"
            headers = {"X-API-Key": self.api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    self.pending_update = data
                    logger.info(f"Pending update detected: {data.get('latest_version')}")
                else:
                    self.pending_update = None
            else:
                logger.warning(f"Failed to check for updates: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch pending update: {e}")
    
    def _process_pending_update(self):
        """Process a pending update based on type and schedule"""
        try:
            if not self.pending_update:
                return
            
            update_info = self.pending_update.get("update_info", {})
            device_update = self.pending_update.get("device_update", {})
            
            update_type = update_info.get("update_type", "scheduled")
            scheduled_for_str = device_update.get("scheduled_for")
            
            # Determine if we should apply the update now
            should_apply = False
            
            if update_type == "urgent":
                # Urgent update: wait for 1 hour of inactivity
                if self.activity_tracker.is_inactive_for(3600):  # 1 hour = 3600 seconds
                    logger.info("Urgent update ready: device inactive for 1 hour")
                    should_apply = True
                else:
                    inactivity = self.activity_tracker.get_inactivity_duration_seconds()
                    logger.debug(f"Waiting for inactivity: {inactivity:.0f}s / 3600s")
            else:
                # Scheduled update: check if it's time (2 AM local time)
                if scheduled_for_str:
                    scheduled_for = datetime.fromisoformat(scheduled_for_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    
                    if now >= scheduled_for:
                        logger.info("Scheduled update ready: time has arrived")
                        should_apply = True
                    else:
                        time_diff = (scheduled_for - now).total_seconds()
                        logger.debug(f"Waiting for scheduled time: {time_diff:.0f}s remaining")
            
            # Apply update if ready
            if should_apply:
                self._apply_update()
        
        except Exception as e:
            logger.error(f"Error processing pending update: {e}")
    
    def _apply_update(self):
        """Download and apply the update"""
        if self.update_in_progress:
            logger.warning("Update already in progress")
            return
        
        try:
            self.update_in_progress = True
            logger.info("Starting update process...")
            
            update_info = self.pending_update.get("update_info", {})
            device_update = self.pending_update.get("device_update", {})
            
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
            
            # Clear pending update
            self.pending_update = None
            
            # Restart service after successful update
            self._restart_service()
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            # Report failure
            if self.pending_update:
                update_id = self.pending_update.get("update_info", {}).get("id")
                self._report_status(update_id, "failed", error_message=str(e))
            
            self.update_in_progress = False
    
    def _download_update(self, update_id: str, version: str) -> Optional[Path]:
        """
        Download update package from server.
        
        Args:
            update_id: Update UUID
            version: Update version
            
        Returns:
            Path to downloaded file or None if failed
        """
        try:
            url = f"{self.server_url}/api/v1/updates/{update_id}/download"
            headers = {"X-API-Key": self.api_key}
            
            logger.info(f"Downloading update {version}...")
            
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
            logger.info(f"Downloaded {file_size} bytes to {temp_file}")
            
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
        Report update status to server.
        
        Args:
            update_id: Update UUID
            status: Status (downloading, installing, completed, failed)
            error_message: Optional error message if failed
        """
        try:
            url = f"{self.server_url}/api/v1/updates/{update_id}/status"
            headers = {
                "X-API-Key": self.api_key,
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


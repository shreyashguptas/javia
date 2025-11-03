"""Device manager for Pi client registration and identification"""
import os
import logging
import platform
import socket
from pathlib import Path
from typing import Optional, Dict, Any
from uuid6 import uuid7
import requests

logger = logging.getLogger(__name__)

# Device UUID storage location (persists across updates)
DEVICE_UUID_FILE = Path.home() / ".javia_device_uuid"

# Version file location
VERSION_FILE = Path(__file__).parent / "VERSION"


class DeviceManager:
    """Manages device identification and registration with server"""
    
    def __init__(self, server_url: str, api_key: Optional[str] = None, timezone: str = "UTC"):
        """
        Initialize device manager.
        
        Args:
            server_url: Server URL
            api_key: Optional API key for admin operations (not used for device auth)
            timezone: Device timezone (e.g., 'America/Los_Angeles')
        """
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key  # Optional - only needed for admin operations
        self.timezone = timezone
        self.device_uuid: Optional[str] = None
        self.current_version: str = "v0.0.0"
        
        # Load or generate device UUID
        self._load_or_generate_uuid()
        
        # Load current version
        self._load_version()
    
    def _load_or_generate_uuid(self):
        """Load existing UUID or generate a new one"""
        try:
            if DEVICE_UUID_FILE.exists():
                # Load existing UUID
                with open(DEVICE_UUID_FILE, 'r') as f:
                    self.device_uuid = f.read().strip()
                logger.info(f"Loaded device UUID: {self.device_uuid}")
                print(f"Loaded device UUID: {self.device_uuid}")
            else:
                # Generate new UUID7
                self.device_uuid = str(uuid7())
                
                # Save to file
                DEVICE_UUID_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(DEVICE_UUID_FILE, 'w') as f:
                    f.write(self.device_uuid)
                
                # Secure the file
                os.chmod(DEVICE_UUID_FILE, 0o600)
                
                logger.info(f"Generated new device UUID: {self.device_uuid}")
                print(f"Generated new device UUID: {self.device_uuid}")
        except Exception as e:
            logger.error(f"Failed to load/generate device UUID: {e}")
            print(f"Failed to load/generate device UUID: {e}")
            # Fallback to in-memory UUID
            self.device_uuid = str(uuid7())
    
    def _load_version(self):
        """Load current software version from VERSION file"""
        try:
            if VERSION_FILE.exists():
                with open(VERSION_FILE, 'r') as f:
                    self.current_version = f.read().strip()
                logger.info(f"Current version: {self.current_version}")
            else:
                logger.warning("VERSION file not found, using default: v0.0.0")
        except Exception as e:
            logger.error(f"Failed to load version: {e}")
    
    def _get_device_metadata(self) -> Dict[str, Any]:
        """Collect device metadata"""
        try:
            metadata = {
                "hardware_model": self._get_hardware_model(),
                "os_version": platform.platform(),
                "python_version": platform.python_version(),
                "hostname": socket.gethostname(),
            }
            
            # Try to get IP address
            try:
                # Create a socket to determine local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                metadata["ip_address"] = s.getsockname()[0]
                s.close()
            except Exception:
                pass
            
            # Try to get MAC address
            try:
                import uuid
                metadata["mac_address"] = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
            except Exception:
                pass
            
            return metadata
        except Exception as e:
            logger.error(f"Failed to collect device metadata: {e}")
            return {}
    
    def _get_hardware_model(self) -> str:
        """Detect Raspberry Pi hardware model"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Model'):
                        return line.split(':', 1)[1].strip()
        except Exception:
            pass
        return "Unknown"
    
    def register(self, device_name: Optional[str] = None) -> bool:
        """
        Register device with server.
        
        Args:
            device_name: Optional friendly name for the device
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/devices/register"
            headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            data = {
                "device_uuid": self.device_uuid,
                "timezone": self.timezone,
                "device_name": device_name,
                "metadata": self._get_device_metadata()
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Device registered successfully: {self.device_uuid}")
                return True
            else:
                logger.error(f"Device registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return False
    
    def send_heartbeat(self, status: str = "online") -> bool:
        """
        Send heartbeat to server using device UUID authentication.
        
        Args:
            status: Device status (online, offline, updating)
            
        Returns:
            True if heartbeat successful, False otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/devices/{self.device_uuid}/heartbeat"
            headers = {
                "X-Device-UUID": self.device_uuid,
                "Content-Type": "application/json"
            }
            
            data = {
                "current_version": self.current_version,
                "status": status,
                "metadata": self._get_device_metadata()
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.debug(f"Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                print(f"Heartbeat failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")
            print(f"Heartbeat failed (server may be unreachable)")
            return False
    
    def check_for_updates(self) -> Optional[Dict[str, Any]]:
        """
        Check if there are pending updates for this device using device UUID authentication.
        
        Returns:
            Update info dict if update available, None otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/devices/{self.device_uuid}/updates/check"
            headers = {
                "X-Device-UUID": self.device_uuid
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("update_available"):
                    logger.info(f"Update available: {data.get('latest_version')}")
                    return data
                else:
                    logger.debug("No updates available")
                    return None
            else:
                logger.warning(f"Update check failed: {response.status_code}")
                print(f"Update check failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            return None
    
    def update_status(self, status: str) -> bool:
        """
        Update device status on server.
        
        Args:
            status: New status (online, offline, updating)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.server_url}/api/v1/devices/{self.device_uuid}/status"
            headers = {
                "X-API-Key": self.api_key
            }
            params = {"status": status}
            
            response = requests.patch(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Device status updated: {status}")
                return True
            else:
                logger.warning(f"Status update failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Failed to update status: {e}")
            return False
    
    def get_device_uuid(self) -> str:
        """Get device UUID"""
        return self.device_uuid
    
    def get_current_version(self) -> str:
        """Get current software version"""
        return self.current_version


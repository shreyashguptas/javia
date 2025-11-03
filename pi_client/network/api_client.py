#!/usr/bin/env python3
"""
API Client for Pi Voice Assistant Client
Handles HTTP communication with the server
"""

import time
import requests
from urllib.parse import unquote
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import config
from audio.codec import decompress_from_opus


class APIClient:
    """
    HTTP client for voice assistant server communication.
    
    Features:
    - Device UUID authentication
    - Persistent HTTP sessions (connection reuse)
    - Automatic retries on connection errors
    - Opus compression for efficient transfer
    """
    
    def __init__(self, device_manager):
        """
        Initialize API client.
        
        Args:
            device_manager: DeviceManager instance for authentication
        """
        self.device_manager = device_manager
        self.server_url = config.SERVER_URL
        self._session = None
    
    def _get_http_session(self):
        """
        Get or create persistent HTTP session.
        
        PERFORMANCE OPTIMIZATION:
        - Connection reuse (TCP handshake only once)
        - Keep-alive connections
        - Reduced latency on subsequent requests
        
        AUTHENTICATION:
        - Uses device UUID for authentication (X-Device-UUID header)
        - No shared API keys - each device has unique identifier
        """
        if self._session is None:
            self._session = requests.Session()
            
            # Get device UUID from device_manager
            if self.device_manager is None:
                print("[ERROR] Device manager not initialized!")
                raise RuntimeError("Device manager must be initialized before making requests")
            
            device_uuid = self.device_manager.get_device_uuid()
            
            # Configure for optimal performance with device authentication
            self._session.headers.update({
                'Connection': 'keep-alive',
                'X-Device-UUID': device_uuid
            })
            
            # Retry on connection errors
            retry_strategy = Retry(
                total=2,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=1, pool_maxsize=1)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        
        return self._session
    
    def send_audio_to_server(self):
        """
        Send audio to server as WAV format.
        
        OPTIMIZATIONS:
        - Connection reuse (keep-alive)
        - Streaming upload (memory efficient)
        - Server-side gain amplification
        - No compression needed (Pi 5 has plenty of bandwidth)
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Send heartbeat to server (includes activity tracking)
        if self.device_manager:
            self.device_manager.send_heartbeat()
        
        print("[SERVER] Preparing audio for upload...")
        
        if not config.RECORDING_FILE.exists():
            print("[ERROR] Recording file not found")
            return False
        
        # Send WAV directly (no compression - Pi 5 has plenty of bandwidth)
        wav_file_size = config.RECORDING_FILE.stat().st_size
        if wav_file_size < 1000:
            print(f"[ERROR] Recording file too small ({wav_file_size} bytes)")
            return False
        
        try:
            session = self._get_http_session()
            
            with open(config.RECORDING_FILE, 'rb') as audio_file:
                files = {
                    'audio': ('recording.wav', audio_file, 'audio/wav')
                }
                data = {
                    'session_id': None,  # TODO: Implement session management
                    'microphone_gain': str(config.MICROPHONE_GAIN)  # Server will amplify audio
                }
                
                if config.VERBOSE_OUTPUT:
                    print(f"[SERVER] Uploading {wav_file_size} bytes WAV (gain: {config.MICROPHONE_GAIN}x on server)...")
                upload_start = time.time()
                
                # Send request with persistent session (faster than new connection)
                response = session.post(
                    f"{self.server_url}/api/v1/process",
                    files=files,
                    data=data,
                    timeout=120,
                    stream=True
                )
                
                upload_time = time.time() - upload_start
                if config.VERBOSE_OUTPUT:
                    print(f"[SERVER] Upload complete ({upload_time:.2f}s)")
                
                if config.VERBOSE_OUTPUT:
                    print(f"[SERVER] Response code: {response.status_code}")
                
                if response.status_code == 200:
                    # Get metadata from headers (URL-decode to handle Unicode characters)
                    transcription = unquote(response.headers.get('X-Transcription', ''))
                    llm_response = unquote(response.headers.get('X-LLM-Response', ''))
                    
                    print(f"[SUCCESS] Transcription: \"{transcription}\"")
                    print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
                    
                    # Save response audio (Opus format)
                    total_bytes = 0
                    with open(config.RESPONSE_OPUS_FILE, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                total_bytes += len(chunk)
                    
                    if total_bytes == 0:
                        print("[ERROR] Received empty audio file")
                        return False
                    
                    if config.VERBOSE_OUTPUT:
                        print(f"[SUCCESS] Opus audio saved: {config.RESPONSE_OPUS_FILE} ({total_bytes} bytes)")
                    
                    # Decompress Opus to WAV for playback
                    if not decompress_from_opus(config.RESPONSE_OPUS_FILE, config.RESPONSE_FILE):
                        print("[ERROR] Failed to decompress response audio")
                        return False
                    
                    return True
                    
                elif response.status_code == 401:
                    print("[ERROR] Unauthorized")
                    return False
                elif response.status_code == 403:
                    print("[ERROR] Forbidden - Device not registered or not authorized")
                    print(f"[ERROR] Device UUID: {self.device_manager.get_device_uuid()}")
                    print("[ERROR] ")
                    print("[ERROR] This device must be registered on the server.")
                    print("[ERROR] On your server, SSH in and run:")
                    print(f"[ERROR]   cd /opt/javia/scripts/register_device")
                    print(f"[ERROR]   sudo ./register_device.sh {self.device_manager.get_device_uuid()}")
                    return False
                else:
                    print(f"[ERROR] Server error {response.status_code}: {response.text}")
                    return False
                    
        except requests.exceptions.Timeout:
            print("[ERROR] Request timeout - server took too long to respond")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] Connection error: {e}")
            print("[ERROR] Check if server is running and accessible")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to communicate with server: {e}")
            import traceback
            print(f"[DEBUG] {traceback.format_exc()}")
            return False


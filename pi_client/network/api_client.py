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
from audio.codec import decompress_from_opus, compress_to_opus, stream_decompress_from_opus_iter


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
        Send audio to server as Opus format.
        
        OPTIMIZATIONS:
        - Connection reuse (keep-alive)
        - Streaming upload (memory efficient)
        - Server-side gain amplification
        - Opus compression for 10x smaller uploads
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Send heartbeat to server (includes activity tracking)
        if self.device_manager:
            self.device_manager.send_heartbeat()
        
        if not config.RECORDING_FILE.exists():
            print("[ERROR] Recording file not found")
            return False

        # Prepare Opus (mono, 24k) for upload to reduce latency
        wav_file_size = config.RECORDING_FILE.stat().st_size
        if wav_file_size < 1000:
            print(f"[ERROR] Recording file too small ({wav_file_size} bytes)")
            return False

        try:
            session = self._get_http_session()
            
            # Load session ID from persistent storage
            session_id = config.get_session_id()
            
            # Encode to Opus
            encode_start = time.time()
            if not compress_to_opus(config.RECORDING_FILE, config.RECORDING_OPUS_FILE, bitrate=config.OPUS_BITRATE):
                print("[ERROR] Failed to encode Opus")
                return False
            encode_ms = int((time.time() - encode_start) * 1000)
            opus_size = config.RECORDING_OPUS_FILE.stat().st_size if config.RECORDING_OPUS_FILE.exists() else 0
            
            with open(config.RECORDING_OPUS_FILE, 'rb') as audio_file:
                files = {
                    'audio': ('recording.opus', audio_file, 'audio/opus')
                }
                data = {
                    'session_id': session_id,
                    'microphone_gain': str(config.MICROPHONE_GAIN)  # Server will amplify audio
                }

                if config.VERBOSE_OUTPUT:
                    print(f"[METRIC] encode_ms={encode_ms}")
                    print(f"[SERVER] Uploading {opus_size} bytes OPUS (gain: {config.MICROPHONE_GAIN}x on server)...")
                # Telemetry timing points
                stop_to_upload_start_ms = None
                if getattr(config, 'LAST_RECORD_END_TS', None):
                    stop_to_upload_start_ms = max(0, int((time.time() - config.LAST_RECORD_END_TS) * 1000))
                upload_start = time.time()

                # Send request with persistent session (faster than new connection)
                response = session.post(
                    f"{self.server_url}/api/v1/process",
                    files=files,
                    data=data,
                    timeout=120,
                    stream=True
                )

                try:
                    ttfb_start = upload_start
                    upload_time = time.time() - upload_start
                    if config.VERBOSE_OUTPUT:
                        if stop_to_upload_start_ms is not None:
                            print(f"[METRIC] stop_to_upload_start_ms={stop_to_upload_start_ms}")
                        print(f"[METRIC] upload_ms={int(upload_time*1000)}")

                    if config.VERBOSE_OUTPUT:
                        print(f"[SERVER] Response code: {response.status_code}")
                    
                    if response.status_code == 200:
                        # Get metadata from headers (URL-decode to handle Unicode characters)
                        transcription = unquote(response.headers.get('X-Transcription', ''))
                        llm_response = unquote(response.headers.get('X-LLM-Response', ''))
                        new_session_id = unquote(response.headers.get('X-Session-ID', ''))
                        if config.VERBOSE_OUTPUT:
                            transcribe_ms = response.headers.get('X-Stage-Transcribe-ms', 'N/A')
                            llm_ms = response.headers.get('X-Stage-LLM-ms', 'N/A')
                            tts_ms = response.headers.get('X-Stage-TTS-ms', 'N/A')
                            total_ms = response.headers.get('X-Stage-Total-ms', 'N/A')
                            print(f"[METRIC] server_stages_ms transcribe={transcribe_ms} llm={llm_ms} tts={tts_ms} total={total_ms}")
                        
                        # Update session ID if server returned a new one
                        if new_session_id and new_session_id != session_id:
                            if config.save_session_id(new_session_id):
                                if config.VERBOSE_OUTPUT:
                                    print(f"[DEBUG] Updated session ID: {new_session_id}")
                        
                        print(f"[SUCCESS] Transcription: \"{transcription}\"")
                        print(f"[SUCCESS] LLM Response: \"{llm_response}\"")
                        
                        # Stream-decode Opus to WAV while downloading
                        total_bytes = 0
                        first_chunk_time = None
                        ttfb_ms = None
                        download_start = time.time()
                        def _iter_and_count():
                            nonlocal total_bytes, first_chunk_time, ttfb_ms
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    if first_chunk_time is None:
                                        first_chunk_time = time.time()
                                        ttfb_ms = int((first_chunk_time - ttfb_start) * 1000)
                                    total_bytes += len(chunk)
                                    yield chunk
                        ok = stream_decompress_from_opus_iter(_iter_and_count(), config.RESPONSE_FILE)
                        
                        if total_bytes == 0 or not ok:
                            print("[ERROR] Received empty audio file")
                            return False
                        
                        if config.VERBOSE_OUTPUT:
                            print(f"[SUCCESS] Audio response received ({total_bytes} bytes)")
                            if ttfb_ms is not None:
                                print(f"[METRIC] ttfb_ms={ttfb_ms}")
                            print(f"[METRIC] download_ms={int((time.time()-download_start)*1000)}")

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
                finally:
                    try:
                        response.close()
                    except Exception:
                        pass
                    
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


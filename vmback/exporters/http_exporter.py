"""
HTTP exporter - direct XenAPI HTTP calls (no xe CLI required)
"""

import logging
import time
import sys
from pathlib import Path
from typing import Dict, Any

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None
    HTTPAdapter = None
    Retry = None

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None

from .base import BaseExporter, ExportError
from ..utils import format_bytes, format_duration

logger = logging.getLogger(__name__)


class HttpExporter(BaseExporter):
    """
    Exporter using direct HTTP API calls to XCP-ng
    
    Advantages:
    - No external dependencies (except requests library)
    - Faster (no shell overhead)
    - Native progress tracking
    - Works on any platform
    
    XenAPI HTTP Export URLs:
    - Pool metadata: GET /pool/xmldbdump?session_id={session_id}
    - VM metadata: GET /export_metadata?session_id={session_id}&uuid={vm_uuid}
    - Full VM: GET /export?session_id={session_id}&uuid={vm_uuid}
    - VDI: GET /export_raw_vdi?session_id={session_id}&vdi={vdi_uuid}&format=vhd
    """
    
    def __init__(self, session, config: Dict[str, Any]):
        """Initialize HTTP exporter with session and config"""
        super().__init__(session, config)
        
        # Check if requests library is available
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "HTTP export requires 'requests' library. "
                "Install with: pip install requests urllib3"
            )
        
        # Get HTTP export settings
        http_config = config.get('export', {}).get('http', {})
        self.scheme = http_config.get('scheme', 'http')
        self.verify_ssl = http_config.get('verify_ssl', False)
        self.timeout = http_config.get('timeout', 3600)
        self.chunk_size = http_config.get('chunk_size', 8388608)  # 8MB default
        
        # Get session ID for HTTP requests
        self.session_id = session._session
        
        # Configure requests session with retries
        self.http_session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session.mount("http://", adapter)
        self.http_session.mount("https://", adapter)
        
        logger.debug(f"HTTP exporter initialized: {self.scheme}, verify_ssl={self.verify_ssl}")
    
    def _build_url(self, host: str, path: str, params: Dict[str, str] = None) -> str:
        """Build full URL for XenAPI HTTP endpoint"""
        base_url = f"{self.scheme}://{host}"
        
        if params is None:
            params = {}
        
        # Always include session ID
        params['session_id'] = self.session_id
        
        # Build query string
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        
        return f"{base_url}{path}?{query}"
    
    def _download_file(self, url: str, filename: str, description: str = "Downloading") -> bool:
        """
        Download file from URL with progress tracking
        
        Args:
            url: URL to download from
            filename: Local file to save to
            description: Description for logging
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"{description} via HTTP")
        logger.debug(f"URL: {url.replace(self.session_id, '[REDACTED]')}")  # Redact session ID
        
        response = None
        use_progress_bar = TQDM_AVAILABLE and sys.stdout.isatty()
        
        try:
            # Start download
            start_time = time.time()
            
            response = self.http_session.get(
                url,
                stream=True,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            # Get total size if available
            total_size = int(response.headers.get('Content-Length', 0))
            
            if total_size > 0:
                logger.info(f"Total size: {format_bytes(total_size)}")
            
            # Download with progress tracking
            downloaded = 0
            last_log_time = time.time()
            log_interval = 5.0  # Log progress every 5 seconds (for non-TTY)
            
            # Initialize progress bar if available and in TTY
            progress_bar = None
            if use_progress_bar and total_size > 0:
                # We have total size - use percentage-based progress
                progress_bar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=description,
                    ncols=100
                )
            elif total_size == 0:
                # No total size - fall back to log-based progress
                logger.debug(f"{description} (size unknown, using log-based progress)")
                use_progress_bar = False
            
            try:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress bar if available
                            if progress_bar:
                                progress_bar.update(len(chunk))
                            
                            # Log progress periodically (for non-TTY or if no progress bar)
                            if not progress_bar:
                                current_time = time.time()
                                if current_time - last_log_time >= log_interval:
                                    if total_size > 0:
                                        percent = (downloaded / total_size) * 100
                                        speed = downloaded / (current_time - start_time)
                                        logger.info(
                                            f"Progress: {format_bytes(downloaded)}/{format_bytes(total_size)} "
                                            f"({percent:.1f}%) at {format_bytes(speed)}/s"
                                        )
                                    else:
                                        speed = downloaded / (current_time - start_time)
                                        logger.info(
                                            f"Downloaded: {format_bytes(downloaded)} at {format_bytes(speed)}/s"
                                        )
                                    last_log_time = current_time
            finally:
                if progress_bar:
                    progress_bar.close()
            
            # Final statistics
            elapsed = time.time() - start_time
            file_size = Path(filename).stat().st_size
            speed = file_size / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"Download complete: {format_bytes(file_size)} in {format_duration(elapsed)} "
                f"({format_bytes(speed)}/s)"
            )
            
            return True
            
        except KeyboardInterrupt:
            logger.warning("Download interrupted by user (Ctrl+C)")
            logger.info("Waiting for XenAPI export operation to cancel...")
            
            # Close the response connection to signal cancellation
            if response is not None:
                try:
                    response.close()
                except:
                    pass
            
            # Wait a bit for XenAPI to process the cancellation
            # This prevents "VDI_IN_USE" errors during cleanup
            logger.info("Waiting 10 seconds for export to cancel...")
            time.sleep(10)
            
            logger.info("Export cancelled, cleanup will proceed")
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error during download: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during download: {e}")
            return False
        finally:
            # Always close response if it exists
            if response is not None:
                try:
                    response.close()
                except:
                    pass
    
    def export_pool_metadata(self, pool: Dict[str, Any], filename: str) -> bool:
        """Export pool metadata via HTTP"""
        logger.info(f"Exporting pool metadata to '{filename}' (via HTTP)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build URL: GET /pool/xmldbdump?session_id={session_id}
        url = self._build_url(pool['master'], '/pool/xmldbdump')
        
        return self._download_file(url, filename, "Exporting pool metadata")
    
    def export_vm_metadata(self, vm: Dict[str, Any], pool: Dict[str, Any], filename: str) -> bool:
        """Export VM metadata via HTTP"""
        vm_uuid = vm['uuid']
        vm_name = vm['name_label']
        
        logger.info(f"Exporting VM metadata to '{filename}' (via HTTP)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build URL: GET /export_metadata?session_id={session_id}&uuid={vm_uuid}
        url = self._build_url(
            pool['master'],
            '/export_metadata',
            {'uuid': vm_uuid}
        )
        
        return self._download_file(url, filename, f"Exporting VM metadata for {vm_name}")
    
    def export_vm_full(self, vm_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """Export full VM via HTTP"""
        logger.info(f"Exporting VM to '{filename}' (via HTTP)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build URL: GET /export?session_id={session_id}&uuid={vm_uuid}
        url = self._build_url(
            pool['master'],
            '/export',
            {'uuid': vm_snapshot_uuid}
        )
        
        return self._download_file(url, filename, "Exporting VM")
    
    def export_vdi(self, vdi_snapshot_uuid: str, pool: Dict[str, Any], filename: str) -> bool:
        """Export VDI via HTTP"""
        logger.info(f"Exporting VDI to '{filename}' (via HTTP)")
        
        # Remove existing file
        file_path = Path(filename)
        if file_path.exists():
            logger.warning(f"File '{filename}' exists, removing it")
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Error removing existing file: {e}")
                return False
        
        # Build URL: GET /export_raw_vdi?session_id={session_id}&vdi={vdi_uuid}&format=vhd
        url = self._build_url(
            pool['master'],
            '/export_raw_vdi',
            {'vdi': vdi_snapshot_uuid, 'format': 'vhd'}
        )
        
        return self._download_file(url, filename, "Exporting VDI")

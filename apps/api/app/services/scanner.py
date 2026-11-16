"""Malware scanner service with ClamAV-compatible abstraction and fail-safe enforcement.

In accordance with Package C:
- Clear, distinct scan states: CLEAN, INFECTED, UNAVAILABLE, ERROR.
- Crucial invariant: Scanner failure or unavailability MUST NOT silently mark a document clean.
- Configurable test mock with built-in EICAR antivirus test file detection for CI.
- Network ClamAV daemon (clamd) client with timeouts and fail-closed error handling.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import socket
import struct
import threading
from typing import Any, Dict, Optional

from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)

# Standard EICAR Antivirus Test Signature (harmless test string recognized by all standard scanners)
EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class ScanStatus(str, Enum):
    """Explicit malware scan outcomes."""
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ScanResult:
    """Outcome of a malware scan."""
    status: ScanStatus
    virus_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class BaseMalwareScanner(ABC):
    """Abstract interface for malware scanning engines."""

    @abstractmethod
    def scan(self, data: bytes) -> ScanResult:
        """Scans binary content for malware.
        
        Must return ScanResult with explicit status. Must fail safe if scanning cannot complete.
        """
        pass


class MockMalwareScanner(BaseMalwareScanner):
    """Test double and CI implementation of malware scanner.
    
    Features:
    1. Detects standard EICAR test string and reports INFECTED.
    2. Allows simulated scan statuses (CLEAN, INFECTED, UNAVAILABLE, ERROR) for comprehensive testing.
    """

    def __init__(self, default_status: ScanStatus = ScanStatus.CLEAN):
        self._default_status = default_status
        self._forced_status: Optional[ScanStatus] = None
        self._forced_virus_name: Optional[str] = None
        self._lock = threading.Lock()

    def set_forced_outcome(self, status: Optional[ScanStatus], virus_name: Optional[str] = None) -> None:
        """Test helper to simulate specific scanner failures or detections."""
        with self._lock:
            self._forced_status = status
            self._forced_virus_name = virus_name

    def scan(self, data: bytes) -> ScanResult:
        with self._lock:
            # Check for simulated forced outcome
            if self._forced_status is not None:
                return ScanResult(
                    status=self._forced_status,
                    virus_name=self._forced_virus_name,
                    details={"simulated": True, "forced_status": self._forced_status.value},
                )

        # Built-in check for standard EICAR test string
        if EICAR_SIGNATURE in data:
            logger.warning("eicar_test_signature_detected", scanner="MockMalwareScanner")
            return ScanResult(
                status=ScanStatus.INFECTED,
                virus_name="Win.Test.EICAR_HDB-1",
                details={"signature": "EICAR-Standard-Antivirus-Test-File"},
            )

        return ScanResult(
            status=self._default_status,
            virus_name=None,
            details={"scanner": "MockMalwareScanner", "bytes_scanned": len(data)},
        )


class ClamAVScanner(BaseMalwareScanner):
    """Network scanner interfacing with a remote or local ClamAV daemon (clamd) via TCP.
    
    Protocol:
    - Sends 'zINSTREAM\\0' command followed by chunked data: [4-byte big-endian length][chunk].
    - Ends stream with 4-byte 0x00000000.
    - Reads line response: e.g. 'stream: OK' or 'stream: <VirusName> FOUND'.
    
    Fail-safe behavior:
    - If clamd is unreachable, times out, or returns a protocol error, returns ScanStatus.UNAVAILABLE.
    - Never marks clean on error.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.host = host or getattr(settings, "CLAMAV_HOST", "localhost")
        self.port = port or getattr(settings, "CLAMAV_PORT", 3310)
        self.timeout = timeout_seconds or getattr(settings, "CLAMAV_TIMEOUT_SECONDS", 5.0)

    def scan(self, data: bytes) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                # Send zINSTREAM command (null-terminated)
                sock.sendall(b"zINSTREAM\x00")

                # Stream chunks in max 64KB segments
                chunk_size = 64 * 1024
                offset = 0
                while offset < len(data):
                    chunk = data[offset : offset + chunk_size]
                    # Pack 4-byte big-endian unsigned int for chunk length
                    length_header = struct.pack(">I", len(chunk))
                    sock.sendall(length_header + chunk)
                    offset += chunk_size

                # Send 0-length chunk to terminate instream
                sock.sendall(struct.pack(">I", 0))

                # Read response until newline or EOF
                response = b""
                while True:
                    buf = sock.recv(1024)
                    if not buf:
                        break
                    response += buf
                    if b"\n" in response or b"\x00" in response:
                        break

                decoded = response.decode("utf-8", errors="replace").strip()
                if "stream: OK" in decoded or decoded == "OK":
                    return ScanResult(
                        status=ScanStatus.CLEAN,
                        details={"clamav_response": decoded},
                    )
                elif "FOUND" in decoded:
                    # Format: 'stream: Eicar-Signature FOUND'
                    parts = decoded.split(":")
                    virus_name = "UnknownVirus"
                    if len(parts) >= 2:
                        virus_part = parts[1].replace("FOUND", "").strip()
                        virus_name = virus_part or virus_name
                    logger.warning("clamav_virus_detected", virus_name=virus_name)
                    return ScanResult(
                        status=ScanStatus.INFECTED,
                        virus_name=virus_name,
                        details={"clamav_response": decoded},
                    )
                else:
                    logger.error("clamav_unexpected_response", response=decoded)
                    return ScanResult(
                        status=ScanStatus.ERROR,
                        details={"error": f"Unexpected clamd response: {decoded}"},
                    )

        except (socket.timeout, TimeoutError) as e:
            logger.error("clamav_scan_timeout", host=self.host, port=self.port, error=str(e))
            return ScanResult(
                status=ScanStatus.UNAVAILABLE,
                details={"error": f"ClamAV connection timed out ({self.timeout}s): {e}"},
            )
        except (ConnectionRefusedError, OSError) as e:
            logger.error("clamav_connection_failed", host=self.host, port=self.port, error=str(e))
            return ScanResult(
                status=ScanStatus.UNAVAILABLE,
                details={"error": f"Unable to connect to ClamAV daemon at {self.host}:{self.port}: {e}"},
            )
        except Exception as e:
            logger.exception("clamav_scan_exception", error=str(e))
            return ScanResult(
                status=ScanStatus.ERROR,
                details={"error": f"ClamAV scanner error: {e}"},
            )


# Global scanner instance
_scanner_instance: Optional[BaseMalwareScanner] = None
_scanner_lock = threading.Lock()


def get_malware_scanner() -> BaseMalwareScanner:
    """Returns the configured malware scanner instance."""
    global _scanner_instance
    with _scanner_lock:
        if _scanner_instance is None:
            scanner_type = getattr(settings, "MALWARE_SCANNER_TYPE", "mock").lower()
            if scanner_type == "clamav":
                _scanner_instance = ClamAVScanner()
            else:
                _scanner_instance = MockMalwareScanner()
    return _scanner_instance


def set_malware_scanner(scanner: BaseMalwareScanner) -> None:
    """Allows tests to inject a configured scanner instance."""
    global _scanner_instance
    with _scanner_lock:
        _scanner_instance = scanner

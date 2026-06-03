import logging
import struct
import socket as socket_module
import threading

log = logging.getLogger('socket_utils')

SOCKET_TIMEOUT = 2.0  # 2 second timeout (was 5s, reducing for faster failure detection)

# Global lock to prevent concurrent socket access from multiple threads
_socket_lock = threading.Lock()

def _flush_socket(sock) -> None:
    """
    Drain any pending data from sock so that our next recv()
    only sees the fresh response to the command we send.
    """
    # Switch to non-blocking so recv() returns immediately if no data
    sock.setblocking(False)
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
    except (BlockingIOError, OSError):
        # No more data to read
        pass
    finally:
        # Restore timeout mode (not infinite blocking)
        sock.settimeout(SOCKET_TIMEOUT)

def readrange(sock, address: str, length: str) -> bytes:
    """Read memory range with timeout protection and thread safety"""
    with _socket_lock:  # Prevent concurrent access
        log.debug(f"[READRANGE] addr={hex(address)} len={length}")
        _flush_socket(sock)
        cmd = f"READRANGE {address} {length}\n".encode('utf-8')

        # Send with timeout
        sock.settimeout(SOCKET_TIMEOUT)
        try:
            sock.sendall(cmd)
            log.debug("[READRANGE] Command sent")
        except socket_module.timeout:
            log.error(f"[READRANGE] TIMEOUT sending command!")
            raise RuntimeError(f"Timeout sending READRANGE command (addr={hex(address)})")
        except Exception as e:
            log.error(f"[READRANGE] ERROR sending: {e}")
            raise RuntimeError(f"Failed to send READRANGE command: {e}")

        # Read header with timeout
        try:
            log.debug("[READRANGE] Waiting for header...")
            hdr = sock.recv(4)
            log.debug(f"[READRANGE] Got header: {len(hdr)} bytes")
        except socket_module.timeout:
            log.error("[READRANGE] TIMEOUT on header!")
            raise RuntimeError(f"Timeout waiting for READRANGE header (addr={hex(address)}, len={length})")
        except Exception as e:
            log.error(f"[READRANGE] ERROR on header: {e}")
            raise RuntimeError(f"Error receiving READRANGE header: {e}")

        if len(hdr) < 4:
            raise RuntimeError("socket closed during READRANGE header")
        size = struct.unpack(">I", hdr)[0]
        log.debug(f"[READRANGE] Reading {size} bytes of data...")

        # Read data with timeout
        data = bytearray()
        try:
            while len(data) < size:
                chunk = sock.recv(min(4096, size - len(data)))
                if not chunk:
                    raise RuntimeError("socket closed mid-dump")
                data.extend(chunk)
        except socket_module.timeout:
            log.error(f"[READRANGE] TIMEOUT on data! Got {len(data)}/{size}")
            raise RuntimeError(f"Timeout receiving READRANGE data. Got {len(data)}/{size} bytes")

        log.debug(f"[READRANGE] Success! Got {len(data)} bytes")
        return bytes(data)


def send_command(sock, cmd: str) -> str:
    """Send command and read response with timeout protection and thread safety"""
    with _socket_lock:  # Prevent concurrent access
        _flush_socket(sock)

        sock.settimeout(SOCKET_TIMEOUT)
        try:
            sock.sendall((cmd.strip() + "\n").encode('utf-8'))
        except socket_module.timeout:
            raise RuntimeError(f"Timeout sending command '{cmd}'")
        except Exception as e:
            raise RuntimeError(f"Failed to send command '{cmd}': {e}")

        data = bytearray()
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    raise RuntimeError("socket closed before full response")
                data.extend(chunk)
                if b"\n" in chunk:
                    break
        except socket_module.timeout:
            raise RuntimeError(f"Timeout waiting for response to command '{cmd}'")

        return data.decode('utf-8').rstrip("\n")

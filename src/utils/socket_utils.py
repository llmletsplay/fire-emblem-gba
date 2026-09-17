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


def reconnect_socket(old_sock=None, host="localhost", port=None, timeout=10):
    """Close old socket (if any) and open a fresh connection to mGBA Lua.

    Waits for the listen port, then probes with a tiny READRANGE so we do not
    hand back a half-dead accept that dies on the next CAP.
    """
    import socket as _socket
    import time as _time
    from src.core import config as _config
    if port is None:
        port = getattr(_config, "PORT", 8888)
    if old_sock is not None:
        try:
            old_sock.close()
        except Exception:
            pass

    last_err = None
    deadline = _time.time() + max(8.0, float(timeout))
    while _time.time() < deadline:
        try:
            sock = _socket.create_connection((host, port), timeout=2)
            sock.settimeout(timeout)
            # Probe: 1-byte read at a safe WRAM address. If Lua is wedged,
            # this fails fast and we retry instead of failing mid-CAP.
            try:
                _flush_socket(sock)
                sock.sendall(b"READRANGE 0x0202BD08 1\n")
                hdr = sock.recv(4)
                if len(hdr) < 4:
                    raise RuntimeError("probe: short header")
                size = int.from_bytes(hdr, "big")
                got = 0
                while got < size:
                    chunk = sock.recv(min(4096, size - got))
                    if not chunk:
                        raise RuntimeError("probe: closed mid-body")
                    got += len(chunk)
                return sock
            except Exception as probe_err:
                last_err = probe_err
                try:
                    sock.close()
                except Exception:
                    pass
                _time.sleep(0.4)
                continue
        except Exception as e:
            last_err = e
            _time.sleep(0.35)
            continue
    raise RuntimeError(f"reconnect_socket failed after wait/probe: {last_err}")

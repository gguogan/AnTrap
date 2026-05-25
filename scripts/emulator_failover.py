"""Spare emulator pool for automatic failover on emulator disconnection.

When a worker detects that its emulator has become unresponsive, it can
request a spare from the shared SpareEmulatorPool and reconnect transparently.
"""

import queue
import subprocess
import threading
import time


class SpareEmulatorPool:
    """Thread-safe pool of spare emulator (console_port, grpc_port) pairs."""

    def __init__(self, console_ports, grpc_ports):
        self._pool = queue.Queue()
        for cp, gp in zip(console_ports, grpc_ports):
            self._pool.put((cp, gp))

    def get(self):
        """Get a spare emulator. Returns (console_port, grpc_port) or None."""
        try:
            return self._pool.get_nowait()
        except queue.Empty:
            return None

    def put_back(self, console_port, grpc_port):
        """Return an emulator to the pool."""
        self._pool.put((console_port, grpc_port))

    @property
    def available(self):
        return self._pool.qsize()


def try_recover_network(adb_path, console_port, timeout=10):
    """Attempt in-place network recovery via airplane-mode toggle.

    Cheap (~10s) and often rescues a transiently broken emulator without
    consuming a spare. Returns True if the emulator passes check_emulator_alive
    afterwards, False otherwise. Does not raise.
    """
    def _adb(args):
        try:
            subprocess.run(
                [adb_path, '-s', f'emulator-{console_port}', 'shell'] + args,
                capture_output=True, text=True, timeout=timeout,
            )
        except Exception:
            pass

    _adb(['cmd', 'connectivity', 'airplane-mode', 'enable'])
    time.sleep(3)
    _adb(['cmd', 'connectivity', 'airplane-mode', 'disable'])
    time.sleep(5)
    _adb(['svc', 'wifi', 'enable'])
    time.sleep(3)
    return check_emulator_alive(adb_path, console_port, timeout=timeout)


def check_emulator_alive(adb_path, console_port, timeout=10, check_network=True):
    """Check that the emulator is responsive AND has working host network.

    Beyond a basic ADB shell echo, this also pings 10.0.2.2 (QEMU's host
    address). Some emulators boot with eth0 link DOWN / ConnectivityService
    not registering it -- adb still works, but apps inside the emulator can't
    reach the host gRPC server, so the a11y forwarder never delivers events
    and the wrapper times out. Treat that state as "not alive" so callers
    can fail over to a spare instead of burning retries.
    """
    try:
        result = subprocess.run(
            [adb_path, '-s', f'emulator-{console_port}', 'shell', 'echo', 'ok'],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0 or 'ok' not in result.stdout:
            return False
        if not check_network:
            return True
        ping = subprocess.run(
            [adb_path, '-s', f'emulator-{console_port}', 'shell',
             'ping', '-c1', '-W2', '10.0.2.2'],
            capture_output=True, text=True, timeout=timeout,
        )
        return ping.returncode == 0
    except Exception:
        return False

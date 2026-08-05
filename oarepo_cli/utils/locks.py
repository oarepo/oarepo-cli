# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""File-based locking mechanism for concurrent execution protection."""

from __future__ import annotations

import atexit
import contextlib
import os
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING

from oarepo_cli.core.errors import LockAcquisitionError

if TYPE_CHECKING:
    from types import TracebackType


class FileLock:
    """
    File-based lock for preventing concurrent executions from corrupting state.

    Uses platform-appropriate locking mechanisms (fcntl on Unix, msvcrt on Windows).
    Supports context manager protocol for automatic release.
    Registers signal handlers and atexit hooks to ensure cleanup on termination.

    Example:
        >>> lock = FileLock("/tmp/myapp.lock", timeout=10.0)
        >>> try:
        ...     lock.acquire()
        ...     # Protected operations here
        ... finally:
        ...     lock.release()

        Or using context manager:
        >>> with FileLock("/tmp/myapp.lock", timeout=10.0):
        ...     # Protected operations here
    """

    # Class-level registry of all active locks for signal handler cleanup
    _active_locks: set[FileLock] = set()
    _signal_handlers_installed = False

    def __init__(
        self,
        lock_path: str | Path,
        timeout: float | None = None,
        *,
        stale_threshold: float = 300.0,
    ) -> None:
        """
        Initialize the file lock.

        Args:
            lock_path: Path to the lock file
            timeout: Maximum time in seconds to wait for lock acquisition.
                    None means wait indefinitely.
            stale_threshold: Time in seconds after which a lock is considered stale
                           (default: 300s = 5 minutes)
        """
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.stale_threshold = stale_threshold
        self._fd: int | None = None
        self._acquired = False

        # Install signal handlers once for all locks
        if not FileLock._signal_handlers_installed:
            self._install_signal_handlers()
            FileLock._signal_handlers_installed = True

    @classmethod
    def _install_signal_handlers(cls) -> None:
        """
        Install signal handlers to release locks on process termination.

        Handles SIGTERM and SIGINT to ensure locks are cleaned up even
        when the process is killed.
        """

        def cleanup_all_locks(signum: int, _frame: object) -> None:
            """Release all active locks and exit."""
            for lock in list(cls._active_locks):
                lock.release()
            # Re-raise the signal to allow normal termination
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        # Register signal handlers
        signal.signal(signal.SIGTERM, cleanup_all_locks)
        signal.signal(signal.SIGINT, cleanup_all_locks)

        # Also use atexit as a fallback for normal exits
        atexit.register(cls._cleanup_all_locks_atexit)

    @classmethod
    def _cleanup_all_locks_atexit(cls) -> None:
        """Clean up all active locks at exit (atexit handler)."""
        for lock in list(cls._active_locks):
            lock.release()

    def acquire(self) -> None:
        """
        Acquire the lock, blocking until available or timeout expires.

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        if self._acquired:
            return

        # Ensure parent directory exists
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        while True:
            try:
                # Try to acquire the lock
                self._try_acquire()
                self._acquired = True
                # Register this lock for signal handler cleanup
                FileLock._active_locks.add(self)
                return
            except OSError:
                # Lock is held by another process
                # Check if it's stale
                if self._is_stale():
                    self._remove_stale_lock()
                    continue

                # Check timeout
                if self.timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= self.timeout:
                        msg = f"Could not acquire lock on {self.lock_path} within {self.timeout}s"
                        raise LockAcquisitionError(msg) from None

                # Wait a bit before retrying
                time.sleep(0.1)

    def _try_acquire(self) -> None:
        """
        Attempt to acquire the lock (non-blocking).

        Raises:
            OSError: If lock is already held
        """
        import platform

        system = platform.system()

        if system == "Windows":
            # Windows: use msvcrt for file locking
            import msvcrt

            # Open or create the lock file
            # Use os.open with O_CREAT | O_EXCL | O_RDWR to atomically create
            try:
                self._fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
            except FileExistsError:
                # File exists, try to lock it
                self._fd = os.open(self.lock_path, os.O_RDWR)
                try:
                    # Use getattr to avoid type checking issues on non-Windows platforms
                    locking = getattr(msvcrt, "locking")  # noqa: B009
                    lk_nblck = getattr(msvcrt, "LK_NBLCK")  # noqa: B009
                    locking(self._fd, lk_nblck, 1)
                except OSError:
                    os.close(self._fd)
                    self._fd = None
                    raise
        else:
            # Unix: use fcntl for file locking
            import fcntl

            # Open or create the lock file
            self._fd = os.open(
                self.lock_path,
                os.O_CREAT | os.O_RDWR,
                0o644,
            )

            try:
                # Try to acquire an exclusive lock (non-blocking)
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(self._fd)
                self._fd = None
                raise

        # Write PID to lock file for debugging
        if self._fd is not None:
            pid_str = f"{os.getpid()}\n"
            os.write(self._fd, pid_str.encode())

    def release(self) -> None:
        """
        Release the lock. This operation is idempotent.

        Safe to call multiple times or even if lock was never acquired.
        """
        if not self._acquired:
            return

        # Unregister from active locks
        FileLock._active_locks.discard(self)

        if self._fd is not None:
            try:
                import platform

                system = platform.system()

                if system == "Windows":
                    import msvcrt

                    # Unlock on Windows
                    # Use getattr to avoid type checking issues on non-Windows platforms
                    with contextlib.suppress(OSError):
                        locking = getattr(msvcrt, "locking")  # noqa: B009
                        lk_unlck = getattr(msvcrt, "LK_UNLCK")  # noqa: B009
                        locking(self._fd, lk_unlck, 1)
                else:
                    import fcntl

                    # Unlock on Unix
                    with contextlib.suppress(OSError):
                        fcntl.flock(self._fd, fcntl.LOCK_UN)

                os.close(self._fd)
            except OSError:
                pass  # Ignore errors during cleanup

            self._fd = None

        # Try to remove the lock file
        with contextlib.suppress(OSError):
            self.lock_path.unlink(missing_ok=True)

        self._acquired = False

    def _is_stale(self) -> bool:
        """
        Check if the lock file is stale (old and process not running).

        A lock is considered stale if:
        1. The lock file is older than stale_threshold
        2. The PID in the lock file (if any) is not running

        Returns:
            True if lock is stale, False otherwise
        """
        if not self.lock_path.exists():
            return False

        # Check age
        try:
            mtime = self.lock_path.stat().st_mtime
            age = time.time() - mtime
            if age < self.stale_threshold:
                return False
        except OSError:
            return False

        # Check if process is still running
        try:
            pid_str = self.lock_path.read_text().strip()
            if pid_str:
                pid = int(pid_str)
                # Check if process exists using platform-appropriate method
                if self._is_process_running(pid):
                    # Process exists, not stale
                    return False
        except (ValueError, OSError):
            # Can't read PID, assume stale if old enough
            pass

        return True

    def _is_process_running(self, pid: int) -> bool:
        """
        Check if a process with the given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        import platform

        system = platform.system()

        if system == "Windows":
            # On Windows, use tasklist command to check if process exists
            try:
                import subprocess

                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                # If the process exists, its PID will appear in the output
                return str(pid) in result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # If we can't check, assume process exists (safer)
                return True
        else:
            # On Unix, use os.kill with signal 0
            try:
                os.kill(pid, 0)
                # Process exists
                return True
            except ProcessLookupError:
                # Process doesn't exist
                return False
            except PermissionError:
                # Process exists but we can't signal it
                return True

    def _remove_stale_lock(self) -> None:
        """Remove a stale lock file."""
        with contextlib.suppress(OSError):
            self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> FileLock:
        """Context manager entry: acquire the lock."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit: release the lock."""
        self.release()

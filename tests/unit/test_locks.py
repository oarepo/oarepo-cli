# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Tests for file-based locking mechanism."""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time
from typing import TYPE_CHECKING

import pytest

from oarepo_cli.core.errors import LockAcquisitionError
from oarepo_cli.utils.locks import FileLock

if TYPE_CHECKING:
    from pathlib import Path


def test_lock_acquisition(tmp_path: Path) -> None:
    """Test that a lock can be acquired."""
    lock_file = tmp_path / "test.lock"
    lock = FileLock(lock_file)

    lock.acquire()
    assert lock._acquired
    assert lock_file.exists()

    lock.release()
    assert not lock._acquired


def test_lock_release(tmp_path: Path) -> None:
    """Test that a lock can be released."""
    lock_file = tmp_path / "test.lock"
    lock = FileLock(lock_file)

    lock.acquire()
    assert lock._acquired

    lock.release()
    assert not lock._acquired
    # Lock file might still exist but should not be locked


def test_idempotent_release(tmp_path: Path) -> None:
    """Test that lock release is idempotent."""
    lock_file = tmp_path / "test.lock"
    lock = FileLock(lock_file)

    lock.acquire()
    lock.release()
    # Should not raise an exception
    lock.release()
    lock.release()


def test_idempotent_acquire(tmp_path: Path) -> None:
    """Test that calling acquire twice doesn't block."""
    lock_file = tmp_path / "test.lock"
    lock = FileLock(lock_file)

    lock.acquire()
    # Should not block
    lock.acquire()
    assert lock._acquired

    lock.release()


def _concurrent_worker(lock_path: str, result_queue: multiprocessing.Queue, delay: float) -> None:
    """Worker function for concurrent lock testing."""
    try:
        lock = FileLock(lock_path, timeout=1.0)
        lock.acquire()
        result_queue.put(("acquired", os.getpid()))
        time.sleep(delay)
        lock.release()
        result_queue.put(("released", os.getpid()))
    except LockAcquisitionError as e:
        result_queue.put(("timeout", os.getpid(), str(e)))
    except Exception as e:
        result_queue.put(("error", os.getpid(), str(e)))


def test_concurrent_acquisition_fails(tmp_path: Path) -> None:
    """Test that concurrent lock acquisition fails as expected."""
    lock_file = tmp_path / "test.lock"

    # Create a queue for results
    result_queue: multiprocessing.Queue = multiprocessing.Queue()

    # Start first process that will hold the lock for 2 seconds
    proc1 = multiprocessing.Process(
        target=_concurrent_worker,
        args=(str(lock_file), result_queue, 2.0),
    )
    proc1.start()

    # Wait for first process to acquire the lock
    event_type, pid = result_queue.get(timeout=5.0)
    assert event_type == "acquired"

    # Start second process that should timeout after 1 second
    proc2 = multiprocessing.Process(
        target=_concurrent_worker,
        args=(str(lock_file), result_queue, 0.1),
    )
    proc2.start()

    # Second process should timeout
    event_type, pid2, *rest = result_queue.get(timeout=5.0)
    assert event_type == "timeout"

    # First process should eventually release
    event_type, pid1 = result_queue.get(timeout=5.0)
    assert event_type == "released"

    proc1.join(timeout=5.0)
    proc2.join(timeout=5.0)

    assert proc1.exitcode == 0
    assert proc2.exitcode == 0


def test_timeout_raises_lock_acquisition_error(tmp_path: Path) -> None:
    """Test that timeout raises LockAcquisitionError."""
    lock_file = tmp_path / "test.lock"

    # Acquire lock in this process
    lock1 = FileLock(lock_file)
    lock1.acquire()

    # Try to acquire with short timeout in same process
    lock2 = FileLock(lock_file, timeout=0.5)

    start = time.time()
    with pytest.raises(LockAcquisitionError, match="Could not acquire lock"):
        lock2.acquire()
    elapsed = time.time() - start

    # Should have waited approximately timeout duration
    assert 0.4 < elapsed < 1.0

    lock1.release()


def test_stale_lock_recovery(tmp_path: Path) -> None:
    """Test that stale locks are detected and recovered."""
    lock_file = tmp_path / "test.lock"

    # Create a lock file with an old timestamp and non-existent PID
    lock_file.write_text("999999\n")

    # Make it appear old by modifying mtime
    old_time = time.time() - 400.0  # Older than default 300s threshold
    os.utime(lock_file, (old_time, old_time))

    # Should be able to acquire despite existing lock file
    lock = FileLock(lock_file, timeout=2.0)
    lock.acquire()
    assert lock._acquired

    lock.release()


def test_context_manager(tmp_path: Path) -> None:
    """Test that FileLock works as a context manager."""
    lock_file = tmp_path / "test.lock"

    with FileLock(lock_file) as lock:
        assert lock._acquired
        assert lock_file.exists()

    assert not lock._acquired


def test_context_manager_with_exception(tmp_path: Path) -> None:
    """Test that lock is released even when exception occurs."""
    lock_file = tmp_path / "test.lock"

    lock = FileLock(lock_file)
    try:
        with lock:
            assert lock._acquired
            raise ValueError("Test exception")
    except ValueError:
        pass

    assert not lock._acquired


def test_lock_file_parent_directory_created(tmp_path: Path) -> None:
    """Test that parent directory is created if it doesn't exist."""
    lock_file = tmp_path / "subdir" / "another" / "test.lock"

    lock = FileLock(lock_file)
    lock.acquire()

    assert lock_file.parent.exists()
    assert lock_file.exists()

    lock.release()


def test_stale_lock_with_running_process(tmp_path: Path) -> None:
    """Test that a lock is not considered stale if the process is still running."""
    lock_file = tmp_path / "test.lock"

    # First, acquire an actual lock with this process
    lock1 = FileLock(lock_file)
    lock1.acquire()

    # Make the lock file appear old
    old_time = time.time() - 400.0
    os.utime(lock_file, (old_time, old_time))

    # Try to acquire with another lock instance - should timeout
    # because the lock is actually held and the process is still running
    lock2 = FileLock(lock_file, timeout=0.5)

    with pytest.raises(LockAcquisitionError):
        lock2.acquire()

    lock1.release()


def test_stale_lock_threshold_not_exceeded(tmp_path: Path) -> None:
    """Test that recent locks are not considered stale."""
    lock_file = tmp_path / "test.lock"

    # Acquire an actual lock first
    lock1 = FileLock(lock_file)
    lock1.acquire()

    # The lock file now exists and is locked, with a recent timestamp
    # Try to acquire with another instance - should timeout (not stale)
    lock2 = FileLock(lock_file, timeout=0.5)

    with pytest.raises(LockAcquisitionError):
        lock2.acquire()

    lock1.release()


def test_lock_with_no_timeout(tmp_path: Path) -> None:
    """Test that lock can be acquired without timeout (but we won't wait forever in test)."""
    lock_file = tmp_path / "test.lock"

    # First lock with no timeout should acquire immediately
    lock = FileLock(lock_file, timeout=None)
    lock.acquire()
    assert lock._acquired

    lock.release()


def test_lock_writes_pid(tmp_path: Path) -> None:
    """Test that lock file contains the PID of the locking process."""
    lock_file = tmp_path / "test.lock"

    lock = FileLock(lock_file)
    lock.acquire()

    content = lock_file.read_text().strip()
    assert content == str(os.getpid())

    lock.release()


def test_lock_custom_stale_threshold(tmp_path: Path) -> None:
    """Test that custom stale threshold is respected."""
    lock_file = tmp_path / "test.lock"

    # Create a lock file with non-existent PID and acquire the lock
    lock_file.write_text("999999\n")
    # Acquire an actual lock first
    lock0 = FileLock(lock_file)
    lock0.acquire()

    # Make it 100 seconds old
    old_time = time.time() - 100.0
    os.utime(lock_file, (old_time, old_time))

    # With default threshold (300s), lock is held so should timeout
    lock1 = FileLock(lock_file, timeout=0.5)
    with pytest.raises(LockAcquisitionError):
        lock1.acquire()

    # Release the first lock
    lock0.release()

    # Now create a stale lock scenario: lock file exists but no actual lock
    # Re-create the file with non-existent PID
    lock_file.write_text("999999\n")
    old_time = time.time() - 100.0
    os.utime(lock_file, (old_time, old_time))

    # With custom threshold (50s), should be stale and recoverable
    lock2 = FileLock(lock_file, timeout=2.0, stale_threshold=50.0)
    lock2.acquire()
    assert lock2._acquired

    lock2.release()


def _signal_test_worker(
    lock_path: str, result_queue: multiprocessing.Queue, _signal_type: int
) -> None:
    """Worker function that acquires a lock and waits for a signal."""
    try:
        lock = FileLock(lock_path)
        lock.acquire()
        result_queue.put(("acquired", os.getpid()))

        # Wait for signal (sleep for a long time)
        time.sleep(60)

        # This should not be reached if signal is sent
        result_queue.put(("completed", os.getpid()))
    except Exception as e:
        result_queue.put(("error", os.getpid(), str(e)))


@pytest.mark.skipif(sys.platform == "win32", reason="Signal handling differs on Windows")
def test_signal_handler_releases_lock_sigterm(tmp_path: Path) -> None:
    """Test that SIGTERM causes lock to be released."""
    lock_file = tmp_path / "test.lock"

    # Create a queue for results
    result_queue: multiprocessing.Queue = multiprocessing.Queue()

    # Start a process that acquires the lock
    proc = multiprocessing.Process(
        target=_signal_test_worker,
        args=(str(lock_file), result_queue, signal.SIGTERM),
    )
    proc.start()

    # Wait for the process to acquire the lock
    event_type, pid = result_queue.get(timeout=5.0)
    assert event_type == "acquired"

    # Verify lock file exists
    assert lock_file.exists()

    # Send SIGTERM to the process
    proc.terminate()
    proc.join(timeout=5.0)

    # After the process terminates, we should be able to acquire the lock
    # (the signal handler should have released it)
    time.sleep(0.5)  # Give a moment for cleanup

    lock2 = FileLock(lock_file, timeout=2.0)
    lock2.acquire()
    assert lock2._acquired

    lock2.release()


@pytest.mark.skipif(sys.platform == "win32", reason="Signal handling differs on Windows")
def test_signal_handler_releases_lock_sigint(tmp_path: Path) -> None:
    """Test that SIGINT causes lock to be released."""
    lock_file = tmp_path / "test.lock"

    # Create a queue for results
    result_queue: multiprocessing.Queue = multiprocessing.Queue()

    # Start a process that acquires the lock
    proc = multiprocessing.Process(
        target=_signal_test_worker,
        args=(str(lock_file), result_queue, signal.SIGINT),
    )
    proc.start()

    # Wait for the process to acquire the lock
    event_type, pid = result_queue.get(timeout=5.0)
    assert event_type == "acquired"

    # Verify lock file exists
    assert lock_file.exists()

    # Send SIGINT to the process
    assert proc.pid is not None
    os.kill(proc.pid, signal.SIGINT)
    proc.join(timeout=5.0)

    # After the process terminates, we should be able to acquire the lock
    time.sleep(0.5)  # Give a moment for cleanup

    lock2 = FileLock(lock_file, timeout=2.0)
    lock2.acquire()
    assert lock2._acquired

    lock2.release()


def test_active_locks_registration(tmp_path: Path) -> None:
    """Test that locks are registered and unregistered from active locks set."""
    lock_file1 = tmp_path / "test1.lock"
    lock_file2 = tmp_path / "test2.lock"

    lock1 = FileLock(lock_file1)
    lock2 = FileLock(lock_file2)

    # Before acquiring, locks should not be in active set
    initial_count = len(FileLock._active_locks)

    lock1.acquire()
    assert len(FileLock._active_locks) == initial_count + 1
    assert lock1 in FileLock._active_locks

    lock2.acquire()
    assert len(FileLock._active_locks) == initial_count + 2
    assert lock2 in FileLock._active_locks

    lock1.release()
    assert len(FileLock._active_locks) == initial_count + 1
    assert lock1 not in FileLock._active_locks

    lock2.release()
    assert len(FileLock._active_locks) == initial_count
    assert lock2 not in FileLock._active_locks


def test_is_process_running_nonexistent(tmp_path: Path) -> None:
    """Test _is_process_running with a non-existent PID."""
    lock = FileLock(tmp_path / "test.lock")

    # Use a very high PID that almost certainly doesn't exist
    nonexistent_pid = 999999
    assert not lock._is_process_running(nonexistent_pid)


def test_is_process_running_current(tmp_path: Path) -> None:
    """Test _is_process_running with the current process PID."""
    lock = FileLock(tmp_path / "test.lock")

    # Current process should be running
    current_pid = os.getpid()
    assert lock._is_process_running(current_pid)


def test_multiple_locks_context_managers(tmp_path: Path) -> None:
    """Test that multiple locks can be held using context managers."""
    lock_file1 = tmp_path / "test1.lock"
    lock_file2 = tmp_path / "test2.lock"

    with FileLock(lock_file1) as lock1:
        assert lock1._acquired
        with FileLock(lock_file2) as lock2:
            assert lock2._acquired
            # Both locks should be active
            assert lock1 in FileLock._active_locks
            assert lock2 in FileLock._active_locks

        # lock2 should be released
        assert not lock2._acquired
        assert lock2 not in FileLock._active_locks

    # Both locks should be released
    assert not lock1._acquired
    assert lock1 not in FileLock._active_locks

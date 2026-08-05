# Lock Race Condition Fixes

## Summary

This PR addresses the potential race conditions and signal handling issues identified in `docs/architecture/review.md` section 3.2.

## Changes Made

### 1. Signal Handler Installation (Primary Fix)
- Added `SIGTERM` and `SIGINT` signal handlers to ensure locks are released when processes are killed
- Signal handlers iterate through all active locks and release them before re-raising the signal
- Added `atexit` handler as a fallback for normal program exits
- Signal handlers are installed once per process (class-level flag prevents duplicate registration)

### 2. Active Locks Registry
- Introduced class-level `_active_locks` set to track all currently held locks
- Locks are added to the registry on acquisition and removed on release
- This allows the signal handler to clean up all locks when the process is terminated

### 3. Cross-Platform Process Checking
- Refactored `_is_stale()` to use a new `_is_process_running()` method
- On Unix: Uses `os.kill(pid, 0)` (existing behavior)
- On Windows: Uses `tasklist` command to check if process exists (fixes Windows incompatibility)
- This ensures stale lock detection works correctly on all platforms

### 4. Comprehensive Test Coverage
Added 6 new tests:
- `test_signal_handler_releases_lock_sigterm`: Verifies SIGTERM releases locks
- `test_signal_handler_releases_lock_sigint`: Verifies SIGINT releases locks
- `test_active_locks_registration`: Tests the active locks registry
- `test_is_process_running_nonexistent`: Tests process checking with non-existent PID
- `test_is_process_running_current`: Tests process checking with current process
- `test_multiple_locks_context_managers`: Tests multiple concurrent locks

## Review Checklist

From `docs/architecture/review.md` section 3.2:

✅ **Lock files include PID and are validated on acquisition**
- Already implemented: PID is written to lock file on line 196-197
- PID is read and validated in `_is_stale()` method

✅ **Stale locks (from dead processes) are automatically cleaned up**
- Already implemented: `_is_stale()` checks both age and process status
- Enhanced with cross-platform `_is_process_running()` method

✅ **Signal handlers ensure locks are released on SIGTERM/SIGINT**
- **NEW**: Signal handlers now installed for SIGTERM and SIGINT
- **NEW**: `atexit` handler added as fallback
- **NEW**: Class-level active locks registry tracks all locks

✅ **Lock acquisition timeout is reasonable and documented**
- Already implemented: Configurable `timeout` parameter
- Default is `None` (wait indefinitely), can be set per lock
- Default `stale_threshold` is 300 seconds (5 minutes)

## Testing

All 21 tests pass, including the 6 new tests that verify signal handling:

```
tests/unit/test_locks.py::test_signal_handler_releases_lock_sigterm PASSED
tests/unit/test_locks.py::test_signal_handler_releases_lock_sigint PASSED
tests/unit/test_locks.py::test_active_locks_registration PASSED
tests/unit/test_locks.py::test_is_process_running_nonexistent PASSED
tests/unit/test_locks.py::test_is_process_running_current PASSED
tests/unit/test_locks.py::test_multiple_locks_context_managers PASSED
```

Code quality checks pass:
- ✅ `make lint` (ruff check)
- ✅ `make format` (ruff format)
- ✅ `make type-check` (ty check)

## Notes

- Signal handler tests are skipped on Windows (`sys.platform == "win32"`) because Windows signal handling differs from Unix
- The implementation ensures backward compatibility - all existing tests continue to pass
- No breaking changes to the public API

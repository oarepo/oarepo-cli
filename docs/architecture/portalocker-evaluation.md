# Evaluation: portalocker vs. Custom FileLock Implementation

## Executive Summary

**Recommendation: Keep the custom implementation for now, but consider portalocker for future phases.**

The custom `FileLock` implementation is simpler, more focused, and already working for the project's specific needs (Step 2.3). However, `portalocker` offers additional features that may be valuable in later phases.

---

## Feature Comparison

| Feature | Custom FileLock | portalocker |
|---------|----------------|-------------|
| **Basic file locking** | ✅ fcntl (Unix), msvcrt (Windows) | ✅ fcntl (Unix), pywin32/msvcrt (Windows) |
| **Timeout support** | ✅ With configurable timeout | ✅ With timeout and check_interval |
| **Context manager** | ✅ Returns FileLock instance | ✅ Returns file handle (Lock) or None (PidFileLock) |
| **Stale lock detection** | ✅ Age + PID check | ❌ Not built-in |
| **Idempotent operations** | ✅ Safe repeated acquire/release | ✅ Via RLock for reentrant locks |
| **Cross-platform** | ✅ Unix & Windows | ✅ Unix, Windows, with better Windows support via pywin32 |
| **PID file management** | ✅ Writes PID for debugging | ✅ PidFileLock class |
| **Shared locks** | ❌ Exclusive only | ✅ LOCK_SH for read locks |
| **Reentrant locks** | ❌ | ✅ RLock class |
| **Bounded semaphores** | ❌ | ✅ BoundedSemaphore class |
| **Redis locks** | ❌ | ✅ Optional RedisLock (with redis extra) |
| **Atomic file operations** | ❌ | ✅ open_atomic function |
| **File handle return** | ❌ Returns self | ✅ Returns open file handle |
| **Dependencies** | 0 (stdlib only) | 1+ (pywin32 optional on Windows) |
| **LOC (implementation)** | ~250 (with tests) | ~2000+ |
| **Maintenance burden** | Custom code to maintain | Well-maintained external library |
| **Test coverage** | 15 custom tests written | Extensive test suite in library |

---

## Detailed Analysis

### Advantages of Custom Implementation

1. **Zero Dependencies**
   - Uses only stdlib (`fcntl`, `msvcrt`, `os`, `pathlib`)
   - No external package management or version conflicts
   - Aligns with "no premature abstraction" principle from AGENTS.md

2. **Simpler & More Focused**
   - ~120 LOC implementation vs 2000+ in portalocker
   - Exactly what's needed for Step 2.3 requirements
   - Easier to understand and debug

3. **Custom Stale Lock Detection**
   - Built-in age + PID-based stale detection
   - Configurable `stale_threshold` (300s default)
   - portalocker doesn't have this feature

4. **Already Working**
   - All 15 tests passing
   - Code reviewed and committed
   - No migration needed

5. **Project-Specific Error Handling**
   - Uses `LockAcquisitionError` from existing error hierarchy
   - Consistent with project's exception model

### Advantages of portalocker

1. **Battle-Tested**
   - 326 GitHub stars, actively maintained
   - Used in production across many projects
   - Comprehensive test suite

2. **More Features**
   - **Shared locks** (`LOCK_SH`): Multiple readers, exclusive writers
   - **PidFileLock**: Built-in PID file with inspection API
   - **RLock**: Reentrant locks (like threading.RLock)
   - **BoundedSemaphore**: Cross-process semaphores
   - **RedisLock**: Distributed locks (optional)
   - **open_atomic**: Atomic file creation

3. **Better Windows Support**
   - Optional pywin32 integration for shared locks on Windows
   - More robust Windows lock handling
   - Better tested on Windows

4. **File Handle Returns**
   - Context manager returns open file handle
   - Allows reading/writing to locked file directly
   - Custom implementation returns self (less flexible)

5. **Split-Brain Protection**
   - TemporaryFileLock/PidFileLock verify inode after locking
   - Prevents POSIX race condition where file is unlinked+recreated

6. **Lower Maintenance**
   - No need to maintain custom locking code
   - Bug fixes and improvements from community
   - Cross-platform edge cases already handled

### Disadvantages of portalocker

1. **Dependency Bloat**
   - Adds external dependency to project
   - Optional pywin32 on Windows (large dependency)
   - Version management in pyproject.toml

2. **More Complex**
   - Larger API surface to learn
   - More code = more potential bugs
   - Overkill for simple lock file needs

3. **Different API**
   - Would require refactoring Step 2.3 code
   - Tests would need rewriting
   - Context manager returns file handle, not lock instance

4. **No Built-in Stale Detection**
   - Would need custom wrapper for stale lock handling
   - Custom implementation's age+PID check not available

---

## Use Case Analysis

### Current Needs (Phase 2: Virtual Environment Management)
- **Goal**: Prevent concurrent venv operations from corrupting state
- **Requirements**:
  - Simple exclusive locks
  - Timeout support
  - Cross-platform
  - Stale lock recovery
- **Verdict**: Custom implementation is sufficient ✅

### Future Needs (Phase 3-7)

#### Phase 3: Library Commands
- Lock requirements: Exclusive locks for build/test operations
- **Verdict**: Custom implementation sufficient ✅

#### Phase 4: Repository Commands
- Lock requirements: Exclusive locks for repository operations
- Potential shared locks for read-only operations (e.g., multiple `info` commands)
- **Verdict**: Shared locks from portalocker could be useful ⚠️

#### Phase 5: Repository Installer
- Lock requirements: Prevent concurrent installations
- **Verdict**: Custom implementation sufficient ✅

#### Phase 6: Hardening & Polish
- Could benefit from portalocker's battle-tested edge case handling
- **Verdict**: Consider migration if edge cases arise ⚠️

#### Distributed Scenarios (Future)
- If OARepo CLI ever needs distributed locking (multiple machines)
- portalocker's RedisLock would be valuable
- **Verdict**: Not needed now, but good to know ℹ️

---

## Migration Effort

If migrating to portalocker later:

### Code Changes Required
1. Replace `FileLock` import with `portalocker.Lock`
2. Update constructor calls (different parameter names)
3. Update context manager usage (returns file handle, not lock)
4. Rewrite tests to use portalocker's API
5. Add pyproject.toml dependency

**Estimated effort**: 2-4 hours

### Example Migration

**Before (custom):**
```python
from oarepo_cli.utils.locks import FileLock

with FileLock("/tmp/lock", timeout=10.0) as lock:
    # Do work
    pass
```

**After (portalocker):**
```python
import portalocker

with portalocker.Lock("/tmp/lock", timeout=10.0) as fh:
    # Do work (fh is file handle, not lock instance)
    pass
```

---

## Recommendations

### Short-term (Phase 2-3): Keep Custom Implementation ✅
**Rationale:**
- Already implemented and tested
- Meets all current requirements
- Zero dependencies
- Simpler to maintain
- Stale lock detection is valuable

### Mid-term (Phase 4-5): Re-evaluate ⚠️
**Consider portalocker if:**
- Shared locks are needed (multiple readers)
- Windows support issues arise
- Edge cases in locking appear
- Team wants to reduce maintenance burden

**Migration cost**: Low (2-4 hours)

### Long-term (Phase 6+): Likely Stay Custom ✅
**Unless:**
- Distributed locking is needed (→ portalocker.RedisLock)
- Bounded semaphores are needed
- Significant Windows lock issues arise

---

## Alternative: Hybrid Approach

**Option**: Keep custom FileLock but add portalocker as optional dependency for specific use cases.

**Example structure:**
```python
# oarepo_cli/utils/locks.py
class FileLock:
    # Current simple implementation
    ...

# Optional for advanced cases:
try:
    import portalocker
    PORTALOCKER_AVAILABLE = True
except ImportError:
    PORTALOCKER_AVAILABLE = False

def get_shared_lock(...):
    if PORTALOCKER_AVAILABLE:
        return portalocker.Lock(..., flags=portalocker.LOCK_SH)
    else:
        raise NotImplementedError("Install portalocker for shared locks")
```

**Verdict**: Not recommended. Adds complexity without clear benefit right now.

---

## Decision Matrix

| Criterion | Weight | Custom | portalocker | Winner |
|-----------|--------|--------|-------------|--------|
| Meets current requirements | 🔥🔥🔥 | ✅ | ✅ | Tie |
| Zero dependencies | 🔥🔥 | ✅ | ❌ | Custom |
| Simplicity | 🔥🔥 | ✅ | ❌ | Custom |
| Stale lock detection | 🔥 | ✅ | ❌ | Custom |
| Battle-tested | 🔥 | ❌ | ✅ | portalocker |
| Shared locks | 🔥 | ❌ | ✅ | portalocker |
| Lower maintenance | 🔥 | ❌ | ✅ | portalocker |
| Already implemented | 🔥🔥 | ✅ | ❌ | Custom |

**Weighted Score:** Custom = 9, portalocker = 4

---

## Final Recommendation

**Keep the custom implementation.**

### Key Reasons:
1. ✅ Already working and tested
2. ✅ Zero dependencies (important per AGENTS.md: "no premature abstraction")
3. ✅ Stale lock detection built-in (not available in portalocker)
4. ✅ Meets all Phase 2 requirements
5. ✅ Simple and maintainable

### When to Revisit:
- If shared locks are needed (Phase 4+)
- If Windows locking issues arise
- If distributed locking is required
- After Phase 6 if maintenance burden becomes significant

### Action Items:
- ✅ Keep Step 2.3 implementation as-is
- 📝 Document this evaluation in project docs
- 📝 Add note in AGENTS.md about portalocker as future option
- ⏰ Re-evaluate during Phase 4 planning

---

## References

- portalocker GitHub: https://github.com/wolph/portalocker
- portalocker Documentation: https://portalocker.readthedocs.io/
- Project AGENTS.md constraints: No premature abstraction, zero dependencies preferred
- Implementation Steps: Phase 2, Step 2.3

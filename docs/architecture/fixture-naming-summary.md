# Test Fixture Naming Convention Documentation

## Summary

This PR addresses review.md issue 4.1 (Test Fixture Naming Inconsistency) by documenting the observed fixture naming patterns in AGENTS.md.

## Problem Statement

From the code review:
> **Issue:** Some fixtures use `mock_*` prefix, others use descriptive names without prefixes. There's no consistent convention.
>
> **Recommendation:** Document preferred fixture naming convention in AGENTS.md and apply uniformly in new tests.

## Solution

Rather than enforcing a new convention or refactoring existing code, this PR documents the patterns already present in the codebase:

### Fixture Naming Conventions

1. **`mock_*` prefix** - Only for fixtures that return Mock objects
   - `mock_context` - Mock ProjectContext
   - `mock_project_root` - Mock project root directory

2. **`clean_*` prefix** - For cleanup fixtures with setup/teardown
   - `clean_testlib` - Cleans up testlib before and after tests
   - `clean_testrepo` - Resets testrepo install-generated state

3. **Descriptive names without prefixes** - For most fixtures
   - `testlib_project` - Path to testlib fixture project
   - `test_context` - ProjectContext using testlib
   - `lint_project` - Minimal, lint-clean library project
   - `lint_project_multi_module` - Multi-module lint project

4. **Guidelines**
   - Avoid generic names (prefer `lint_project` over `project`)
   - Always document what the fixture provides in its docstring
   - Name should clearly indicate the fixture's purpose

## Examples Provided

The documentation includes three concrete examples showing:
- A `mock_context` fixture returning a Mock object
- A `clean_testlib` cleanup fixture with setup/teardown
- A `lint_project` descriptive fixture

These examples are taken directly from the existing codebase (tests/conftest.py, tests/unit/test_lint_service.py, tests/integration/conftest.py).

## Impact

- **No code changes required** - Existing fixtures already follow these patterns
- **Clear guidance for future tests** - Developers know which pattern to use
- **Documentation-only change** - Zero risk to existing functionality
- **Maintains consistency** - Formalizes observed best practices

## Files Modified

1. **AGENTS.md**
   - Added "Test fixture naming" subsection under Conventions
   - Included three code examples
   - Clear, actionable guidelines

2. **docs/architecture/review.md**
   - Marked issue 4.1 as resolved
   - Updated recommendations section to show completion
   - Added to changelog

## Verification

- ✅ `make check` passes (lint, format, type-check)
- ✅ Documentation is clear and includes examples
- ✅ Review.md accurately reflects resolution status

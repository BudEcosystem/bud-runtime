# Baseline Performance Metrics

**Date**: 2026-01-15
**Branch**: 001-rename-budworkflow-to-budpipeline
**Purpose**: Pre-rename baseline for comparison after implementation

---

## Test Results Baseline

### budworkflow Service Tests
**Command**: `python3 -m pytest -v --tb=short`
**Status**: ❌ COLLECTION ERRORS

**Errors Found**:
1. **TypeError in registry.py**: `unsupported operand type(s) for |: 'types.GenericAlias' and 'builtin_function_or_method'`
   - Location: `budworkflow/handlers/registry.py:167`
   - Cause: Python 3.12 incompatibility with union type syntax
   - Affected files: test_cluster_handlers.py, test_notification_handlers.py, test_registry.py

2. **ModuleNotFoundError**: `No module named 'croniter'`
   - Location: `budworkflow/scheduler/cron_parser.py:10`
   - Affected: test_cron_parser.py

3. **Total Collection Errors**: 5 test files
4. **Time**: 1.24s

**Conclusion**: Test suite has Python 3.12 compatibility issues and missing dependencies.

### budadmin Frontend Tests
**Command**: `npm test`
**Status**: ⚠️ NO TEST SCRIPT

**Note**: No test framework configured for budadmin. See `TESTING.md` for recommendations.

---

## Service Startup Metrics

### budworkflow Service
**Status**: Not measured (service contains import errors)
**Note**: Service would fail to start due to Python 3.12 type union syntax errors

### budadmin Frontend
**Build Status**: ✅ PASSING
**TypeScript**: ✅ PASSING (0 errors)
**Linting**: ✅ PASSING (warnings only)

---

## Performance Metrics

### API Latency
**Status**: ⚠️ NOT MEASURED
**Reason**: Service not running due to import errors
**Target**: < 200ms p95 latency (from spec.md SC-008)

### Memory Usage
**Status**: ⚠️ NOT MEASURED
**Reason**: Service not running
**Target**: < 600MB (from quickstart.md)

### Startup Time
**Status**: ⚠️ NOT MEASURED
**Reason**: Service not running
**Target**: < 2 minutes (from spec.md SC-002)

---

## Code Quality Metrics

### Python (budworkflow)
- **Ruff Linting**: Not run (would show errors from pre-commit)
- **Type Checking (mypy)**: Not configured
- **Test Coverage**: 0% (tests don't run)

### TypeScript (budadmin)
- **Type Checking**: ✅ 100% passing
- **Linting**: ✅ Passing (131 ESLint warnings, 0 errors)
- **Build**: ✅ Successful
- **Test Coverage**: N/A (no tests)

---

## File Count Baseline

### Services
```bash
services/budworkflow/    - 1 service directory
services/budapp/         - Contains budworkflow proxy routes
services/budadmin/       - Contains budworkflow UI pages
```

### Files Affected (from grep analysis)
- **Python files with "budworkflow" imports**: 34 files
- **API proxy files**: 9 files
- **Frontend files**: ~18 files
- **Infrastructure files**: 5 files
- **Total estimated**: 70+ files

---

## Dependencies Status

### Python Dependencies (budworkflow)
**Missing or Incompatible**:
- `croniter` - Missing module
- Python 3.12 type union syntax issues

### Node Dependencies (budadmin)
**Status**: ✅ All installed
**Build**: ✅ Working

### Refactoring Tools
**Status**: ❌ NOT INSTALLED
- `rope` (Python refactoring) - Not installed
- `jscodeshift` (JavaScript/TypeScript refactoring) - Not installed

---

## Environment Information

### System
- **OS**: Linux 6.14.0-1017-azure
- **Python**: 3.12 (compatibility issues detected)
- **Node**: v20.x (from nix environment)
- **Working Directory**: `/home/budadmin/ditto/bud-stack`

### Git
- **Branch**: 001-rename-budworkflow-to-budpipeline
- **Latest Commit**: 7f88b07be (PROJECT MANAGER status report)
- **Uncommitted Changes**: None

---

## Baseline Comparison Criteria (SC-008)

From spec.md Success Criteria SC-008:
> Platform performance metrics (API latency, throughput, execution time) remain within 5% of pre-rename baselines

### Metrics to Track Post-Rename

| Metric | Baseline | Target Post-Rename | Status |
|--------|----------|-------------------|---------|
| API p95 Latency | N/A | N/A ± 5% | ⚠️ Not measured |
| Memory Usage | N/A | N/A ± 5% | ⚠️ Not measured |
| Startup Time | N/A | N/A ± 5% | ⚠️ Not measured |
| Test Pass Rate | 0% (errors) | Should improve | 📊 Baseline: 5 errors |
| Build Success | Frontend ✅ | Must remain ✅ | ✅ Passing |
| TypeScript Errors | 0 | Must remain 0 | ✅ Baseline: 0 |

---

## Recommendations

### Before Starting Rename

1. **Fix Python 3.12 Compatibility**:
   - Update type union syntax in registry.py (line 167)
   - Use `Union[type[BaseHandler], callable]` instead of `type[BaseHandler] | callable`

2. **Install Missing Dependencies**:
   - Install `croniter` package
   - Install `rope` for Python refactoring
   - Install `jscodeshift` for TypeScript refactoring

3. **Establish Runtime Metrics**:
   - Start budworkflow service in development
   - Measure actual API latency, memory, startup time
   - Record baseline before any rename operations

### During Rename

- Compare test results after each phase
- Verify build still passes
- Ensure TypeScript errors remain at 0
- Monitor for new linting errors

### Post-Rename Validation

- Run same baseline tests
- Compare metrics ± 5% tolerance
- Verify all 70+ files updated consistently

---

## Conclusion

**Baseline Status**: ⚠️ PARTIAL

- ✅ Frontend quality metrics established
- ❌ Backend service not running due to Python 3.12 issues
- ❌ Runtime performance metrics not captured
- ✅ File count and scope documented

**Action Required**: Fix Python compatibility issues before proceeding with rename to enable proper baseline measurement.

---

*Baseline captured during Phase 1 (Setup) of rename project*
*Last Updated: 2026-01-15*

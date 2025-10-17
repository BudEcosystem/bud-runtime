# Testing Guidelines for BudPrompt

## Test Naming Convention

All test functions must use descriptive prefixes for CI/CD clarity. This helps immediately identify the nature of failing tests in pipeline reports.

### Required Prefixes:
- **`test_success_`** - Tests that validate successful scenarios with valid inputs
- **`test_failure_`** - Tests that validate proper rejection of invalid inputs

### Examples:
```python
# Success scenarios - expecting valid inputs to pass
def test_success_string_valid_patterns(...)  # Valid pattern matching
def test_success_array_within_bounds(...)    # Array within min/max limits
def test_success_number_boundary_values(...) # Valid boundary values

# Failure scenarios - expecting invalid inputs to be rejected
def test_failure_string_invalid_email_format(...)  # Invalid email rejection
def test_failure_array_below_minimum_items(...)    # Array validation failure
def test_failure_number_invalid_multiple_of(...)   # Invalid multiple rejection
```

## Pytest Markers

### CI/CD Marker
All tests intended for CI/CD pipeline execution must be marked with `@pytest.mark.ci_cd`:

```python
@pytest.mark.ci_cd
def test_success_string_valid_patterns(...):
    """Test that valid patterns are accepted."""
    ...
```

### Available Markers:
- **`ci_cd`** - Tests that run in CI/CD pipeline (GitHub Actions)

To run only CI/CD tests locally:
```bash
# Run all tests with ci_cd marker
docker exec budserve-development-budprompt pytest tests/ -m ci_cd -v

# Run ci_cd tests from a specific file
docker exec budserve-development-budprompt pytest tests/test_structured_output.py -m ci_cd -v
```

## Benefits of This Convention:

1. **CI/CD Pipeline Clarity**: Immediately identify if a failing test is:
   - A success scenario failing (critical - feature broken)
   - A failure scenario failing (validation not working properly)

2. **Better Test Organization**: Tests automatically grouped by type in reports

3. **Easier Debugging**: Clear indication of what validation is affected

4. **Maintainability**: New developers can quickly understand test purpose

## Running Tests

### Unit Tests (Docker Container)
```bash
# Run all unit tests
docker exec budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/ -v"

# Run structured output tests
docker exec budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/test_structured_output.py -v"

# Run specific test with markers
docker exec budserve-development-budprompt bash -c "PYTHONPATH=/app pytest tests/ -m ci_cd -v"
```

### Integration Tests with LLM
```bash
PYTHONPATH=<ABSOLUTE_PATH>bud-runtime/services/budprompt pytest tests/test_integration -m llm -v
```

### Local Development Testing
```bash
# Start development environment
./deploy/start_dev.sh

# Wait for containers to be ready, then run tests
docker exec budserve-development-budprompt pytest tests/ -v
```

### CI/CD Pipeline Testing
```bash
# Run only CI/CD marked tests (as done in GitHub Actions)
docker exec budserve-development-budprompt pytest tests/ -m ci_cd -v

# Run CI/CD tests with coverage
docker exec budserve-development-budprompt pytest tests/ -m ci_cd --cov=budprompt --cov-report=term-missing -v
```

## Test Categories

### String Properties Tests
- Pattern validation (regex patterns)
- Format validation (email, UUID, datetime, IP addresses)
- Optional field handling

### Array Properties Tests
- Size constraints (minItems, maxItems)
- Nested arrays and matrices
- Type validation for array items

### Number Properties Tests
- Range constraints (minimum, maximum)
- Exclusive boundaries
- Multiple constraints (multipleOf)
- Floating point precision edge cases

### Type Support Tests
- Basic types (string, number, boolean, integer)
- Complex types (objects, arrays, enums)
- Union types (anyOf)
- Optional fields

## Writing New Tests

When creating new test functions, always:

1. Use the appropriate prefix (`test_success_` or `test_failure_`)
2. Include descriptive names that explain what's being tested
3. Group related tests together
4. Add comments for complex validation scenarios
5. Ensure proper error assertions for failure tests
6. Apply `@pytest.mark.ci_cd` decorator for tests that should run in CI/CD

Example structure:
```python
@pytest.mark.ci_cd
def test_success_feature_valid_scenario():
    """Test that valid input is accepted."""
    # Arrange
    valid_data = {...}

    # Act
    result = model.validate(valid_data)

    # Assert
    assert result.field == expected_value

@pytest.mark.ci_cd
def test_failure_feature_invalid_scenario():
    """Test that invalid input is properly rejected."""
    # Arrange
    invalid_data = {...}

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        model.validate(invalid_data)
    assert "expected_error" in str(exc_info.value)
```

## Test Coverage

Ensure comprehensive coverage by testing:
- Valid inputs at boundaries
- Invalid inputs just outside boundaries
- Edge cases and special values
- Optional field behavior
- Type coercion scenarios
- Error message content

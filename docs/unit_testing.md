# 🧪 Unit Testing

PyGuard recommends using [pytest](https://docs.pytest.org/en/stable/getting-started.html) for writing and running unit
tests. **pytest** is a robust testing framework that makes
it easy to write simple and scalable test cases. Test-Driven Development (TDD) is preferred as it ensures that tests are
written before the code is implemented, promoting better design and code quality.

### Advantages of Test-Driven Development (TDD)

- **Improved Code Quality**: Writing tests first helps to define the desired behavior of the code, resulting in cleaner
  and more maintainable code.
- **Fewer Bugs**: TDD helps catch bugs early in the development cycle, reducing the likelihood of defects in production.
- **Refactoring Confidence**: With a comprehensive test suite, developers can refactor code with confidence, knowing
  that existing functionality is protected by tests.
- **Better Design**: TDD encourages writing small, modular, and loosely-coupled code, leading to a better overall
  design.

### Guidelines for Writing Test Cases

- **Write Tests First**: Follow TDD by writing your test cases before implementing the actual code.
- **Use Descriptive Names**: Name your test functions and methods clearly to indicate what they are testing.
- **Keep Tests Independent**: Each test should be independent and not rely on the outcome of other tests.
- **Use Assertions**: Use assertions to verify the expected outcomes of your tests. pytest provides a rich set of
  [assertion](https://docs.pytest.org/en/stable/how-to/assert.html#assertraises) functions.
- **Test Edge Cases**: Ensure your tests cover edge cases and potential failure points.
- **Mock External Dependencies**: Use mocking to isolate the code being tested from external dependencies, such as
  databases or APIs.

## Structuring Tests

- **Directory Structure**: Place your tests in a dedicated directory, typically named `tests`, at the root of your
  project.
- **File Structure**: Organize your test files to mirror the structure of your application code. This makes it easy to
  find and manage tests.
- **Test Functions**: Write test functions for each function or method in your application. Use descriptive names and
  docstrings to explain what each test does.

**Example Directory Structure**:

```markdown
my_project/
├── my_project/
│ ├── __init__.py
│ ├── module_a.py
│ └── module_b.py
├── tests/
│ ├── __init__.py
│ ├── test_module_a.py
│ └── test_module_b.py

```

### Using Pytest Markers

Markers are used to categorize tests and control their execution. Pytest provides several built-in markers and allows
you to create custom ones.

#### Common Use Cases

- **Skip Tests**: Use `@pytest.mark.skip` to skip a test.
- **Skip Tests Conditionally**: Use `@pytest.mark.skipif(condition, reason="...")` to skip tests based on a condition.
- **Expected Failures**: Use `@pytest.mark.xfail` to mark a test as expected to fail.
- **Custom Markers**: Define your own markers for grouping tests (e.g., `@pytest.mark.slow` for slow tests).

See the [Must Read](#must-read) section for references

## Identifying Slow Tests

You can use the `--durations` flag with pytest to identify slow tests. This is particularly useful for performance
optimization.

```bash
pytest --durations=10
```

This command will list the 10 slowest tests, helping you focus on performance bottlenecks.

### Profiling Slow Tests

Identifying and profiling slow tests can help you optimize the performance of your test suite and your codebase.

- **Identify Slow Tests**: Use `pytest --durations=10` to identify the slowest tests.
- **Analyze Performance**: Use profiling tools like `cProfile` or `line_profiler` to analyze the performance of the
  identified slow tests.

## 🪩 Worth a Read

- [Understanding Test Driven Development (TDD)](https://www.browserstack.com/guide/what-is-test-driven-development)
- [Python Unit Testing Best Practices For Building Reliable Applications](https://pytest-with-eric.com/introduction/python-unit-testing-best-practices/)
- [Pytest Markers And Good Test Management](https://pytest-with-eric.com/pytest-best-practices/pytest-markers/)
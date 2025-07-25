# 🕵️ Hooks & Workflows

## Table of Contents

---

- [Installation / Setup](#-installation--setup)
- [Pre-Commit Stage Hooks](#-pre-commit-stage-hooks)
    - [Linting](#-linting)
    - [Formatting](#-formatting)
    - [Type Checking](#-type-checking)
- [Pre-Commit Message Stage Hooks]()
- [Worth a Read](#-worth-a-read)

## ⚒️ Installation / Setup

### 🔐 Pre-Commit Hooks

Pre-commit hooks help ensure code quality and adherence to standards by automatically running checks at various stages
in the development workflow. Here’s how to set up and utilize pre-commit hooks in your project:

**Dependencies**

- [NodeJs](https://nodejs.org/en/download/package-manager) >= v20.16.0
- [Python](https://www.python.org/downloads/) >= v3.8

**Install Pre-Commit Hooks**

To install the pre-commit hooks specified in your `.pre-commit-config.yaml` file, run the following command:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

This command sets up the hooks defined in your configuration file to run automatically.

**Test Pre-Commit Hooks**

To test the pre-commit hooks before making a commit, stage your changes and run:

```bash
pre-commit run --all-files
```

This command will execute all the hooks defined in your configuration file against all files, allowing you to test
and debug issues before committing your changes.

## 🔐 Pre-Commit Stage Hooks

Before each commit, the hooks defined in `.pre-commit-config.yaml` with `commit` stage are executed.
This stage allows you to catch and fix issues before the code is committed to the repository.

### 🧹 Linting

Ensuring your code is clean and adheres to established coding standards is crucial for maintaining a high-quality
codebase. This hook runs ruff to perform linting checks on your code. It helps identify syntax errors,
stylistic issues, and potential bugs. Running this hook ensures that your code adheres to the defined linting
rules.

[Ruff](https://docs.astral.sh/ruff/rules/) integrates several powerful tools to provide comprehensive linting and we
have handpicked the following essential
ones:

- **Pycodestyle**: Checks for style guide compliance.
- **Pyflakes**: Detects various errors.
- **Flake8-bugbear**: Identifies potential bugs and design problems.
- **Flake8-simplify**: Suggests simpler and more readable code.
- **Isort**: Ensures imports are sorted correctly.
- **Pydocstyle**: Enforces consistent docstring style, using Google docstring format.

Ruff provides a unified interface to these tools, simplifying configuration and execution. This ensures that your
codebase consistently follows best practices and standards.

### 🧼 Formatting

For formatting, we have configured ruff to align
with [Black](https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html)'s style, ensuring
consistent code formatting across the entire codebase. [Ruff](https://docs.astral.sh/ruff/formatter/) handles this
formatting, making sure that your code remains clean and readable.

### 🐞 Type Checking

---

Type annotations in Python help improve code readability and maintainability by explicitly specifying the types of
variables, function parameters, and return values. This hook runs mypy to check for type annotations and ensure type
correctness in your code. Type checking helps catch type-related errors early and improves code quality by enforcing
type consistency.

#### Benefits of Type Annotations

- **Readability**: Type annotations make the code easier to read and understand by providing clear information about the
  expected types of variables and function parameters.
- **Maintainability**: Explicit type definitions help maintain consistency across the codebase, making it easier to
  manage and update the code.
- **Early Error Detection**: Mypy can catch type-related errors during development, reducing the likelihood of runtime
  errors and improving code quality.

## 🔐 Pre-Commit Message Stage Hooks

Before each commit, the hooks defined in `.pre-commit-config.yaml` with `commit-msg` are
executed. This stage allows you to catch and fix issues in the commit message before the changes are committed to the
repository.

### ✅ **Commit Message Linting** (commitlint):

This hook runs commitlint to validate your commit messages against a defined set of rules. Proper commit message
formatting helps maintain a clean and structured project history, making it easier to track changes, understand the
purpose of each commit, and automate tasks like changelog generation.

By using these pre-commit hooks, you can maintain high code quality and consistency throughout your development process.
They help automate code reviews and enforce standards, making your workflow more efficient and reliable.

## 🪩 Worth a Read

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Google Docstrings Guidelines](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Type Annotations in Python](https://docs.python.org/3/library/typing.html)
- [MyPy Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)
# Pre-commit Hooks for Bud-Stack

This repository includes comprehensive pre-commit hooks that ensure code quality across all service types.

## What's Included

The pre-commit configuration includes checks for:

### Multi-language Support
- **Python services**: Ruff formatting and import sorting for `budapp`, `budcluster`, `budsim`, `budmodel`, `budmetrics`, `budnotify`, `ask-bud`, `budeval`
- **Rust service**: Cargo fmt and clippy for `budgateway`
- **TypeScript/JavaScript services**: ESLint for `budadmin` and `budplayground`

### General File Checks
- Large file detection (>1MB)
- Case conflicts
- Executable shebangs
- JSON/YAML/TOML/XML validation
- Merge conflict markers
- Private key detection (with appropriate exclusions)
- End-of-file and trailing whitespace fixes

### Code Quality
- Python formatting with Ruff
- Python import sorting
- Rust formatting with cargo fmt
- Rust linting with cargo clippy (with graceful degradation)
- TypeScript/JavaScript linting with ESLint
- Conventional commit message validation
- Security scanning of Python dependencies

## Installation

Run the installation script from the project root:

```bash
./scripts/install_hooks.sh
```

This will:
- Install pre-commit if not available
- Install commit message hooks for conventional commits
- Install Node.js dependencies for frontend services
- Set up all language-specific hooks

## Usage

### Automatic (Recommended)
Pre-commit hooks run automatically on every commit.

### Manual
Run hooks manually on all files:
```bash
pre-commit run --all-files
```

Run specific hooks:
```bash
pre-commit run ruff --all-files
pre-commit run cargo-fmt
pre-commit run budadmin-lint
```

### Bypass (Emergency Only)
To skip hooks temporarily (not recommended):
```bash
git commit --no-verify
```

## Troubleshooting

### Common Issues

1. **ESLint configuration missing**: The install script creates ESLint configs for frontend services
2. **Cargo dependency issues**: Rust linting has graceful degradation for dependency problems
3. **Private key false positives**: Documentation files with example keys are excluded
4. **YAML template issues**: Helm templates and .minijinja files are excluded from YAML validation

### Service-specific Notes

- **Python services**: Only critical linting rules are enforced (import sorting, basic syntax)
- **Rust service**: Clippy runs with all warnings as errors but fails gracefully
- **Frontend services**: ESLint runs with warnings allowed for better development experience
- **Templates**: Helm charts and template files are excluded from validation

## Configuration Files

- `.pre-commit-config.yaml`: Main configuration
- `services/budadmin/.eslintrc.json`: ESLint config for dashboard
- `services/budplayground/.eslintrc.json`: ESLint config for playground
- `scripts/install_hooks.sh`: Installation script

## Philosophy

The hooks are designed to:
- **Catch critical issues** without being overly strict
- **Auto-fix** safe formatting issues
- **Warn** about code quality issues without blocking commits
- **Gracefully degrade** when tools have dependency issues
- **Respect** existing code style and conventions

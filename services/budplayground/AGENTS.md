# Repository Guidelines

## Project Structure & Module Organization
`services/` hosts all runtime microservices, including FastAPI backends (`budapp`, `budcluster`, `budsim`, `budmodel`, `budmetrics`, `budnotify`, `ask-bud`, `budeval`), the Rust gateway (`budgateway`), and Next.js frontends (`budadmin`, `budplayground`). Shared automation lives in `scripts/`, infrastructure-as-code in `infra/helm` and `infra/tofu`, and reproducible dev shells in `nix/` with `flake.nix`. Keep service-specific tests beneath their `tests/` directory, and update `docs/` whenever runtime contracts or external dependencies shift.

## Build, Test, and Development Commands
Enter the toolchain shell with `nix develop` (or `nix develop .#bud`) before running any builds. Install git hooks once with `./scripts/install_hooks.sh`. Start a Python service via `cd services/budapp && ./deploy/start_dev.sh --build`, which composes Docker and Dapr sidecars; reuse the same pattern for sibling services. For the playground UI, run `cd services/budplayground && npm install && npm run dev` (port 8007). Launch the Rust gateway locally with `cd services/budgateway && cargo run`.

## Coding Style & Naming Conventions
Python code follows four-space indents, 119-character lines, and Ruff’s default lint set; organize modules in snake_case and Pydantic models in PascalCase. TypeScript mirrors Next.js conventions with PascalCase components and colocated styling; lint with `npm run lint` and type-check with `npm run typecheck`. Rust modules stay kebab-case on disk with CamelCase types, and must pass `cargo fmt -- --config-path services/budgateway/clippy.toml` and resolve Clippy warnings. Default to ASCII; add concise comments only for non-obvious logic.

## Testing Guidelines
Each Python service runs `pytest`, with tests named `tests/test_*.py`; consult `services/budapp/TESTING_GUIDELINES.md` for approved mocks and audit scenarios. The gateway uses `cargo test --workspace` for unit and integration coverage under `gateway/tests`. Frontends must pass `npm run lint` and `npm run typecheck`; add Storybook or Playwright coverage when UX changes. Call out data migrations, new env vars, or Dapr/IAM shifts in documentation and review notes.

## Commit & Pull Request Guidelines
Commits follow Conventional Commits (for example, `feat(budadmin): add timeline widget`); squash work-in-progress before review. Pull requests should enumerate scope, link relevant issues, list build/test commands executed, and attach UI screenshots or logs when behavior changes. Highlight any secrets handling, infrastructure updates, or contract changes, and keep Terraform/Helm modules synchronized with runtime adjustments.

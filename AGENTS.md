# Repository Guidelines

## Project Structure & Module Organization
- `services/` houses microservices: FastAPI backends (`budapp`, `budcluster`, `budsim`, `budmodel`, `budmetrics`, `budnotify`, `ask-bud`, `budeval`), the Rust gateway (`budgateway`), and Next.js frontends (`budadmin`, `budplayground`).
- `infra/helm` and `infra/tofu` capture Kubernetes charts and Terraform/OpenTofu modules; update them whenever runtime contracts change.
- `docs/` holds architecture notes; `nix/` plus `flake.nix` define reproducible dev shells; shared automation sits in `scripts/`.

## Build, Test, and Development Commands
- Enter the Nix shell with `nix develop` (or `nix develop .#bud`) to preload Python 3.11, Node 20, Rust, and Dapr tooling.
- Install hooks via `./scripts/install_hooks.sh` after cloning or upgrading toolchains.
- Backend services: `cd services/budapp && ./deploy/start_dev.sh --build` launches FastAPI with Docker Compose and Dapr; other Python services reuse the script.
- Frontend: `cd services/budadmin && npm install && npm run dev` (port 8007). Gateway: `cd services/budgateway && cargo run`.
- Run `pre-commit run --all-files` before opening a PR; CI mirrors these checks.

## Coding Style & Naming Conventions
- Python: Ruff enforces four-space indentation and a 119-character line limit. Keep snake_case modules, PascalCase Pydantic models, and tests under `tests/`.
- TypeScript: follow Next.js defaults, PascalCase React components, and colocated styles. Treat `npm run lint` and `npm run typecheck` as authoritative.
- Rust: format with `cargo fmt -- --config-path services/budgateway/clippy.toml` and resolve Clippy warnings. Use kebab-case module directories and CamelCase types.

## Testing Guidelines
- Run `pytest` inside each Python service; tests live in `tests/test_*.py`. Consult `services/budapp/TESTING_GUIDELINES.md` for approved mocking and audit-trail edge cases.
- Gateway: `cargo test --workspace` exercises the Rust crates; integration fixtures belong in `gateway/tests`.
- Frontend: `npm run lint` and `npm run typecheck` gate merges; add Storybook or Playwright coverage when UI behavior changes.
- Note data migrations or env-var shifts in the PR description and update service docs when stateful dependencies move.

## Commit & Pull Request Guidelines
- Commits follow Conventional Commits (`feat(budadmin): ...`, `fix(budmodel): ...`); squash work-in-progress before review.
- PRs must outline scope, linked issues, migration steps, exposed ports, and UI screenshots when applicable.
- Include a "Testing" block enumerating commands run (e.g., `pytest`, `cargo test`, `npm run lint`) and call out secret, Dapr, or IAM updates explicitly.

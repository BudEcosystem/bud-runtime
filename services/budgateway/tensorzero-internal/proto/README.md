# Bud Sentinel Proto

This directory vendors the Bud Sentinel gRPC definitions so the gateway can compile client stubs without depending directly on the private repository. The `bud.proto` file tracks the public v2 schema so the Sentinel contract is visible even when upstream is proprietary.

## Source

- Upstream: `bud-sentinel`
- Maintainers should copy updates from that file whenever the Bud Sentinel service evolves.

## Refresh Instructions

1. Update the local Bud Sentinel repository to the desired revision.
2. Copy the upstream v2 schema into this folder (overwriting `bud.proto`).
3. Re-run `cargo build` (or `cargo test`) so `tonic-build` regenerates the client code.
4. Commit the changes along with any generated Rust modules under `src/inference/providers/bud_sentinel/generated/`.

Keep this proto under version control so builds remain hermetic even when the upstream repo is private.

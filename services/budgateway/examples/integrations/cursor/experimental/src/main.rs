//! This file is intended to run as a post-commit hook for the cursorzero application.
//!
//! Steps performed in `main`:
//! 1. Parse command-line arguments (repository path and gateway URL).
//! 2. Discover the Git repository at the given path.
//! 3. Retrieve the latest commit and its parent's timestamp interval.
//! 4. Generate diffs for each file in the commit.
//! 5. For each diff hunk, parse its content into a syntax tree.
//! 6. Compute tree-edit-distance metrics and collect inference data.
//! 7. Send collected inferences to an external service via HTTP gateway.
//!
//! By running automatically after each commit, this hook enables continuous
//! code-change analysis and integration with TensorZero.

use anyhow::Result;
use clap::Parser;
use git2::Repository;
// TODO: This example needs to be updated to work without the removed client SDK
// The following imports were used by the removed functionality:
// use std::collections::HashMap;
// use cursorzero::clickhouse::InferenceInfo;
// use cursorzero::ted::minimum_ted;
// use cursorzero::{
//     clickhouse::get_inferences_in_time_range,
//     cursor::parse_cursor_output,
//     git::{
//         find_paths_in_repo, get_commit_timestamp_and_parent_timestamp, get_diff_by_file,
//         get_last_commit_from_repo,
//     },
//     parsing::parse_hunk,
// };
// use serde_json::json;
// use tensorzero::{ClientBuilder, ClientBuilderMode, FeedbackParams};
// use tensorzero_internal::clickhouse::ClickHouseConnectionInfo;
// use tensorzero_internal::inference::types::ContentBlockChatOutput;
// use tree_sitter::Tree;
// use uuid::Uuid;
use tracing_subscriber::{EnvFilter, FmtSubscriber};
use url::Url;

#[derive(Parser, Debug)]
struct Cli {
    #[clap(short, long, default_value = ".")]
    path: String,
    #[clap(long, default_value = "http://localhost:6900")]
    gateway_url: Url,
}

#[tokio::main]
async fn main() -> Result<()> {
    let subscriber = FmtSubscriber::builder()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .finish();
    #[expect(clippy::expect_used)]
    tracing::subscriber::set_global_default(subscriber)
        .expect("Failed to set global default subscriber");

    let args = Cli::parse();
    let _repo = Repository::discover(args.path)?;
    // TODO: This example needs to be updated to work without the removed client SDK
    // The example would need to:
    // 1. Parse commits and diffs from the repository
    // 2. Create a client to interact with the gateway
    // 3. Query ClickHouse for inference data
    // 4. Process and filter inferences based on the tree-sitter parsing results
    //
    // Original client construction that was removed:
    // let client = ClientBuilder::new(ClientBuilderMode::HTTPGateway {
    //     url: args.gateway_url,
    // })
    // .build()
    // .await?;
    return Err(anyhow::anyhow!(
        "This example needs to be updated to work without the removed client SDK"
    ));
    // The rest of the code has been removed since it's unreachable after the return statement above
}

// TODO: The following struct definitions were used by the removed functionality:
// #[derive(Debug)]
// struct TreeInfo {
//     path: PathBuf, // VSCode workspace relative path for inferences, git-relative path for diffs
//     tree: Tree,
//     src: Vec<u8>,
// }
//
// #[derive(Debug)]
// struct NormalizedInferenceTreeInfo {
//     paths: Vec<PathBuf>, // git-relative paths that might be the right path for this inference
//     tree: Tree,
//     src: Vec<u8>,
// }

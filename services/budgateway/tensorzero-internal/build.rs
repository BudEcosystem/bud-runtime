#![expect(clippy::expect_used)]

fn main() {
    built::write_built_file().expect("Failed to acquire build-time information");
    generate_bud_sentinel_proto().expect("Failed to generate Bud Sentinel gRPC client");
}

fn generate_bud_sentinel_proto() -> Result<(), Box<dyn std::error::Error>> {
    let proto_path = std::path::Path::new("proto/bud.proto");
    println!("cargo:rerun-if-changed={}", proto_path.display());

    tonic_build::configure()
        .build_server(false)
        .compile_protos(&[proto_path], &["proto"])?;
    Ok(())
}

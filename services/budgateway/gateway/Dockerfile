# ========== builder ==========

FROM rust:1.88.0 AS builder

WORKDIR /src

RUN apt-get update && apt-get install -y clang libc++-dev libsasl2-dev libssl-dev protobuf-compiler libopenblas-dev && rm -rf /var/lib/apt/lists/*

COPY . .

ARG CARGO_BUILD_FLAGS=""

RUN --mount=type=cache,id=tensorzero-gateway-release,sharing=shared,target=/usr/local/cargo/registry \
    --mount=type=cache,id=tensorzero-gateway-release,sharing=shared,target=/usr/local/cargo/git \
    cargo build --release -p gateway $CARGO_BUILD_FLAGS && \
    cp -r /src/target/release /release

# ========== base ==========

FROM debian:bookworm-slim AS base

RUN apt-get update && apt-get install -y ca-certificates openssl wget libsasl2-2 libssl-dev protobuf-compiler libopenblas-dev && rm -rf /var/lib/apt/lists/*

# ========== gateway ==========

FROM base AS gateway

RUN useradd -m -s /bin/bash gateway

# Copy gateway binary and GeoIP database before switching to gateway user
COPY --from=builder /release/gateway /usr/local/bin/gateway

# Create directory structure and download GeoIP database for location data enrichment
RUN mkdir -p /app/geo && \
    wget -O /app/geo/GeoLite2-City.mmdb https://git.io/GeoLite2-City.mmdb && \
    chmod 644 /app/geo/GeoLite2-City.mmdb

# Set proper ownership for the gateway user
RUN chown -R gateway:gateway /app

USER gateway

WORKDIR /app

EXPOSE 3000

ENTRYPOINT ["gateway"]

CMD ["--warn-default-cmd", "--config-file", "config/tensorzero.toml"]

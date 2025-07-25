# ✨ Bud-Serve-Cluster 
---
This repository is responsible for onboarding, deploying and monitoring clusters.

### 🔧 Features

- Onboarding clusters
- Deploying models
- Monitoring clusters

### 🚀 Getting Started

- Clone the repository
- Generate the private key and public key

    ```bash
    mkdir -p crypto-keys
    # Generate a private RSA key, 4096-bit keys
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out crypto-keys/rsa-private-key.pem
    # Generate a 256-bit key for AES
    openssl rand -out crypto-keys/symmetric-key-256 32
    chmod 644 crypto-keys/rsa-private-key.pem
    chmod 644 crypto-keys/symmetric-key-256
    ```
- Copy the .env.sample file to .env and set the required variables
- Run the application using docker compose

    ```bash
    ./deploy/start-dev.sh --build
    ```


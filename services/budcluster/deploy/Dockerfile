# Use the slim version to reduce the base image size
FROM python:3.11.0-slim


RUN

# Install system dependencies in one layer, clean up afterwards
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ansible \
    ca-certificates \
    gnupg \
    lsb-release \
    && curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update && apt-get install -y terraform \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/ \
    && curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash \
    && helm repo add stable https://charts.helm.sh/stable \
    && helm plugin install https://github.com/databus23/helm-diff \
    && ansible-galaxy collection install community.kubernetes \
    && rm -rf /var/lib/apt/lists/*  # Clean up apt cache to reduce image size


RUN git clone --branch release/v1.1.0 https://github.com/BudEcosystem/llm-benchmark.git /llm-benchmark

WORKDIR /llm-benchmark
RUN pip install --prefer-binary -e .

RUN pip install git+https://github.com/BudEcosystem/bud-microframe.git

# Set up the app and install dependencies with binary wheels
WORKDIR /app
COPY . .

# Install Python dependencies and build in a single step, prefer binary wheels, and clean up pip cache
RUN pip install --upgrade pip \
    && pip install --prefer-binary --no-cache-dir -r ./requirements.txt \
    && python setup.py sdist bdist_wheel \
    && pip install --prefer-binary . \
    && rm -rf /root/.cache/*  # Clean pip cache to reduce size

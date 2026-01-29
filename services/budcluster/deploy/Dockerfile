# Use the slim version to reduce the base image size
FROM python:3.11.0-slim

# Install system dependencies in one layer, clean up afterwards
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    openssh-client \
    && curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update && apt-get install -y terraform \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/ \
    && curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash \
    && helm repo add stable https://charts.helm.sh/stable \
    && helm plugin install https://github.com/databus23/helm-diff \
    && rm -rf /var/lib/apt/lists/*

# Install ansible-core instead of full ansible (saves ~200MB)
# Install community.kubernetes from GitHub to avoid Ansible Galaxy API issues
RUN pip install --no-cache-dir ansible-core==2.15.* ansible-runner \
    && ansible-galaxy collection install git+https://github.com/ansible-collections/kubernetes.core.git,main --force \
    && rm -rf /root/.cache/pip/*

# Install CPU-only PyTorch to save ~8GB (CUDA version is ~10GB, CPU-only is ~2GB)
# RUN pip install --no-cache-dir \
#     torch==2.2.0+cpu torchvision==0.17.0+cpu \
#     -f https://download.pytorch.org/whl/torch_stable.html

# Install llm-benchmark with build dependencies (required for madoka C++ compilation)
# Install build tools, compile llm-benchmark, then remove build tools to keep image slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && pip install --no-cache-dir git+https://github.com/BudEcosystem/llm-benchmark.git \
    && apt-get remove -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install bud-microframe
RUN pip install --no-cache-dir git+https://github.com/BudEcosystem/bud-microframe.git

# Set up the app and install dependencies with binary wheels
WORKDIR /app
COPY . .

# Install Python dependencies and build in a single step, prefer binary wheels, and clean up pip cache
RUN pip install --upgrade pip \
    && pip install --prefer-binary --no-cache-dir -r ./requirements.txt \
    && python setup.py sdist bdist_wheel \
    && pip install --prefer-binary . \
    && rm -rf /root/.cache/*  # Clean pip cache to reduce size

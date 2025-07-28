FROM python:3.11.0

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/stable.txt" && \
    KUBECTL_VERSION=$(cat stable.txt) && \
    curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/ && \
    rm stable.txt

COPY scripts/install_kubeai.sh /app/
RUN chmod +x /app/install_kubeai.sh && /app/install_kubeai.sh

WORKDIR /app
COPY . .
# COPY alembic.ini /app/
# COPY alembic /app/alembic
# COPY requirements.txt /app/

RUN pip install --upgrade pip
RUN pip install -r ./requirements.txt
# RUN pip install .

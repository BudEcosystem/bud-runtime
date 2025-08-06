# Bud Infrastructure

This directory manages the Infrastructure as Code (IaC) for deploying the Bud stack across cloud, bare metal, and Kubernetes (k8s) clusters. The setup leverages Helm charts for orchestration, Terraform and NixOS for provisioning, and SOPS for secure secrets management. It supports multi-environment deployments with a unified approach, ensuring consistency.

## Architecture Overview

The infrastructure is structured as a layered architecture, with Helm charts defining Kubernetes workloads, a NixOS-based Kubernetes cluster, and Azure VMs for hosting, provisioned via Terraform.

```
  ╔════════════════════════════════════════════════════════════════════╗
  ║                                                                    ║
  ║                          Helm Charts                               ║
  ║                                                                    ║
  ║        ┌──────────────────────┬──────────────────────┐             ║
  ║        │                      │                      │             ║
  ║        │      devbox          │        bud           │             ║
  ║        │                      │                      │             ║
  ║        └──────────────────────┴──────────────────────┘             ║
  ║                                                                    ║
  ╚════════════════════════════════════════════════════════════════════╝
                     ↓                  ↓
                     ↓                  ↓
  ╔════════════════════════════════════════════════════════════════════╗
  ║                                                                    ║
  ║                           NixOS Nodes                              ║
  ║                                                                    ║
  ║        ┌──────────────────────────────────────────────────┐        ║
  ║        │                                                  │        ║
  ║        │               Kubernetes Cluster                 │        ║
  ║        │                                                  │        ║
  ║        └──────────────────────────────────────────────────┘        ║
  ║                                                                    ║
  ╚════════════════════════════════════════════════════════════════════╝
                     ↓                  ↓
                     ↓                  ↓
  ╔════════════════════════════════════════════════════════════════════╗
  ║                                                                    ║
  ║                       OpenTofu(Terraform)                          ║
  ║                                                                    ║
  ║    ┌──────────────────────┐    ┌──────────────────────────────┐    ║
  ║    │                      │    │                              │    ║
  ║    │  Compute Allocation  │    │       DNS Zone Updates       │    ║
  ║    │                      │    │                              │    ║
  ║    └──────────────────────┘    └──────────────────────────────┘    ║
  ║            ↑                           ↑                           ║
  ║            │                           │                           ║
  ║            └──────────┬────────────────┘                           ║
  ║                       │                                            ║
  ║                       │                                            ║
  ║          ┌────────────┴────────────┐                               ║
  ║          │                         │                               ║
  ║          │        devbox module    │                               ║
  ║          │                         │                               ║
  ║          └─────────────────────────┘                               ║
  ║                       ↑                                            ║
  ║                       │                                            ║
  ║          ┌────────────┴────────────┐                               ║
  ║          │                         │                               ║
  ║          │       azure module      │                               ║
  ║          │                         │                               ║
  ║          └─────────────────────────┘                               ║
  ║                                                                    ║
  ╚════════════════════════════════════════════════════════════════════╝
```

- **Helm Charts**: Define Kubernetes workloads for `devbox` and `bud`, including dependencies like ClickHouse, Kafka, and Keycloak. Polled every minute for changes.
- **NixOS**: Hosting the k8s cluster and the workloads defined by Helm charts. Polls the repository every hour for configuration updates.
- **OpenTofu**: Hosting NixOS and managing DNS Zone, with automated `terraform apply` via GitHub workflows on `master` branch merges.

## Directory Structure and Components

### [infra/helm](./infra/helm)
Contains Helm charts for deploying Kubernetes workloads. The cd polls this directory every minute for changes, automatically applying updates when new commits are merged to the `master` branch.

- **[infra/helm/bud](./infra/helm/bud)**: Helm chart for the `bud` application stack.
  - **Purpose**: Deploys a suite of microservices and dependencies for the `bud` application.
  - **Contents**:
    - `values.enc.yaml`: Encrypted values file for sensitive configurations, managed with SOPS.
    - `values.yaml`: Default configuration values for the chart.

- **[infra/helm/devbox](./infra/helm/devbox)**: Helm chart for the `devbox` application.
  - **Purpose**: Deploys any additional services not releated to bud, eg: vaultwarden.

### [infra/terraform](./infra/terraform)
Contains Terraform configurations for provisioning Azure infrastructure. Automated `terraform apply` is triggered via a GitHub workflow when changes are merged to the `master` branch.

- **[infra/terraform/azure](./infra/terraform/azure)**: Terraform modules for Azure resources.
  - **Purpose**: Provisions Azure VMs and related infrastructure for the NixOS Kubernetes cluster.
  - **Contents**:
    - `main.tf`, `master.tf`, `worker.tf`: Define Azure resources for master and worker nodes.
    - `provider.tf`: Configures the Azure provider.
    - `vars.tf`: Defines Terraform variables.
    - `output.tf`: Specifies output values (e.g., VM IPs).
    - `secrets.yaml`: Stores sensitive data, encrypted with SOPS.

- **[infra/terraform/devbox](./infra/terraform/devbox)**: Terraform configuration for `devbox`-specific resources.
  - **Purpose**: Provisions additional resources like DNS for `devbox` VMs.
  - **Contents**:
    - `main.tf`, `dns.tf`: Define resources and DNS configurations.
    - `provider.tf`: provider configuration.
    - `output.tf`: Output values for `devbox` resources.
    - `secrets.yaml`: Encrypted secrets for `devbox`.
    - `decrypt-devbox-sops.sh`: Script to decrypt and copy sops age key for NixOS.

### [nix](./nix)
Manages NixOS configurations and images for the Kubernetes cluster. polls this directory every hour for NixOS configuration changes, automatically applying updates when new commits are merged to the `master` branch.

- **[nix/images](./nix/images)**: Nix configurations for building OCI container images.
  - **Purpose**: Defines reproducible container images.

- **[nix/nixos](./nix/nixos)**: NixOS system configurations.
  - **Purpose**: Configures the NixOS operating system for Kubernetes nodes.
  - **Contents**:
    - `common/`: Shared configurations, including [configuration.nix](./nix/nixos/common/configuration.nix) and modules like [users.nix](./nix/nixos/common/modules/users.nix).
    - `devbox/`: `devbox`-specific configurations, including:
      - `configuration.nix`, `hardware-configuration.nix`, `disko.nix`: System and disk configurations.
      - `facter.json`: Metadata for the node.
      - `modules/`: Includes [k3s.nix](./nix/nixos/devbox/modules/k3s.nix) for Kubernetes setup and [cd/](./nix/nixos/devbox/modules/cd) for continuous deployment with Helm ([default.nix](./nix/nixos/devbox/modules/cd/helm/default.nix), [script.sh](./nix/nixos/devbox/modules/cd/helm/script.sh)).
      - `secrets.yaml`: Encrypted secrets for NixOS.

- **[nix/workflows](./nix/workflows)**: Nix-based CI/CD workflows.
  - **Purpose**: Automates infrastructure tasks, including Terraform apply.
  - **Contents**:
    - `default.nix`: Main workflow configuration.
    - `devbox_tofu_apply/`: Workflow for applying Terraform configurations ([script.sh](./nix/workflows/devbox_tofu_apply/script.sh)).
    - `secrets.yaml`: Encrypted secrets for workflows.

- **[nix/shell.nix](./nix/shell.nix)**: Defines a development environment for working with the repository.

## Automated Deployments

Deployments are fully automated when changes are merged into the `master` branch:
- **NixOS Configurations**: The cd polls the [nix/nixos](./nix/nixos) directory every hour for configuration changes.
- **Helm Charts**: The cd polls the [infra/helm](./infra/helm) directory every minute for changes to Helm charts.
- **Terraform**: A GitHub workflow in [nix/workflows/devbox_tofu_apply](./nix/workflows/devbox_tofu_apply) triggers `terraform apply` for changes in [infra/terraform](./infra/terraform) when merged to `master`.

## Secrets Management with SOPS

Secrets are managed using [SOPS](https://github.com/mozilla/sops) to encrypt sensitive data in files like `values.enc.yaml` and `secrets.yaml`.
First you should reach out to someone with existing access to the secrets to add your public key.

- **Encryption**: Files are encrypted using age key.
- **Usage**: Helm and Terraform use decrypted values during automated deployments. Ensure SOPS is configured with the correct key in the CI/CD pipeline.
- **Example**:
  ```bash
  # view/edit secrets
  sops infra/helm/bud/values.enc.yaml
  # decrypt secrets to a file
  sops -d infra/helm/bud/values.enc.yaml > infra/helm/bud/secrets.yaml
  ```

## Common Scenarios

### Adding a New User
1. **Update NixOS Configuration**:
   - Edit [nix/nixos/common/modules/users.nix](./nix/nixos/common/modules/users.nix).
2. **Commit and Merge**:
   - Push changes to a feature branch and create a pull request to merge into `master`.
   - The NixOS cd will poll [nix/nixos](./nix/nixos) within an hour and apply the update automatically.

### Adding a New Microservice
To add a new microservice to the `bud` Helm chart:
1. **Create a New Helm Template**:
   - Add a new YAML file in [infra/helm/bud/templates/microservices](./infra/helm/bud/templates/microservices), e.g., `newmicroservice.yaml`.
   - Example template:
     ```yaml
     apiVersion: apps/v1
     kind: Deployment
     metadata:
       name: {{ include "bud.fullname" . }}-newmicroservice
       labels:
         {{- include "bud.labels" . | nindent 8 }}
     spec:
       replicas: 1
       selector:
         matchLabels:
           app: newmicroservice
       template:
         metadata:
           labels:
             app: newmicroservice
         spec:
           containers:
           - name: newmicroservice
             image: "your-image:tag"
             ports:
             - containerPort: 8080
     ```
2. **Update Values**:
   - Add configuration to [infra/helm/bud/values.yaml](./infra/helm/bud/values.yaml):
     ```yaml
     microservices:
       newmicroservice:
         enabled: true
         image: your-image:tag
     ```
   - If secrets are required, update [infra/helm/bud/values.enc.yaml](./infra/helm/bud/values.enc.yaml) using SOPS.
3. **Commit and Merge**:
   - Push changes to a feature branch and merge into `master` via a pull request.
   - The cluster will poll [infra/helm/bud](./infra/helm/bud) within a minute and apply the Helm chart update automatically.
4. **Update Ingress (if needed)**:
   - Add rules to [infra/helm/bud/templates/ingress.yaml](./infra/helm/bud/templates/ingress.yaml) for external access.

## Contributing
- Ensure all secrets are encrypted with SOPS before committing.
- Follow the directory structure for new components.
- Test changes locally using tools like `kind` for Kubernetes or `terraform plan` for infrastructure.
- Merge changes to `master` for automated deployment.

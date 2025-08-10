import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4

from ..cluster_ops.terrafrom import TerraformClusterManager
from ..cluster_ops.terrafrom_schemas import AWSConfig


class AWSEksManager(TerraformClusterManager):
    """AWSEksManager Class For Managing AWS EKS Clusters."""

    def __init__(self, config: AWSConfig):
        """Initialize AWSEksManager with AWS configuration."""
        super().__init__()
        self.config = config

    def _copy_terraform_files(self) -> None:
        """Create Terraform files for AWS EKS cluster."""
        prefix = f"{hashlib.md5(self.config.cluster_name.encode(), usedforsecurity=False).hexdigest()}"
        self.temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.unique_state_name = f"{prefix}-eks-{uuid4()}"  # TODO: change this to more identifiable one

        # Get the absolute path to the templates directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "aws-eks")

        if not os.path.exists(template_dir):
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # Copy Terraform files from templates
        shutil.copytree(template_dir, self.temp_dir, dirs_exist_ok=True)

        print(f"Terraform files copied to: {self.temp_dir}")

    def _convert_config_to_terraform(self) -> str:
        """Convert the config into terraform.tfvars file."""
        # Convert tags to Terraform format
        tags_dict = self.config.tags.to_dict() if self.config.tags else {}
        tags_str = "{\n" + "\n".join([f'  {key} = "{value}"' for key, value in tags_dict.items()]) + "\n}"

        return f"""
region = "{self.config.region}"
access_key = "{self.config.access_key}"
secret_key = "{self.config.secret_key}"
cluster_name = "{self.config.cluster_name}"
vpc_name = "{self.config.vpc_name}"

tags = {tags_str}
        """

    def get_outputs(self):
        """Get Terraform outputs."""
        try:
            cwd = os.path.join(str(self.temp_dir), "environments", "prod")

            process = subprocess.Popen(
                ["terraform", "output", "-json"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            output = []
            for line in iter(process.stdout.readline, ""):
                output.append(line)

            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                return json.loads("".join(output))
            return None

        except Exception as e:
            print(f"Error getting outputs: {str(e)}")
            return None

    def generate_kubeconfig(self):
        """Generate kubeconfig for kubectl access."""
        try:
            outputs = self.get_outputs()
            if not outputs or "kubeconfig" not in outputs:
                print("Failed to get kubeconfig from Terraform outputs")
                return None

            kubeconfig = json.loads(outputs["kubeconfig"]["value"])
            kubeconfig_path = os.path.join(self.temp_dir, "kubeconfig")

            with open(kubeconfig_path, "w") as f:
                json.dump(kubeconfig, f, indent=2)

            print(f"Kubeconfig written to: {kubeconfig_path}")
            return kubeconfig_path

        except Exception as e:
            print(f"Error generating kubeconfig: {str(e)}")
            return None

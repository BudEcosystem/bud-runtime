import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4

from ..cluster_ops.terrafrom import TerraformClusterManager
from ..cluster_ops.terrafrom_schemas import AzureConfig


class AzureAksManager(TerraformClusterManager):
    """AzureAksManager Class For Managing Azure AKS Clusters."""

    def __init__(self, config: AzureConfig):
        """Initialize AzureAksManager with Azure configuration."""
        super().__init__()
        self.config = config

    def _copy_terraform_files(self) -> None:
        """Create Terraform files for Azure AKS cluster."""
        prefix = f"{hashlib.md5(self.config.cluster_name.encode()).hexdigest()}"
        self.temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.unique_state_name = f"{prefix}-aks-{uuid4()}"  # TODO : change this to more identifiable one

        # Get the absolute path to the templates directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "azure-aks")

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
subscription_id = "{self.config.subscription_id}"
tenant_id = "{self.config.tenant_id}"
client_id = "{self.config.client_id}"
client_secret = "{self.config.client_secret}"
resource_group_name = "{self.config.resource_group_name}"
location = "{self.config.cluster_location}"


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

            # print(process.stdout)

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

import os
import subprocess
import sys
from abc import ABC, abstractmethod


class TerraformClusterManager(ABC):
    """Abstract base class for Terraform-based cluster managers."""

    def __init__(self):
        """Initialize the manager."""
        self.temp_dir = None

    @abstractmethod
    def _copy_terraform_files(self) -> None:
        """Create terraform.tfvars file."""
        pass

    def init(self, state_name: str):
        """Initialize Terraform."""
        try:
            # Prepare Terraform files
            self._copy_terraform_files()
            var_data = self._convert_config_to_terraform()

            # Ensure directories exist
            tfvars_path = os.path.join(str(self.temp_dir), "environments", "prod", "terraform.tfvars")
            os.makedirs(os.path.dirname(tfvars_path), exist_ok=True)

            # Write terraform.tfvars
            with open(tfvars_path, "w") as f:
                f.write(var_data)

            # Terraform backend config parameters
            backend_config = [
                "-backend-config=bucket=terraform-state-bucket",
                f"-backend-config=key={state_name}/terraform.tfstate",
                "-backend-config=region=us-east-1",
                "-backend-config=endpoint=https://bud-store.bud.studio",
                "-backend-config=access_key=shohpaeha1ceekaePhah8taeyohy7U",
                "-backend-config=secret_key=Cahthi1quailaacaeWah8Ea9hae4ofaishoonair8YoDeejahgi8vuth9pi9",
                "-backend-config=skip_credentials_validation=true",
                "-backend-config=skip_requesting_account_id=true",
                "-backend-config=skip_metadata_api_check=true",
                "-backend-config=force_path_style=true",
                "-backend-config=skip_region_validation=true",
            ]

            # Run terraform init with real-time output
            env = os.environ.copy()
            cwd = os.path.join(str(self.temp_dir), "environments", "prod")

            process = subprocess.Popen(
                ["terraform", "init"] + backend_config,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )

            # Stream output in real-time
            output = []
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                sys.stdout.flush()
                output.append(line)

            process.stdout.close()
            return_code = process.wait()

            # Validate the process
            # if return_code != 0:
            #     print(f"Terraform init failed with return code {return_code}")
            #     raise Exception("Terraform init failed")

            # Create a result object similar to subprocess.run for compatibility
            result = type("", (), {})()
            result.returncode = return_code
            result.stdout = "".join(output)

            return result

        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            raise

    @abstractmethod
    def _convert_config_to_terraform(self) -> str:
        """Convert the config into terraform.tfvars file."""
        pass

    def plan(self):
        """Run Terraform plan."""
        if self.temp_dir is None:
            raise ValueError("temp_dir must be set before running plan")

        try:
            cwd = os.path.join(str(self.temp_dir), "environments", "prod")

            process = subprocess.Popen(
                ["terraform", "plan", "-out=tfplan"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output in real-time
            output = []
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                sys.stdout.flush()
                output.append(line)

            process.stdout.close()
            return_code = process.wait()

            # if return_code != 0:
            #     raise subprocess.CalledProcessError(return_code, "terraform plan")

            # Create a result object similar to subprocess.run for compatibility
            result = type("", (), {})()
            result.returncode = return_code
            result.stdout = "".join(output)

            return result

        except subprocess.CalledProcessError as e:
            print(f"Terraform plan failed with return code {e.returncode}")
            raise
        except Exception as e:
            print(f"Error during plan: {str(e)}")
            raise

    def apply(self):
        """Apply Terraform configuration."""
        if self.temp_dir is None:
            raise ValueError("temp_dir must be set before running apply")

        try:
            cwd = os.path.join(str(self.temp_dir), "environments", "prod")

            process = subprocess.Popen(
                ["terraform", "apply", "-auto-approve", "tfplan"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output in real-time
            output = []
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                sys.stdout.flush()
                output.append(line)

            process.stdout.close()
            return_code = process.wait()

            # if return_code != 0:
            #     raise subprocess.CalledProcessError(return_code, "terraform apply")

            # Create a result object similar to subprocess.run for compatibility
            result = type("", (), {})()
            result.returncode = return_code
            result.stdout = "".join(output)

            return result

        except subprocess.CalledProcessError as e:
            print(f"Terraform apply failed with return code {e.returncode}")
            raise
        except Exception as e:
            print(f"Error during apply: {str(e)}")
            raise

    def destroy(self):
        """Destroy resources created by Terraform."""
        try:
            cwd = os.path.join(str(self.temp_dir), "environments", "prod")

            process = subprocess.Popen(
                ["terraform", "destroy", "-auto-approve"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output in real-time
            output = []
            for line in iter(process.stdout.readline, ""):
                print(line, end="")
                sys.stdout.flush()
                output.append(line)

            process.stdout.close()
            return_code = process.wait()

            # Create a result object similar to subprocess.run for compatibility
            result = type("", (), {})()
            result.returncode = return_code
            result.stdout = "".join(output)

            return result

        except Exception as e:
            print(f"Error during destroy: {str(e)}")
            raise

    @abstractmethod
    def get_outputs(self):
        """Get Terraform outputs."""
        pass

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil

            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

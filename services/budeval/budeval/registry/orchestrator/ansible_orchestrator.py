import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import ansible_runner
import yaml

from budeval.commons.logging import logging
from budeval.commons.storage_config import StorageConfig


logger = logging.getLogger(__name__)

# add export ANSIBLE_PYTHON_INTERPRETER=/home/ubuntu/bud-serve-eval/.venv/bin/python to sys.executable


class AnsibleOrchestrator:
    """Central job orchestrator using Ansible playbooks based on runner_type."""

    def __init__(self, playbook_dir: Optional[Path] = None):
        """Initialize the Ansible orchestrator with a playbook directory.

        Args:
            playbook_dir: Optional path to the directory containing Ansible playbooks.
                          If not provided, defaults to the repository's ansible/playbooks directory.

        Raises:
            FileNotFoundError: If the specified playbook directory does not exist.
        """
        repo_root = Path(__file__).resolve().parents[2]
        self._playbook_dir = playbook_dir or repo_root / "ansible" / "playbooks"
        if not self._playbook_dir.exists():
            raise FileNotFoundError(f"Ansible playbook directory not found: {self._playbook_dir}")

    def _parse_kubeconfig(self, kubeconfig: Optional[str], temp_id: str) -> tuple[dict, dict]:
        """Parse kubeconfig and return files and extravars.

        Args:
            kubeconfig: Kubernetes configuration as JSON string or None
            temp_id: Temporary ID for file naming

        Returns:
            Tuple of (files dict, extravars dict)
        """
        files = {}
        extravars = {}

        # For Testing: Load from local yaml file if no kubeconfig provided
        if kubeconfig is None and Path("/mnt/HC_Volume_103274798/bud-runtime/services/budeval/k3s.yaml").exists():
            # Read the local k3s.yaml file
            with open(
                "/mnt/HC_Volume_103274798/bud-runtime/services/budeval/k3s.yaml",
                "r",
            ) as f:
                kubeconfig_yaml_content = f.read()
            # Since it's already YAML, we don't need to parse/convert it
            files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml_content}
            extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
        elif kubeconfig:
            try:
                # 1) Parse the incoming JSON string into a Python dict
                kubeconfig_dict = json.loads(kubeconfig)

                # 2) Dump that dict out as YAML
                kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)

                files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml}
                extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid kubeconfig JSON provided: {e}. Falling back to local k3s.yaml if available.")
                # Fall back to local k3s.yaml if available
                if Path("/mnt/HC_Volume_103274798/bud-runtime/services/budeval/k3s.yaml").exists():
                    with open(
                        "/mnt/HC_Volume_103274798/bud-runtime/services/budeval/k3s.yaml",
                        "r",
                    ) as f:
                        kubeconfig_yaml_content = f.read()
                    files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml_content}
                    extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
                else:
                    # Use in-cluster config as last resort
                    extravars = {"use_in_cluster_config": True}
        else:
            # Try environment-based kubeconfig discovery
            env_kubeconfig = os.environ.get("KUBECONFIG")
            home_kubeconfig = str(Path.home() / ".kube" / "config")

            if env_kubeconfig and Path(env_kubeconfig).exists():
                try:
                    kubeconfig_yaml_content = Path(env_kubeconfig).read_text()
                    files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml_content}
                    extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
                except Exception as e:
                    logger.warning(f"Failed to read KUBECONFIG at {env_kubeconfig}: {e}. Falling back further.")
                    extravars = {"use_in_cluster_config": True}
            elif Path(home_kubeconfig).exists():
                try:
                    kubeconfig_yaml_content = Path(home_kubeconfig).read_text()
                    files = {f"{temp_id}_kubeconfig.yaml": kubeconfig_yaml_content}
                    extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
                except Exception as e:
                    logger.warning(f"Failed to read ~/.kube/config: {e}. Using in-cluster config.")
                    extravars = {"use_in_cluster_config": True}
            else:
                # Use in-cluster config - don't pass kubeconfig_path
                extravars = {"use_in_cluster_config": True}

        return files, extravars

    def verify_cluster_connection(self, kubeconfig: Optional[str] = None) -> bool:
        """Verify cluster connection using an Ansible playbook via a kubeconfig in JSON form."""
        temp_id = f"verify-{uuid.uuid4().hex}"
        playbook = "verify_cluster_k8s.yml"

        files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

        # Ensure namespace is provided to the playbook
        try:
            from budeval.commons.storage_config import StorageConfig

            extravars["namespace"] = StorageConfig.get_current_namespace()
        except Exception:
            # Fallback to 'default' if storage config is unavailable
            extravars.setdefault("namespace", "default")

        try:
            self._run_ansible_playbook(playbook, temp_id, files, extravars)
            logger.info(
                "::: EVAL Ansible ::: Ansible-based cluster verification succeeded for %s",
                temp_id,
            )
            return True
        except Exception as e:
            logger.error(
                "::: EVAL Ansible ::: Ansible-based cluster verification failed: %s",
                e,
                exc_info=True,
            )
            return False

    def run_job(
        self,
        runner_type: str,
        uuid: str,
        kubeconfig: Optional[str],
        engine_args: Dict[str, Any],
        docker_image: str,
        namespace: Optional[str] = None,
        ttl_seconds: int = 600,
    ):
        """Run a job using the specified runner type.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            engine_args: Arguments to pass to the engine.
            docker_image: Docker image to use for the job.
            namespace: Kubernetes namespace to deploy the job in. Defaults to "budeval".
            ttl_seconds: Time-to-live in seconds for the job after completion. Defaults to 600.

        Raises:
            ValueError: If the specified runner_type is not supported.
        """
        playbook_map = {
            "kubernetes": "submit_job_k8s.yml",
        }
        playbook = playbook_map.get(runner_type.lower())
        if not playbook:
            raise ValueError(f"Unsupported runner_type: {runner_type}")

        # Resolve namespace if not provided
        if namespace is None:
            namespace = StorageConfig.get_current_namespace()
            logger.debug(f"Auto-detected namespace: {namespace}")

        job_yaml = self._render_job_yaml(uuid, docker_image, engine_args, namespace, ttl_seconds)

        files = {
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        # Handle kubeconfig
        kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
        files.update(kube_files)
        extravars.update(kube_extravars)

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def run_job_with_volumes(
        self,
        runner_type: str,
        uuid: str,
        kubeconfig: Optional[str],
        engine_args: Dict[str, Any],
        docker_image: str,
        namespace: Optional[str] = None,
        ttl_seconds: int = 600,
        output_volume_size: str = "5Gi",
    ):
        """Run a job with persistent volumes using the specified runner type.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            engine_args: Arguments to pass to the engine.
            docker_image: Docker image to use for the job.
            namespace: Kubernetes namespace to deploy the job in. Defaults to "budeval".
            ttl_seconds: Time-to-live in seconds for the job after completion. Defaults to 600.
            output_volume_size: Size of the output persistent volume. Defaults to "5Gi".

        Raises:
            ValueError: If the specified runner_type is not supported.
        """
        playbook_map = {
            "kubernetes": "submit_job_with_volumes_k8s.yml",
        }
        playbook = playbook_map.get(runner_type.lower())
        if not playbook:
            raise ValueError(f"Unsupported runner_type: {runner_type}")

        # Resolve namespace if not provided
        if namespace is None:
            namespace = StorageConfig.get_current_namespace()
            logger.debug(f"Auto-detected namespace: {namespace}")

        # Generate YAML manifest for Job only (no separate output PVC needed)
        job_yaml = self._render_job_with_volumes_yaml(uuid, docker_image, engine_args, namespace, ttl_seconds)

        files = {
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        # Handle kubeconfig
        kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
        files.update(kube_files)
        extravars.update(kube_extravars)

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def run_job_with_generic_config(
        self,
        runner_type: str,
        uuid: str,
        kubeconfig: Optional[str],
        job_config: Dict[str, Any],
        namespace: Optional[str] = None,
    ):
        """Run a job using generic configuration from transformer.

        Args:
            runner_type: Type of runner to use (e.g., "kubernetes").
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            job_config: Generic job configuration from transformer containing:
                - image: Docker image
                - command: Container command
                - args: Command arguments
                - env_vars: Environment variables
                - config_volume: Configuration volume details
                - data_volumes: Data volume mounts
                - output_volume: Output volume details
                - cpu_request, cpu_limit, memory_request, memory_limit: Resource limits
                - ttl_seconds: TTL after completion
            namespace: Kubernetes namespace to deploy the job in. Defaults to "budeval".

        Raises:
            ValueError: If the specified runner_type is not supported.
        """
        playbook_map = {
            "kubernetes": "submit_job_with_volumes_k8s.yml",
        }
        playbook = playbook_map.get(runner_type.lower())
        if not playbook:
            raise ValueError(f"Unsupported runner_type: {runner_type}")

        # Resolve namespace if not provided
        if namespace is None:
            namespace = StorageConfig.get_current_namespace()
            logger.debug(f"Auto-detected namespace: {namespace}")

        # Generate YAML manifest for Job only (no separate output PVC needed)
        job_yaml = self._render_generic_job_yaml(uuid, job_config, namespace)

        # Enhanced debug logging
        logger.info("=== OpenCompass Job Submission Debug ===")
        logger.info(f"Job UUID: {uuid}")
        logger.info(f"Job config command: {job_config.get('command')}")
        logger.info(f"Job config args: {job_config.get('args')}")
        logger.info(f"Environment variables: {job_config.get('env_vars', {})}")
        logger.info(f"Data volumes: {job_config.get('data_volumes', [])}")
        logger.info(f"Config volume: {job_config.get('config_volume', {})}")
        logger.info("=== Full Job YAML ===")
        logger.info(job_yaml)
        logger.info("=== End Debug ===")

        files = {
            "job.yaml": job_yaml,
        }
        extravars = {
            "job_name": uuid,
            "job_template_path": "job.yaml",
            "namespace": namespace,
        }

        # Handle kubeconfig
        kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
        files.update(kube_files)
        extravars.update(kube_extravars)

        self._run_ansible_playbook(playbook, uuid, files, extravars)

    def cleanup_job_resources(
        self,
        uuid: str,
        kubeconfig: Optional[str],
        namespace: Optional[str] = None,
        eval_request_id: Optional[str] = None,
    ):
        """Clean up job resources including volumes and ConfigMaps.

        Args:
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            namespace: Kubernetes namespace. Defaults to "budeval".
            eval_request_id: Optional evaluation request ID for ConfigMap cleanup.
        """
        playbook = "cleanup_job_resources_k8s.yml"

        # Resolve namespace if not provided
        if namespace is None:
            namespace = StorageConfig.get_current_namespace()
            logger.debug(f"Auto-detected namespace: {namespace}")

        files = {}
        extravars = {
            "job_name": uuid,
            "namespace": namespace,
        }

        # Handle kubeconfig
        kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
        files.update(kube_files)
        extravars.update(kube_extravars)

        try:
            self._run_ansible_playbook(playbook, uuid, files, extravars)
            logger.info(f"Successfully cleaned up resources for job {uuid}")

            # Also cleanup ConfigMap if eval_request_id is provided
            if eval_request_id:
                try:
                    from budeval.evals.configmap_manager import ConfigMapManager

                    configmap_manager = ConfigMapManager(namespace=namespace)
                    configmap_manager.delete_opencompass_config_map(eval_request_id, kubeconfig)
                    logger.info(f"Successfully cleaned up ConfigMap for eval request {eval_request_id}")
                except Exception as configmap_e:
                    logger.warning(f"ConfigMap cleanup failed for {eval_request_id}: {configmap_e}")

        except Exception as e:
            logger.error(
                f"Failed to cleanup resources for job {uuid}: {e}",
                exc_info=True,
            )
            raise e

    def get_job_status(
        self,
        uuid: str,
        kubeconfig: Optional[str],
        namespace: Optional[str] = None,
    ) -> dict:
        """Get job status.

        Args:
            uuid: Unique identifier for the job.
            kubeconfig: Kubernetes configuration as a JSON string (optional, uses in-cluster config if not provided).
            namespace: Kubernetes namespace. Defaults to "budeval".

        Returns:
            Dict containing job status information.
        """
        playbook = "get_job_status_k8s.yml"

        # Resolve namespace if not provided
        if namespace is None:
            namespace = StorageConfig.get_current_namespace()
            logger.debug(f"Auto-detected namespace: {namespace}")

        files = {}
        extravars = {
            "job_name": uuid,
            "namespace": namespace,
        }

        # Handle kubeconfig
        kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
        files.update(kube_files)
        extravars.update(kube_extravars)

        try:
            result = self._run_ansible_playbook_with_output(playbook, uuid, files, extravars)
            logger.info(f"Successfully retrieved status for job {uuid}")

            # Parse the Ansible output to extract job status
            job_status = self._parse_job_status_from_ansible_output(result, uuid)

            logger.warning(f"XXX EVAL XXX : Job {uuid} status: {job_status}")

            return job_status

        except Exception as e:
            logger.error(f"Failed to get status for job {uuid}: {e}", exc_info=True)
            return {
                "status": "error",
                "phase": "failed",
                "message": str(e),
                "active": 0,
                "succeeded": 0,
                "failed": 1,
            }

    def _run_ansible_playbook(
        self,
        playbook: str,
        uuid: str,
        files: Dict[str, str],
        extravars: Dict[str, Any],
    ) -> None:
        playbook_path = self._playbook_dir / playbook
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        pdir = Path(tempfile.mkdtemp(prefix=f"ansible_{uuid}_"))
        logger.debug("Created private data dir: %s", pdir)

        # Write ansible.cfg to enforce interpreter and disable host key checking
        (pdir / "ansible.cfg").write_text(
            f"[defaults]\ninterpreter_python = {sys.executable}\nhost_key_checking = False\n"
        )

        # Create inventory
        (pdir / "inventory").mkdir()
        (pdir / "inventory" / "hosts").write_text(
            "[local]\nlocalhost ansible_connection=local ansible_python_interpreter=" + sys.executable + "\n"
        )

        # Write extra files at the root of private_data_dir
        for rel_path, content in files.items():
            full_path = pdir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Copy playbook into project/
        project_dir = pdir / "project"
        project_dir.mkdir()
        shutil.copy(playbook_path, project_dir / playbook)

        # Override extravars file paths to absolute paths
        if "kubeconfig_path" in extravars:
            extravars["kubeconfig_path"] = str(pdir / extravars["kubeconfig_path"])
        if "job_template_path" in extravars:
            extravars["job_template_path"] = str(pdir / extravars["job_template_path"])
        if "pv_data_template_path" in extravars:
            extravars["pv_data_template_path"] = str(pdir / extravars["pv_data_template_path"])
        if "pvc_data_template_path" in extravars:
            extravars["pvc_data_template_path"] = str(pdir / extravars["pvc_data_template_path"])
        if "pv_output_template_path" in extravars:
            extravars["pv_output_template_path"] = str(pdir / extravars["pv_output_template_path"])
        if "pvc_output_template_path" in extravars:
            extravars["pvc_output_template_path"] = str(pdir / extravars["pvc_output_template_path"])

        # Environment vars for ansible-runner
        venv_bin = os.path.dirname(sys.executable)
        current_path = os.environ.get("PATH", "")
        envvars = {
            "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "PATH": f"{venv_bin}:{current_path}",
        }

        # If kubeconfig file path is present, also export KUBECONFIG for modules honoring env var
        if "kubeconfig_path" in extravars:
            envvars["KUBECONFIG"] = extravars["kubeconfig_path"]

        logger.info(f"Running Ansible playbook: {playbook} with extravars: {extravars}")
        logger.info(f"Using Python interpreter: {sys.executable}")
        logger.info(f"PATH environment: {envvars['PATH']}")

        res = ansible_runner.run(
            private_data_dir=str(pdir),
            playbook=playbook,
            extravars=extravars,
            envvars=envvars,
            verbosity=2,
        )

        if res.rc != 0:
            error_msg = f"Ansible playbook failed: {playbook}, rc={res.rc}"
            if hasattr(res, "stdout") and res.stdout:
                error_msg += f", stdout: {res.stdout.read()}"
            if hasattr(res, "stderr") and res.stderr:
                error_msg += f", stderr: {res.stderr.read()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)

    def _run_ansible_playbook_with_output(
        self,
        playbook: str,
        uuid: str,
        files: Dict[str, str],
        extravars: Dict[str, Any],
    ) -> Any:
        """Run Ansible playbook and return the result object for output parsing."""
        playbook_path = self._playbook_dir / playbook
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        pdir = Path(tempfile.mkdtemp(prefix=f"ansible_{uuid}_"))
        logger.debug("Created private data dir: %s", pdir)

        # Write ansible.cfg to enforce interpreter and disable host key checking
        (pdir / "ansible.cfg").write_text(
            f"[defaults]\ninterpreter_python = {sys.executable}\nhost_key_checking = False\n"
        )

        # Create inventory
        (pdir / "inventory").mkdir()
        (pdir / "inventory" / "hosts").write_text(
            "[local]\nlocalhost ansible_connection=local ansible_python_interpreter=" + sys.executable + "\n"
        )

        # Write extra files at the root of private_data_dir
        for rel_path, content in files.items():
            full_path = pdir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Copy playbook into project/
        project_dir = pdir / "project"
        project_dir.mkdir()
        shutil.copy(playbook_path, project_dir / playbook)

        # Override extravars file paths to absolute paths
        if "kubeconfig_path" in extravars:
            extravars["kubeconfig_path"] = str(pdir / extravars["kubeconfig_path"])
        if "job_template_path" in extravars:
            extravars["job_template_path"] = str(pdir / extravars["job_template_path"])
        if "pv_data_template_path" in extravars:
            extravars["pv_data_template_path"] = str(pdir / extravars["pv_data_template_path"])
        if "pvc_data_template_path" in extravars:
            extravars["pvc_data_template_path"] = str(pdir / extravars["pvc_data_template_path"])
        if "pv_output_template_path" in extravars:
            extravars["pv_output_template_path"] = str(pdir / extravars["pv_output_template_path"])
        if "pvc_output_template_path" in extravars:
            extravars["pvc_output_template_path"] = str(pdir / extravars["pvc_output_template_path"])

        # Environment vars for ansible-runner
        venv_bin = os.path.dirname(sys.executable)
        current_path = os.environ.get("PATH", "")
        envvars = {
            "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
            "ANSIBLE_HOST_KEY_CHECKING": "False",
            "PATH": f"{venv_bin}:{current_path}",
        }

        # If kubeconfig file path is present, also export KUBECONFIG for modules honoring env var
        if "kubeconfig_path" in extravars:
            envvars["KUBECONFIG"] = extravars["kubeconfig_path"]

        logger.info(f"Running Ansible playbook: {playbook} with extravars: {extravars}")
        logger.info(f"Using Python interpreter: {sys.executable}")
        logger.info(f"PATH environment: {envvars['PATH']}")

        res = ansible_runner.run(
            private_data_dir=str(pdir),
            playbook=playbook,
            extravars=extravars,
            envvars=envvars,
            verbosity=2,
        )

        if res.rc != 0:
            error_msg = f"Ansible playbook failed: {playbook}, rc={res.rc}"
            if hasattr(res, "stdout") and res.stdout:
                error_msg += f", stdout: {res.stdout.read()}"
            if hasattr(res, "stderr") and res.stderr:
                error_msg += f", stderr: {res.stderr.read()}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)
        return res

    def _parse_job_status_from_ansible_output(self, ansible_result: Any, job_name: str) -> dict:
        """Parse job status from Ansible playbook output."""
        try:
            # Default status
            status_info = {
                "status": "unknown",
                "phase": "unknown",
                "active": 0,
                "succeeded": 0,
                "failed": 0,
                "pod_count": 0,
                "data_pvc_status": "unknown",
                "output_pvc_status": "unknown",
                "message": "Status retrieved",
                "start_time": None,
                "completion_time": None,
            }

            # Try to extract information from Ansible events
            if hasattr(ansible_result, "events"):
                for event in ansible_result.events:
                    if event.get("event") == "runner_on_ok":
                        event_data = event.get("event_data", {})
                        task_name = event_data.get("task", "")

                        # Look for the set_fact task that contains job status
                        if "Set job status facts" in task_name:
                            res = event_data.get("res", {})
                            ansible_facts = res.get("ansible_facts", {})
                            job_status = ansible_facts.get("job_status", {})

                            logger.info(f"XXX EVAL XXX Job status: {job_status}")

                            if job_status:
                                status_info.update(job_status)

                                # Determine overall status based on job conditions
                                # Safely convert to int, handling both string and int values
                                try:
                                    active = int(job_status.get("active", 0))
                                    succeeded = int(job_status.get("succeeded", 0))
                                    failed = int(job_status.get("failed", 0))
                                except (ValueError, TypeError):
                                    # Fallback to 0 if conversion fails
                                    active = 0
                                    succeeded = 0
                                    failed = 0

                                # Check phase first for NotFound status
                                phase = job_status.get("phase", "")
                                if phase == "NotFound":
                                    status_info["status"] = "failed"
                                    status_info["phase"] = "NotFound"
                                    status_info["message"] = "Job not found in cluster"
                                elif succeeded > 0:
                                    status_info["status"] = "succeeded"
                                elif failed > 0:
                                    status_info["status"] = "failed"
                                elif active > 0:
                                    status_info["status"] = "running"
                                else:
                                    status_info["status"] = "pending"

                                # Extract start and completion times if present under common key variants
                                def _get_time(js: dict, keys: list[str]) -> str | None:
                                    for k in keys:
                                        v = js.get(k)
                                        if v:
                                            return str(v)
                                    return None

                                status_info["start_time"] = _get_time(
                                    job_status, ["start_time", "startTime"]
                                ) or status_info.get("start_time")
                                status_info["completion_time"] = _get_time(
                                    job_status,
                                    ["completion_time", "completionTime"],
                                ) or status_info.get("completion_time")

                                break

            logger.debug(f"Parsed job status for {job_name}: {status_info}")
            return status_info

        except Exception as e:
            logger.error(
                f"Error parsing job status from Ansible output: {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "phase": "unknown",
                "active": 0,
                "succeeded": 0,
                "failed": 0,
                "message": f"Error parsing status: {str(e)}",
            }

    def _render_job_yaml(
        self,
        uuid: str,
        docker_image: str,
        args: Dict[str, Any],
        namespace: str,
        ttl: int,
    ) -> str:
        safe_args = json.dumps(args)
        return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {uuid}
  namespace: {namespace}
spec:
  ttlSecondsAfterFinished: {ttl}
  template:
    spec:
      containers:
        - name: engine
          image: {docker_image}
          env:
            - name: ENGINE_ARGS
              value: '{safe_args}'
      restartPolicy: Never
  backoffLimit: 1
"""

    def _render_persistent_volume_yaml(self, name: str, size: str, volume_type: str) -> str:
        # Note: This creates a PV without hostPath
        # The actual storage backend depends on your cluster configuration
        return f"""apiVersion: v1
kind: PersistentVolume
metadata:
  name: {name}
  labels:
    type: {volume_type}
    app: budeval
spec:
  capacity:
    storage: {size}
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: manual
  # Storage provisioner will handle the actual storage backend
  # No hostPath specified
"""

    def _render_persistent_volume_claim_yaml(self, name: str, _pv_name: str, size: str, namespace: str) -> str:
        # Render a PVC using environment-aware configuration for job-specific volumes
        from budeval.commons.storage_config import StorageConfig

        job_cfg = StorageConfig.get_job_volumes_config()
        access_mode = job_cfg.get("access_mode", "ReadWriteOnce")
        storage_class = job_cfg.get("storage_class", "")

        return f"""apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    app: budeval
spec:
  accessModes:
    - {access_mode}
{f"  storageClassName: {storage_class}" if storage_class else ""}
  resources:
    requests:
      storage: {size}
"""

    def _render_job_with_volumes_yaml(
        self,
        uuid: str,
        docker_image: str,
        args: Dict[str, Any],
        namespace: str,
        ttl: int,
    ) -> str:
        safe_args = json.dumps(args)

        # Get PVC name from configuration
        from budeval.commons.storage_config import StorageConfig

        pvc_name = StorageConfig.get_eval_datasets_pvc_name()

        # Extract eval_request_id for ConfigMap mounting
        eval_request_id = args.get("eval_request_id", uuid)
        configmap_name = f"opencompass-config-{eval_request_id.lower()}"

        # Extract datasets to pass to OpenCompass
        datasets = args.get("datasets", ["mmlu"])
        datasets_arg = " ".join(datasets)

        # Model configuration is now handled via bud-model.py config file

        # Create OpenCompass CLI arguments - use config file mode with bud-model
        opencompass_cmd = f"cd /workspace && python /opt/opencompass/run.py --models bud-model --datasets {datasets_arg} --work-dir /workspace/outputs --max-num-workers 8 --debug"

        # Create bash script that copies config and runs OpenCompass
        bash_script = f"""#!/bin/bash
set -e
echo "Setting up OpenCompass model configuration..."
mkdir -p /workspace/opencompass/configs/models/bud
cp /workspace/configs/bud-model.py /workspace/opencompass/configs/models/bud/bud-model.py
echo "Model configuration copied successfully"
echo "Starting OpenCompass evaluation..."
{opencompass_cmd}
"""

        return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {uuid}
  namespace: {namespace}
spec:
  ttlSecondsAfterFinished: {ttl}
  template:
    spec:
      containers:
        - name: engine
          image: {docker_image}
          command: ["bash"]
          args: ["-c", {json.dumps(bash_script)}]
          env:
            - name: ENGINE_ARGS
              value: '{safe_args}'
            - name: OPENCOMPASS_CONFIG_PATH
              value: '/workspace/configs'
            - name: HF_HOME
              value: '/workspace/cache'
            - name: TRANSFORMERS_CACHE
              value: '/workspace/cache'
            - name: TORCH_HOME
              value: '/workspace/cache'
          volumeMounts:
            - name: eval-datasets
              mountPath: /workspace/data
              subPath: data
              readOnly: true
            - name: eval-datasets-results
              mountPath: /workspace/outputs
              subPath: results/{uuid}
              readOnly: false
            - name: opencompass-config
              mountPath: /workspace/configs
              readOnly: true
            - name: cache-volume
              mountPath: /workspace/cache
          workingDir: /workspace
      volumes:
        - name: eval-datasets
          persistentVolumeClaim:
            claimName: {pvc_name}
            # Note: This PVC must exist in the same namespace as the job
        - name: eval-datasets-results
          persistentVolumeClaim:
            claimName: {pvc_name}
            # Reusing same PVC for results output
        - name: opencompass-config
          configMap:
            name: {configmap_name}
            items:
              - key: "bud-model.py"
                path: "bud-model.py"
              - key: "bud-datasets.py"
                path: "bud-datasets.py"
              - key: "eval_config.py"
                path: "eval_config.py"
              - key: "metadata.json"
                path: "metadata.json"
        - name: cache-volume
          emptyDir: {{}}
      restartPolicy: Never
  backoffLimit: 1
"""

    def run_playbook_json(
        self,
        playbook: str,
        uuid: str,
        extravars: Dict[str, Any],
        kubeconfig: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run an Ansible playbook and return JSON output.

        Args:
            playbook: Name of the playbook to run
            uuid: Unique identifier for this run
            extravars: Extra variables to pass to the playbook
            kubeconfig: Optional kubeconfig content

        Returns:
            Dictionary with the JSON output from the playbook
        """
        import json
        import tempfile

        # Add output file for JSON result
        fd, output_file_name = tempfile.mkstemp(
            suffix=".json",
            prefix=f"ansible_output_{uuid}_",
        )
        os.close(fd)  # Close the file descriptor

        extravars["output_file"] = output_file_name

        # Handle kubeconfig
        files = {}
        if kubeconfig:
            kube_files, kube_extravars = self._parse_kubeconfig(kubeconfig, uuid)
            files.update(kube_files)
            extravars.update(kube_extravars)

        try:
            # Run the playbook
            self._run_ansible_playbook(playbook, uuid, files, extravars)

            # Read the JSON output
            with open(output_file_name, "r") as f:
                result = json.load(f)

            return result

        finally:
            # Clean up temp file
            if os.path.exists(output_file_name):
                os.unlink(output_file_name)

    def get_job_status_simple(
        self,
        job_id: str,
        namespace: str = "budeval",
        kubeconfig: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get job status with simple output."""
        extravars = {
            "job_name": job_id,
            "namespace": namespace,
        }

        try:
            result = self.run_playbook_json("get_job_status_simple.yml", job_id, extravars, kubeconfig)
            return result
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return {"success": False, "job_status": None, "error": str(e)}

    def extract_results_simple(
        self,
        job_id: str,
        namespace: str = "budeval",
        kubeconfig: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract results with simple output."""
        from budeval.commons.storage_config import StorageConfig

        pvc_name = StorageConfig.get_eval_datasets_pvc_name()
        local_extract_path = "/tmp/eval_extractions"

        extravars = {
            "job_id": job_id,
            "namespace": namespace,
            "pvc_name": pvc_name,
            "local_extract_path": local_extract_path,
        }

        try:
            # Check if extraction playbook exists, if not return simple success
            playbook_path = self._playbook_dir / "extract_results_simple.yml"
            if not playbook_path.exists():
                logger.warning(f"Extraction playbook not found at {playbook_path}, returning placeholder result")
                return {
                    "success": True,
                    "job_id": job_id,
                    "extracted_path": f"{local_extract_path}/{job_id}/results",
                    "files_count": 0,
                    "message": "Extraction playbook not implemented yet",
                }

            result = self.run_playbook_json("extract_results_simple.yml", job_id, extravars, kubeconfig)
            return result
        except Exception as e:
            logger.error(f"Failed to extract results for {job_id}: {e}")
            return {
                "success": False,
                "job_id": job_id,
                "extracted_path": None,
                "files_count": 0,
                "error": str(e),
            }

    def _render_generic_job_yaml(self, uuid: str, job_config: Dict[str, Any], namespace: str) -> str:
        """Render a generic job YAML from transformer configuration.

        Args:
            uuid: Job unique identifier
            job_config: Generic job configuration from transformer
            namespace: Kubernetes namespace

        Returns:
            Kubernetes Job YAML as string
        """
        # Extract configuration
        image = job_config.get("image")
        command = job_config.get("command", [])
        args = job_config.get("args", [])
        env_vars = job_config.get("env_vars", {})
        config_volume = job_config.get("config_volume", {})
        data_volumes = job_config.get("data_volumes", [])
        output_volume = job_config.get("output_volume", {})
        ttl = job_config.get("ttl_seconds", 3600)

        # Resources
        cpu_request = job_config.get("cpu_request", "500m")
        cpu_limit = job_config.get("cpu_limit", "2000m")
        memory_request = job_config.get("memory_request", "1Gi")
        memory_limit = job_config.get("memory_limit", "4Gi")

        # Build environment variables section
        env_section = ""
        if env_vars:
            env_list = []
            for key, value in env_vars.items():
                env_list.append(f"""            - name: {key}
              value: '{value}'""")
            env_section = "\n".join(env_list)

        # Build volume mounts section
        volume_mounts = []
        volumes = []

        # Config volume
        if config_volume:
            volume_mounts.append("""            - name: config
              mountPath: /workspace/configs
              readOnly: true""")

            volumes.append(f"""        - name: config
          configMap:
            name: {config_volume["configMapName"]}""")

        # Check if we have the same PVC being mounted multiple times
        pvc_usage = {}
        for _i, vol in enumerate(data_volumes):
            if vol.get("claimName"):
                pvc_name = vol["claimName"]
                if pvc_name not in pvc_usage:
                    pvc_usage[pvc_name] = []
                pvc_usage[pvc_name].append(("data", vol))

        if output_volume and output_volume.get("claimName"):
            pvc_name = output_volume["claimName"]
            if pvc_name not in pvc_usage:
                pvc_usage[pvc_name] = []
            pvc_usage[pvc_name].append(("output", output_volume))

        # If same PVC is used multiple times, consolidate to single mount
        same_pvc_detected = any(len(usages) > 1 for usages in pvc_usage.values())

        if same_pvc_detected:
            logger.info("Detected same PVC being mounted multiple times, using consolidated mount approach")
            # Use single mount point for shared PVC
            for pvc_name, usages in pvc_usage.items():
                if len(usages) > 1:
                    # Use the first volume's mount settings as base
                    first_vol = usages[0][1]
                    volume_mounts.append(f"""            - name: shared-storage
              mountPath: {first_vol.get("mountPath", "/workspace/shared")}
              readOnly: false""")

                    volumes.append(f"""        - name: shared-storage
          persistentVolumeClaim:
            claimName: {pvc_name}""")
                else:
                    # Single usage, handle normally
                    vol_type, vol = usages[0]
                    vol_name = vol.get("name", "data-0" if vol_type == "data" else "output")

                    if vol_type == "data":
                        volume_mounts.append(f"""            - name: {vol_name}
              mountPath: {vol["mountPath"]}
              readOnly: {str(vol.get("readOnly", True)).lower()}""")
                    else:  # output
                        if vol.get("subPath"):
                            volume_mounts.append(f"""            - name: {vol_name}
              mountPath: {vol.get("mountPath", "/workspace/outputs")}
              subPath: {vol["subPath"]}""")
                        else:
                            volume_mounts.append(f"""            - name: {vol_name}
              mountPath: /workspace/outputs""")

                    volumes.append(f"""        - name: {vol_name}
          persistentVolumeClaim:
            claimName: {pvc_name}""")

            # Handle emptyDir volumes
            for vol in data_volumes:
                if vol.get("type") == "emptyDir":
                    vol_name = vol.get("name", "cache")
                    volume_mounts.append(f"""            - name: {vol_name}
              mountPath: {vol["mountPath"]}""")
                    volumes.append(f"""        - name: {vol_name}
          emptyDir: {{}}""")
        else:
            # No same PVC detected, use original logic
            for i, vol in enumerate(data_volumes):
                vol_name = vol.get("name", f"data-{i}")
                volume_mounts.append(f"""            - name: {vol_name}
              mountPath: {vol["mountPath"]}
              readOnly: {str(vol.get("readOnly", True)).lower()}""")

                if vol.get("claimName"):
                    volumes.append(f"""        - name: {vol_name}
          persistentVolumeClaim:
            claimName: {vol["claimName"]}""")
                elif vol.get("type") == "emptyDir":
                    volumes.append(f"""        - name: {vol_name}
          emptyDir: {{}}""")

            # Output volume
            if output_volume:
                if output_volume.get("type") == "shared_pvc" and output_volume.get("subPath"):
                    volume_mounts.append(f"""            - name: output
              mountPath: {output_volume.get("mountPath", "/workspace/outputs")}
              subPath: {output_volume["subPath"]}""")

                    volumes.append(f"""        - name: output
          persistentVolumeClaim:
            claimName: {output_volume["claimName"]}""")
                else:
                    volume_mounts.append("""            - name: output
              mountPath: /workspace/outputs""")

                    volumes.append(f"""        - name: output
          persistentVolumeClaim:
            claimName: {output_volume["claimName"]}""")

        volume_mounts_str = "\n".join(volume_mounts) if volume_mounts else ""
        volumes_str = "\n".join(volumes) if volumes else ""

        # Format command and args
        if isinstance(command, list) and len(command) == 2 and command[0] == "/bin/bash" and command[1] == "-c":
            # Special handling for bash scripts
            command_str = json.dumps(command)
            args_str = json.dumps(args)
        else:
            command_str = json.dumps(command) if command else "[]"
            args_str = json.dumps(args) if args else "[]"

        return f"""apiVersion: batch/v1
kind: Job
metadata:
  name: {uuid}
  namespace: {namespace}
  labels:
    app: budeval
    engine: {job_config.get("engine", "unknown")}
spec:
  ttlSecondsAfterFinished: {ttl}
  template:
    spec:
      containers:
        - name: engine
          image: {image}
          command: {command_str}
          args: {args_str}
{
            f'''          env:
{env_section}'''
            if env_section
            else ""
        }
{
            f'''          volumeMounts:
{volume_mounts_str}'''
            if volume_mounts_str
            else ""
        }
          resources:
            requests:
              cpu: {cpu_request}
              memory: {memory_request}
            limits:
              cpu: {cpu_limit}
              memory: {memory_limit}
          workingDir: /workspace
{
            f'''      volumes:
{volumes_str}'''
            if volumes_str
            else ""
        }
      restartPolicy: Never
  backoffLimit: {job_config.get("backoff_limit", 2)}
"""

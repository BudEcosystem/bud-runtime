"""Simplified Ansible orchestrator for Kubernetes operations."""

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import ansible_runner
import yaml

from budeval.commons.config import app_settings


logger = logging.getLogger(__name__)


class AnsibleOrchestrator:
    """Orchestrates Kubernetes operations using Ansible playbooks."""

    def __init__(self):
        """Initialize the orchestrator."""
        # Use the existing playbooks directory structure
        self.playbook_dir = Path(__file__).parent.parent / "ansible" / "playbooks"
        if not self.playbook_dir.exists():
            raise FileNotFoundError(f"Playbook directory not found: {self.playbook_dir}")

    def verify_cluster(self, namespace: str, kubeconfig: Optional[str] = None) -> bool:
        """Verify Kubernetes cluster connectivity."""
        return self._run_playbook("verify_cluster_k8s.yml", extravars={"namespace": namespace}, kubeconfig=kubeconfig)

    def deploy_job(
        self, job_id: str, job_yaml: str, namespace: str, kubeconfig: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deploy a Kubernetes job."""
        temp_id = f"job-{uuid.uuid4().hex[:8]}"

        success = self._run_playbook(
            "submit_job_with_volumes_k8s.yml",
            extravars={"job_name": job_id, "namespace": namespace, "job_template_path": f"{temp_id}_job.yaml"},
            files={f"{temp_id}_job.yaml": job_yaml},
            kubeconfig=kubeconfig,
        )

        return {"job_id": job_id, "success": success, "namespace": namespace}

    def get_job_status(self, job_id: str, namespace: str, kubeconfig: Optional[str] = None) -> Dict[str, Any]:
        """Get the status of a Kubernetes job."""
        result = self._run_playbook_with_output(
            "get_job_status_k8s.yml", extravars={"job_name": job_id, "namespace": namespace}, kubeconfig=kubeconfig
        )

        # Parse job status from Ansible output
        # Now result is a dict with 'events' key containing parsed event data
        if result and "events" in result:
            for event in result["events"]:
                if event.get("event") == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    if "job_status" in event_data.get("res", {}).get("ansible_facts", {}):
                        job_status = event_data["res"]["ansible_facts"]["job_status"]

                        # Determine status
                        succeeded = int(job_status.get("succeeded", 0))
                        failed = int(job_status.get("failed", 0))
                        active = int(job_status.get("active", 0))

                        if succeeded > 0:
                            status = "completed"
                        elif failed > 0:
                            status = "failed"
                        elif active > 0:
                            status = "running"
                        else:
                            status = "pending"

                        return {"status": status, "details": job_status}

        return {"status": "unknown", "details": {}}

    def cleanup_job(self, job_id: str, namespace: str, kubeconfig: Optional[str] = None) -> bool:
        """Clean up a Kubernetes job and its resources."""
        return self._run_playbook(
            "cleanup_job_resources_k8s.yml",
            extravars={"job_name": job_id, "namespace": namespace},
            kubeconfig=kubeconfig,
        )

    def extract_results(
        self, job_id: str, namespace: str, local_path: str, kubeconfig: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract results from PVC to local filesystem."""
        pvc_name = app_settings.opencompass_dataset_path

        result = self._run_playbook_with_output(
            "extract_results_from_pvc.yml",
            extravars={
                "job_id": job_id,
                "namespace": namespace,
                "pvc_name": pvc_name,
                "results_subpath": f"results/{job_id}",
                "local_extract_path": local_path,
            },
            kubeconfig=kubeconfig,
        )

        # Check if extraction was successful
        if result and result.get("rc") == 0:
            return {"success": True, "local_path": f"{local_path}/{job_id}/outputs"}

        return {"success": False, "error": "Extraction failed"}

    def _run_playbook(
        self,
        playbook: str,
        extravars: Dict[str, Any],
        files: Optional[Dict[str, str]] = None,
        kubeconfig: Optional[str] = None,
    ) -> bool:
        """Run an Ansible playbook and return success status."""
        result = self._run_playbook_with_output(playbook, extravars, files, kubeconfig)
        return result is not None and result.get("rc") == 0

    def _run_playbook_with_output(
        self,
        playbook: str,
        extravars: Dict[str, Any],
        files: Optional[Dict[str, str]] = None,
        kubeconfig: Optional[str] = None,
    ) -> Any:
        """Run an Ansible playbook and return the result object."""
        with tempfile.TemporaryDirectory(prefix="ansible_") as tmpdir:
            private_data_dir = Path(tmpdir)

            # Create required ansible-runner directory structure
            artifacts_dir = private_data_dir / "artifacts"
            artifacts_dir.mkdir(exist_ok=True)

            # Setup kubeconfig if provided
            if kubeconfig:
                try:
                    kubeconfig_dict = json.loads(kubeconfig)
                    kubeconfig_yaml = yaml.safe_dump(kubeconfig_dict)

                    kubeconfig_file = private_data_dir / "kubeconfig.yaml"
                    kubeconfig_file.write_text(kubeconfig_yaml)
                    extravars["kubeconfig_path"] = str(kubeconfig_file)
                except (json.JSONDecodeError, yaml.YAMLError) as e:
                    logger.error(f"Failed to parse kubeconfig: {e}")
                    return None

            # Copy playbook to project directory
            project_dir = private_data_dir / "project"
            project_dir.mkdir()
            playbook_path = self.playbook_dir / playbook
            (project_dir / playbook).write_text(playbook_path.read_text())

            # Write additional files to the project directory where Ansible can find them
            if files:
                for filename, content in files.items():
                    file_path = project_dir / filename
                    file_path.write_text(content)
                    logger.debug(f"Wrote file {filename} to {file_path}")

            # Run playbook
            try:
                logger.info(f"Running playbook {playbook} with extravars: {extravars}")
                logger.debug(f"Private data dir: {private_data_dir}")
                logger.debug(f"Playbook exists: {playbook_path.exists()}")

                result = ansible_runner.run(
                    private_data_dir=str(private_data_dir),
                    playbook=playbook,
                    extravars=extravars,
                    quiet=False,  # Show output for debugging
                    suppress_ansible_output=False,
                    verbosity=2,  # Increase verbosity for debugging
                )

                if result.rc != 0:
                    logger.error(f"Playbook {playbook} failed with rc={result.rc}")
                    # Log more details about the failure
                    if hasattr(result, "stdout"):
                        logger.error(
                            f"Stdout: {result.stdout.read() if hasattr(result.stdout, 'read') else result.stdout}"
                        )
                    if hasattr(result, "stderr"):
                        logger.error(
                            f"Stderr: {result.stderr.read() if hasattr(result.stderr, 'read') else result.stderr}"
                        )
                    if hasattr(result, "events"):
                        for event in result.events:
                            if event.get("event") == "runner_on_failed":
                                logger.error(f"Failed task: {event}")
                else:
                    logger.info(f"Playbook {playbook} completed successfully")

                # IMPORTANT: Parse events while still in the temp directory context
                # Extract the events data before the directory is deleted
                parsed_result = {"rc": result.rc, "status": result.status, "events": []}

                if hasattr(result, "events"):
                    for event in result.events:
                        # Create a copy of the event data
                        parsed_result["events"].append(dict(event))

                return parsed_result

            except Exception as e:
                logger.error(f"Failed to run playbook {playbook}: {e}", exc_info=True)
                return None

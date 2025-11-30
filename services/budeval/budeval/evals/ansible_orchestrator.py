#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------

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

from budeval.commons.config import app_settings
from budeval.commons.logging import logging
from budeval.commons.storage_config import StorageConfig


logger = logging.getLogger(__name__)


class AnsibleOrchestrator:
    """AnsibleOrchestrator class for managing Ansible playbooks and roles."""

    def __init__(self, playbook_dir: Optional[Path] = None):
        """Initialize with playbook directory."""
        repo_root = Path(__file__).resolve().parents[2]
        self._playbook_dir = playbook_dir or repo_root / "budeval" / "ansible" / "playbooks"

        if not self._playbook_dir.exists():
            raise FileNotFoundError(f"Playbook directory not found: {self._playbook_dir}")

    def _parse_kubeconfig(self, kubeconfig: Optional[str], temp_id: str) -> tuple[dict, dict]:
        """Parse kubeconfig and return files and extravars.

        Args:
            kubeconfig: Kubernetes configuration as JSON string or None
            temp_id: Temporary ID for file naming

        Returns:
            Tuple of (files dict, extravars dict)
        """

        def _create_kubeconfig_files(content: str) -> tuple[dict, dict]:
            """Create files and extravars from kubeconfig content."""
            files = {f"{temp_id}_kubeconfig.yaml": content}
            extravars = {"kubeconfig_path": f"{temp_id}_kubeconfig.yaml"}
            return files, extravars

        def _use_in_cluster_config() -> tuple[dict, dict]:
            """Return in-cluster config setup."""
            return {}, {"use_in_cluster_config": True}

        # Try kubeconfig sources in priority order
        kubeconfig_sources = [
            # 1. Provided kubeconfig (JSON)
            lambda: self._try_json_kubeconfig(kubeconfig) if kubeconfig else None,
            # 2. Local k3s.yaml for testing
            lambda: self._try_local_k3s(),
            # 3. Environment KUBECONFIG
            lambda: self._try_env_kubeconfig(),
            # 4. Default ~/.kube/config
            lambda: self._try_home_kubeconfig(),
        ]

        for source in kubeconfig_sources:
            try:
                result = source()
                if result:
                    return _create_kubeconfig_files(result)
            except Exception as e:
                logger.warning(f"Kubeconfig source failed: {e}")
                continue

        # Fallback to in-cluster config
        return _use_in_cluster_config()

    def _try_json_kubeconfig(self, kubeconfig: str) -> Optional[str]:
        """Try to parse JSON kubeconfig and convert to YAML."""
        try:
            kubeconfig_dict = json.loads(kubeconfig)
            return yaml.safe_dump(kubeconfig_dict, sort_keys=False, default_flow_style=False)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid kubeconfig JSON: {e}")
            return None

    def _try_local_k3s(self) -> Optional[str]:
        """Try to read local k3s.yaml file."""
        k3s_path = Path("/mnt/HC_Volume_103274798/bud-runtime/services/budeval/k3s.yaml")
        if k3s_path.exists():
            return k3s_path.read_text()
        return None

    def _try_env_kubeconfig(self) -> Optional[str]:
        """Try to read kubeconfig from KUBECONFIG environment variable."""
        env_kubeconfig = os.environ.get("KUBECONFIG")
        if env_kubeconfig and Path(env_kubeconfig).exists():
            return Path(env_kubeconfig).read_text()
        return None

    def _try_home_kubeconfig(self) -> Optional[str]:
        """Try to read kubeconfig from ~/.kube/config."""
        home_kubeconfig = Path.home() / ".kube" / "config"
        if home_kubeconfig.exists():
            return home_kubeconfig.read_text()
        return None

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

        # Copy playbook dependencies (e.g., included task files)
        # Look for all .yml files in the playbooks directory
        for dep_file in self._playbook_dir.glob("*.yml"):
            if dep_file.name != playbook:  # Don't copy main playbook again
                try:
                    shutil.copy(dep_file, project_dir / dep_file.name)
                    logger.debug(f"Copied playbook dependency: {dep_file.name}")
                except Exception as e:
                    logger.warning(f"Could not copy dependency {dep_file.name}: {e}")

        # Override extravars file paths to absolute paths
        if "kubeconfig_path" in extravars:
            extravars["kubeconfig_path"] = str(pdir / extravars["kubeconfig_path"])
        if "manifest_path" in extravars:
            extravars["manifest_path"] = str(pdir / extravars["manifest_path"])
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
            # Get stdout and stderr content from ansible-runner artifacts
            stdout_file = pdir / "artifacts" / "stdout"
            stderr_file = pdir / "artifacts" / "stderr"

            if stdout_file.exists():
                try:
                    stdout_content = stdout_file.read_text()
                    error_msg += f", stdout: {stdout_content}"
                except Exception as e:
                    logger.warning(f"Could not read stdout file: {e}")

            if stderr_file.exists():
                try:
                    stderr_content = stderr_file.read_text()
                    error_msg += f", stderr: {stderr_content}"
                except Exception as e:
                    logger.warning(f"Could not read stderr file: {e}")

            logger.error(error_msg)
            raise RuntimeError(error_msg)
        logger.info("Playbook %s completed successfully for job %s", playbook, uuid)

    def deploy_evaluation_jobs(self, eval_jobs: str, kubeconfig: Optional[str] = None) -> list:
        """Deploy multiple jobs to the cluster using Ansible playbook."""
        playbook = "apply_manifest.yml"

        jobs = []

        # load eval_jobs into json
        eval_requests = json.loads(eval_jobs)
        for eval_request in eval_requests:
            logger.info(f"Deploying eval job: {eval_request}")

            logger.info(f"RUNS ID {eval_request.get('run_id')}")
            temp_id = eval_request.get("run_id", f"eval-{uuid.uuid4().hex}")

            # JOBS TRACKING
            jobs.append(temp_id)

            files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

            # Build Extra Args
            namespace = StorageConfig.get_current_namespace()
            extravars["namespace"] = namespace
            extravars["job_name"] = temp_id

            bash_script = eval_request.get("script", "")

            # Generate job manifest using proper YAML dictionary to avoid escaping issues
            job_manifest_dict = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"name": temp_id, "namespace": namespace},
                "spec": {
                    "ttlSecondsAfterFinished": 3600,
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "engine",
                                    "image": app_settings.opencompass_docker_image,
                                    "command": ["bash"],
                                    "args": ["-c", bash_script],
                                    "env": [
                                        {"name": "ENGINE_ARGS", "value": ""},
                                        {
                                            "name": "OPENCOMPASS_CONFIG_PATH",
                                            "value": "/workspace/configs",
                                        },
                                        {
                                            "name": "HF_HOME",
                                            "value": "/workspace/cache",
                                        },
                                        {
                                            "name": "TRANSFORMERS_CACHE",
                                            "value": "/workspace/cache",
                                        },
                                        {
                                            "name": "TORCH_HOME",
                                            "value": "/workspace/cache",
                                        },
                                        {
                                            "name": "COMPASS_DATA_CACHE",
                                            "value": "/workspace/shared",
                                        },
                                    ],
                                    "volumeMounts": [
                                        {
                                            "name": "eval-datasets-shared",
                                            "mountPath": "/workspace/shared",
                                        },
                                        {
                                            "name": "cache-volume",
                                            "mountPath": "/workspace/cache",
                                        },
                                    ],
                                    "workingDir": "/workspace",
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "eval-datasets-shared",
                                    "persistentVolumeClaim": {"claimName": "bud-dev-budeval-dataset"},
                                },
                                {"name": "cache-volume", "emptyDir": {}},
                            ],
                            "restartPolicy": "Never",
                        }
                    },
                    "backoffLimit": 1,
                },
            }

            # Convert to YAML string
            job_template = yaml.safe_dump(job_manifest_dict, sort_keys=False, default_flow_style=False)

            logger.info(f"Generated job manifest for {temp_id}")
            logger.debug(f"Job manifest content:\n{job_template}")

            # Add manifest file to files dict
            manifest_filename = f"{temp_id}_job_manifest.yaml"
            files[manifest_filename] = job_template

            # Add manifest path to extravars
            extravars["manifest_path"] = manifest_filename

            # Run Ansible playbook to apply the manifest
            try:
                self._run_ansible_playbook(playbook, temp_id, files, extravars)
                logger.info(f"Successfully deployed eval job: {temp_id}")
            except Exception as e:
                logger.error(f"Failed to deploy eval job {temp_id}: {e}")
                raise

        return jobs

    def extract_job_results(
        self,
        eval_id: str,
        run_ids: list[str],
        kubeconfig: Optional[str] = None,
        job_timing_map: Optional[dict[str, dict]] = None,
    ) -> dict:
        """Extract results from completed evaluation jobs using Kubernetes extraction job.

        This method:
        1. Deploys a Kubernetes Job that mounts the eval-datasets PVC
        2. Runs a Python script to parse OpenCompass CSV results
        3. Retrieves the parsed results via kubectl logs
        4. Merges timing information from job monitoring
        5. Returns structured results with run_id and timing data

        Args:
            eval_id: Evaluation request ID
            run_ids: List of run IDs (job names) to extract results for
            kubeconfig: Optional kubeconfig JSON
            job_timing_map: Optional timing data from job monitoring
                {job_id: {startTime, completionTime, status, ...}}

        Returns:
            {
                "success": bool,
                "results": [
                    {
                        "run_id": "...",
                        "eval_id": "...",
                        "status": "success|error",
                        "startTime": "2025-11-11T10:00:00Z",
                        "completionTime": "2025-11-11T10:15:30Z",
                        "duration_seconds": 930.0,
                        "scores": [
                            {
                                "dataset": "demo_gsm8k",
                                "metric": "accuracy",
                                "score": 65.62,
                                "version": "1d7fe4"
                            }
                        ]
                    }
                ]
            }
        """
        temp_id = f"extract-{uuid.uuid4().hex[:8]}"
        playbook = "extract_results_k8s.yml"

        files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

        # Build Extra Args
        namespace = StorageConfig.get_current_namespace()
        extravars["namespace"] = namespace
        extravars["eval_id"] = eval_id
        extravars["run_ids"] = ",".join(run_ids)
        extravars["temp_id"] = temp_id

        logger.info(f"Extracting results for eval_id={eval_id}, run_ids={run_ids}")

        # Run The Playbook
        try:
            self._run_ansible_playbook(playbook, temp_id, files, extravars)

            # Read results from temporary file created by playbook
            results_file = Path(tempfile.gettempdir()) / f"extraction_results_{temp_id}.json"

            if results_file.exists():
                with open(results_file, "r") as f:
                    extraction_results = json.load(f)
                results_file.unlink()  # Clean up

                # Merge timing information if available
                if extraction_results.get("success") and job_timing_map:
                    for result in extraction_results.get("results", []):
                        run_id = result.get("run_id")
                        if run_id and run_id in job_timing_map:
                            timing_info = job_timing_map[run_id]
                            result["startTime"] = timing_info.get("startTime", "")
                            result["completionTime"] = timing_info.get("completionTime", "")

                            # Calculate duration if both timestamps exist
                            start_time = timing_info.get("startTime")
                            completion_time = timing_info.get("completionTime")
                            if start_time and completion_time:
                                try:
                                    from datetime import datetime

                                    start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                                    end = datetime.fromisoformat(completion_time.replace("Z", "+00:00"))
                                    duration_seconds = (end - start).total_seconds()
                                    result["duration_seconds"] = duration_seconds
                                    logger.info(f"Job {run_id} duration: {duration_seconds}s")
                                except Exception as e:
                                    logger.warning(f"Failed to calculate duration for {run_id}: {e}")

                logger.info(f"Successfully extracted results for {len(run_ids)} runs")
                return extraction_results
            else:
                logger.error("Extraction results file not found")
                return {
                    "success": False,
                    "results": [],
                    "error": "Results file not created",
                }

        except Exception as e:
            logger.error(f"Failed to extract results: {e}", exc_info=True)
            return {"success": False, "results": [], "error": str(e)}

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

    def verify_cluster_connection(self, kubeconfig: Optional[str] = None) -> bool:
        """Verify cluster connection using an Ansible playbook via a kubeconfig in JSON form."""
        temp_id = f"verify-{uuid.uuid4().hex}"
        playbook = "verify_cluster_k8s.yml"

        files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

        # Build Extra Args
        extravars["namespace"] = StorageConfig.get_current_namespace()

        # Run The Playbook
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

    def check_jobs_status(self, job_ids: list[str], kubeconfig: Optional[str] = None) -> dict:
        """Check status of multiple Kubernetes jobs.

        Args:
            job_ids: List of job names to check
            kubeconfig: Optional kubeconfig JSON

        Returns:
            {
                "job1": {
                    "status": "Running|Succeeded|Failed",
                    "phase": "Pending|Running|Succeeded|Failed",
                    "message": "Error message if failed",
                    "completionTime": "2025-10-17T00:10:00Z"
                },
                "job2": {...}
            }
        """
        temp_id = f"check-status-{uuid.uuid4().hex}"
        playbook = "check_job_status_k8s.yml"

        files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

        # Build Extra Args
        namespace = StorageConfig.get_current_namespace()
        extravars["namespace"] = namespace
        extravars["job_names"] = ",".join(job_ids)  # Pass as comma-separated string

        # Set temp ID in environment for Ansible playbook
        extravars["temp_id"] = temp_id

        # Run The Playbook
        try:
            self._run_ansible_playbook(playbook, temp_id, files, extravars)

            # Read results from temporary file created by playbook
            results_file = Path(tempfile.gettempdir()) / f"job_status_{temp_id}.json"

            if results_file.exists():
                with open(results_file, "r") as f:
                    job_statuses = json.load(f)
                results_file.unlink()  # Clean up

                logger.info(f"Retrieved status for {len(job_statuses)} jobs")
                return job_statuses
            else:
                logger.error("Job status results file not found")
                return {}

        except Exception as e:
            logger.error(f"Failed to check job status: {e}", exc_info=True)
            # Return empty dict on error - monitoring will retry
            return {}

    def parse_job_logs(self, job_ids: list[str], kubeconfig: Optional[str] = None) -> dict:
        """Parse pod logs to extract ETA and progress data from OpenCompass logs.

        Args:
            job_ids: List of job names to parse logs for
            kubeconfig: Optional kubeconfig JSON

        Returns:
            {
                "job_id": {
                    "eta_data": {
                        "total_eta_seconds": 487,
                        "total_batches": 66,
                        "total_tasks": 2,
                        "speed_per_batch": 7.38
                    },
                    "latest_progress": {
                        "remaining_seconds": 158,
                        "batches_completed": 45,
                        "batches_total": 66
                    },
                    "progress_percentage": 68.18,
                    "status": "running|starting|no_logs"
                }
            }
        """
        temp_id = f"parse-logs-{uuid.uuid4().hex[:8]}"
        playbook = "parse_job_logs_k8s.yml"

        files, extravars = self._parse_kubeconfig(kubeconfig, temp_id)

        # Build Extra Args
        namespace = StorageConfig.get_current_namespace()
        extravars["namespace"] = namespace
        extravars["job_names"] = ",".join(job_ids)
        extravars["temp_id"] = temp_id

        logger.info(f"Parsing logs for jobs: {job_ids}")

        # Run The Playbook
        try:
            self._run_ansible_playbook(playbook, temp_id, files, extravars)

            # Read results from temporary file
            results_file = Path(tempfile.gettempdir()) / f"log_progress_{temp_id}.json"

            if results_file.exists():
                with open(results_file, "r") as f:
                    log_progress = json.load(f)
                results_file.unlink()  # Clean up

                logger.info(f"Parsed logs for {len(log_progress)} jobs")
                return log_progress
            else:
                logger.warning("Log progress results file not found")
                return {}

        except Exception as e:
            logger.error(f"Failed to parse job logs: {e}", exc_info=True)
            # Return empty dict on error - monitoring will continue
            return {}

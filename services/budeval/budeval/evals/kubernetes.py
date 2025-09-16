"""Kubernetes operations using simplified Ansible orchestrator."""

import logging
from typing import Any, Dict, Optional

import yaml

from budeval.ansible.orchestrator import AnsibleOrchestrator
from budeval.commons.config import app_settings
from budeval.evals.opencompass import OpenCompassHandler
from budeval.evals.schemas import EvaluationRequest, JobStatus


logger = logging.getLogger(__name__)


class KubernetesManager:
    """Manages Kubernetes operations for evaluation jobs."""

    def __init__(self):
        """Initialize the Kubernetes manager."""
        self.orchestrator = AnsibleOrchestrator()
        self.opencompass = OpenCompassHandler()

    def verify_cluster(self, namespace: str, kubeconfig: Optional[str] = None) -> bool:
        """Verify Kubernetes cluster connectivity."""
        try:
            return self.orchestrator.verify_cluster(namespace, kubeconfig)
        except Exception as e:
            logger.error(f"Cluster verification failed: {e}")
            return False

    def deploy_evaluation_job(self, request: EvaluationRequest) -> Dict[str, Any]:
        """Deploy an evaluation job to Kubernetes."""
        job_id = f"eval-{request.eval_request_id}"

        try:
            # Generate complete job YAML with ConfigMap
            job_yaml = self._generate_complete_yaml(job_id, request)

            # Deploy job using Ansible
            result = self.orchestrator.deploy_job(
                job_id=job_id, job_yaml=job_yaml, namespace=request.namespace, kubeconfig=request.kubeconfig
            )

            if result.get("success"):
                logger.info(f"Successfully deployed evaluation job: {job_id}")
                return {"job_id": job_id, "status": "deployed", "namespace": request.namespace}
            else:
                logger.error(f"Failed to deploy job: {job_id}")
                return {"job_id": job_id, "status": "failed", "error": "Deployment failed"}

        except Exception as e:
            logger.error(f"Error deploying job {job_id}: {e}")
            return {"job_id": job_id, "status": "error", "error": str(e)}

    def get_job_status(self, job_id: str, namespace: str, kubeconfig: Optional[str] = None) -> Dict[str, Any]:
        """Get the status of an evaluation job."""
        try:
            result = self.orchestrator.get_job_status(job_id=job_id, namespace=namespace, kubeconfig=kubeconfig)

            status_str = result.get("status", "unknown")

            # Map Ansible status to our JobStatus enum
            status_mapping = {
                "completed": JobStatus.COMPLETED,
                "failed": JobStatus.FAILED,
                "running": JobStatus.RUNNING,
                "pending": JobStatus.PENDING,
            }

            status = status_mapping.get(status_str, JobStatus.PENDING)

            return {
                "job_id": job_id,
                "status": status.value,
                "details": result.get("details", {}),
                "raw_status": result,
            }

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return {"job_id": job_id, "status": JobStatus.FAILED.value, "error": str(e)}

    def cleanup_job(self, job_id: str, namespace: str, kubeconfig: Optional[str] = None) -> bool:
        """Clean up an evaluation job and its resources."""
        try:
            return self.orchestrator.cleanup_job(job_id=job_id, namespace=namespace, kubeconfig=kubeconfig)
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {e}")
            return False

    def extract_results(self, job_id: str, namespace: str, kubeconfig: Optional[str] = None) -> Dict[str, Any]:
        """Extract evaluation results from PVC."""
        try:
            local_path = str(app_settings.extraction_base_path)

            result = self.orchestrator.extract_results(
                job_id=job_id, namespace=namespace, local_path=local_path, kubeconfig=kubeconfig
            )

            return result

        except Exception as e:
            logger.error(f"Error extracting results for {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def _generate_complete_yaml(self, job_id: str, request: EvaluationRequest) -> str:
        """Generate complete YAML with ConfigMap and Job."""
        # Get OpenCompass configuration
        config_files = self.opencompass.generate_config(request)
        command = self.opencompass.build_command(request)
        env_vars = self.opencompass.get_environment_variables(request)
        resources = self.opencompass.get_resource_requirements()

        # ConfigMap name
        configmap_name = f"opencompass-config-{request.eval_request_id}"

        # Build environment variables list
        env_list = [{"name": k, "value": v} for k, v in env_vars.items()]

        # ConfigMap
        configmap = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": configmap_name,
                "namespace": request.namespace,
                "labels": {"app": "budeval", "eval-request-id": str(request.eval_request_id)},
            },
            "data": config_files,
        }

        # Job
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_id,
                "namespace": request.namespace,
                "labels": {
                    "app": "budeval",
                    "eval-request-id": str(request.eval_request_id),
                    "model": request.model.name,
                },
            },
            "spec": {
                "ttlSecondsAfterFinished": request.timeout_minutes * 60,
                "backoffLimit": 2,
                "template": {
                    "metadata": {"labels": {"app": "budeval", "job-name": job_id}},
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "opencompass",
                                "image": app_settings.opencompass_image,
                                "command": ["/bin/bash", "-c"],
                                "args": [command],
                                "env": env_list,
                                "volumeMounts": [
                                    {"name": "config", "mountPath": "/workspace/configs", "readOnly": True},
                                    {
                                        "name": "shared-storage",
                                        "mountPath": "/workspace/data",
                                        "subPath": "data",
                                        "readOnly": True,
                                    },
                                    {
                                        "name": "shared-storage",
                                        "mountPath": "/workspace/outputs",
                                        "subPath": f"results/{job_id}",
                                    },
                                    {"name": "cache", "mountPath": "/workspace/cache"},
                                ],
                                "resources": {
                                    "requests": {
                                        "memory": resources["memory_request"],
                                        "cpu": resources["cpu_request"],
                                    },
                                    "limits": {"memory": resources["memory_limit"], "cpu": resources["cpu_limit"]},
                                },
                            }
                        ],
                        "volumes": [
                            {"name": "config", "configMap": {"name": configmap_name}},
                            {
                                "name": "shared-storage",
                                "persistentVolumeClaim": {"claimName": app_settings.opencompass_dataset_path},
                            },
                            {"name": "cache", "emptyDir": {}},
                        ],
                    },
                },
            },
        }

        # Combine ConfigMap and Job
        combined_yaml = f"""---
{yaml.dump(configmap, default_flow_style=False)}
---
{yaml.dump(job, default_flow_style=False)}
"""

        return combined_yaml

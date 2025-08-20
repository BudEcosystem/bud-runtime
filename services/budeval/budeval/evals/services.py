from typing import Optional, Union

from budmicroframe.commons.schemas import ErrorResponse, WorkflowMetadataResponse

from budeval.commons.logging import logging
from budeval.evals.kubernetes import KubernetesClusterHandler
from budeval.evals.schemas import DeployEvalJobRequest, StartEvaluationRequest

# Import engines to ensure they are registered
from budeval.registry.engines import opencompass  # noqa: F401


logger = logging.getLogger(__name__)


class EvaluationOpsService:
    """Service for evaluation."""

    @classmethod
    async def verify_cluster_connection(
        cls, verify_cluster_connection_request: StartEvaluationRequest, task_id: str, workflow_id: str
    ):
        """Verify cluster connection."""
        logger.info(f"Verifying cluster connection for workflow_id: {workflow_id} and task_id: {task_id}")
        k8_handler = KubernetesClusterHandler()
        # Use empty string if kubeconfig is None (will use default kubeconfig)
        kubeconfig = verify_cluster_connection_request.kubeconfig or ""
        return k8_handler.verify_cluster_connection(kubeconfig)

    @classmethod
    async def deploy_eval_job(
        cls, evaluate_model_request: DeployEvalJobRequest, task_id: str, workflow_id: str
    ) -> dict:
        """Deploy evaluation job with persistent volumes."""
        logger.info(f"Deploying evaluation job for workflow_id: {workflow_id} and task_id: {task_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Create unique job identifier
            job_uuid = f"eval-{evaluate_model_request.eval_request_id}"
            logger.info(f"Creating job with UUID: {job_uuid}")

            # Get engine metadata for Docker image
            from budeval.registry.engines.core import EngineRegistry

            # Debug: List all registered engines
            registered_engines = EngineRegistry.list_engines()
            logger.info(f"Registered engines: {list(registered_engines.keys())}")

            try:
                engine_metadata = EngineRegistry.get_metadata(evaluate_model_request.engine)
                logger.info(
                    f"Using engine: {evaluate_model_request.engine}, Docker image: {engine_metadata.docker_image_url}"
                )
            except KeyError as e:
                logger.error(f"Engine {evaluate_model_request.engine} not found in registry: {e}")
                logger.error(f"Available engines: {list(registered_engines.keys())}")
                raise ValueError(f"Unsupported engine: {evaluate_model_request.engine}") from e

            # Prepare engine arguments
            engine_args = {
                "model_name": evaluate_model_request.eval_request_id,
                "api_key": evaluate_model_request.api_key,
                "base_url": evaluate_model_request.base_url,
                "datasets": evaluate_model_request.dataset,
                "engine": evaluate_model_request.engine,
            }
            logger.info(f"Engine arguments prepared: {engine_args}")

            # Deploy job with volumes
            logger.info(
                "Deploying job with volumes - Shared datasets at /workspace/data, Output: 10Gi at /workspace/outputs"
            )
            ansible_orchestrator.run_job_with_volumes(
                runner_type="kubernetes",
                uuid=job_uuid,
                kubeconfig=evaluate_model_request.kubeconfig,
                engine_args=engine_args,
                docker_image=engine_metadata.docker_image_url,
                namespace="budeval",
                ttl_seconds=7200,  # 2 hour TTL to allow extraction time
                output_volume_size="10Gi",  # Testing
            )

            logger.info(f"Successfully deployed evaluation job {job_uuid}")
            return {
                "job_id": job_uuid,
                "status": "deployed",
                "namespace": "budeval",
                "data_volume": f"{job_uuid}-data-pv",
                "output_volume": f"{job_uuid}-output-pv",
            }

        except Exception as e:
            logger.error(f"Failed to deploy evaluation job: {e}", exc_info=True)
            raise e

    @classmethod
    async def deploy_eval_job_with_transformation(
        cls, evaluate_model_request: DeployEvalJobRequest, transformed_data: dict, task_id: str, workflow_id: str
    ) -> dict:
        """Deploy evaluation job using transformed configuration data."""
        logger.info(
            f"Deploying evaluation job with transformation for workflow_id: {workflow_id} and task_id: {task_id}"
        )

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Extract job configuration from transformed data
            job_config = transformed_data.get("job_config", {})
            job_uuid = job_config.get("job_id", f"eval-{evaluate_model_request.eval_request_id}")

            # Debug logging
            logger.info(f"Transformed data keys: {list(transformed_data.keys())}")
            logger.info(f"Job config keys: {list(job_config.keys())}")

            # If args are missing (due to payload size reduction), regenerate them
            if not job_config.get("args"):
                logger.info("Args missing from job_config, regenerating command...")
                try:
                    # TODO: Regenerate command using transformer

                    from uuid import UUID

                    from budeval.core.schemas import (
                        EvaluationEngine,
                        GenericDatasetConfig,
                        GenericEvaluationRequest,
                        GenericModelConfig,
                        ModelType,
                    )
                    from budeval.core.transformers.opencompass_transformer import OpenCompassTransformer

                    # Create a generic request from the original request
                    datasets = [
                        GenericDatasetConfig(name=d, category="custom")
                        for d in evaluate_model_request.dataset
                        if isinstance(d, str)
                    ]

                    # Create model config
                    model_config = GenericModelConfig(
                        name=evaluate_model_request.eval_request_id,
                        type=ModelType.API,
                        api_key=evaluate_model_request.api_key,
                        base_url=evaluate_model_request.base_url,
                    )

                    generic_request = GenericEvaluationRequest(
                        eval_request_id=UUID(evaluate_model_request.eval_request_id),
                        engine=EvaluationEngine.OPENCOMPASS,
                        model=model_config,
                        datasets=datasets,
                    )

                    # Regenerate command using transformer
                    transformer = OpenCompassTransformer()
                    command, args = transformer.build_command(generic_request)
                    job_config["command"] = command
                    job_config["args"] = args
                    logger.info(f"Regenerated command with args length: {len(args[0]) if args else 0}")

                except Exception as e:
                    logger.error(f"Failed to regenerate command: {e}")
                    # Fallback to a simple command
                    job_config["args"] = ["echo 'Command regeneration failed'; exit 1"]

            logger.info(f"Job config command: {job_config.get('command')}")
            logger.info(
                f"Job config args: {job_config.get('args', [''])[0][:200] if job_config.get('args') else 'None'}"
            )

            logger.info(f"Creating job with UUID: {job_uuid}")
            logger.info(f"Using engine: {job_config.get('engine')}, Docker image: {job_config.get('image')}")

            # Deploy job with transformed configuration
            logger.info("Deploying job with transformed configuration and volumes")
            ansible_orchestrator.run_job_with_generic_config(
                runner_type="kubernetes",
                uuid=job_uuid,
                kubeconfig=evaluate_model_request.kubeconfig,
                job_config=job_config,
                namespace="budeval",
            )

            logger.info(f"Successfully deployed evaluation job {job_uuid}")
            return {
                "job_id": job_uuid,
                "status": "deployed",
                "namespace": "budeval",
                "engine": job_config.get("engine"),
                "output_volume": job_config.get("output_volume", {}).get("claimName"),
            }

        except Exception as e:
            logger.error(f"Failed to deploy evaluation job with transformation: {e}", exc_info=True)
            raise e

    @classmethod
    async def get_job_status(cls, job_id: str, kubeconfig: Optional[str], namespace: str = "budeval") -> dict:
        """Get the status of a deployed evaluation job."""
        logger.info(f"Getting status for job: {job_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Get job status using Ansible
            status = ansible_orchestrator.get_job_status(job_id, kubeconfig, namespace)

            return {
                "job_id": job_id,
                "status": status.get("status", "unknown"),
                "namespace": namespace,
                "details": status,
            }

        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}", exc_info=True)
            return {"job_id": job_id, "status": "error", "error": str(e)}

    @classmethod
    async def cleanup_job(cls, job_id: str, kubeconfig: Optional[str], namespace: str = "budeval") -> dict:
        """Clean up a deployed evaluation job and its resources."""
        logger.info(f"Cleaning up job: {job_id}")

        try:
            from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

            # Initialize Ansible orchestrator
            ansible_orchestrator = AnsibleOrchestrator()

            # Clean up job resources
            ansible_orchestrator.cleanup_job_resources(job_id, kubeconfig, namespace)

            return {"job_id": job_id, "status": "cleaned_up", "namespace": namespace}

        except Exception as e:
            logger.error(f"Failed to cleanup job {job_id}: {e}", exc_info=True)
            return {"job_id": job_id, "status": "cleanup_failed", "error": str(e)}


class EvaluationService:
    """Service for evaluation."""

    async def evaluate_model(
        self, evaluate_model_request: StartEvaluationRequest
    ) -> Union[WorkflowMetadataResponse, ErrorResponse]:
        """Evaluate model.

        Args:
            evaluate_model_request: StartEvaluationRequest

        Returns:
            Union[WorkflowMetadataResponse, ErrorResponse]
        """
        logger.info(f"Model Evaluation Started for workflow_id: {evaluate_model_request.eval_model_info.model_name}")

        response: Union[WorkflowMetadataResponse, ErrorResponse]

        from .workflows import EvaluationWorkflow

        try:
            response = await EvaluationWorkflow().__call__(evaluate_model_request)
        except Exception as e:
            logger.error(f"Error evaluating model: {e}", exc_info=True)
            return ErrorResponse(message=f"Error evaluating model: {e}")
        return response

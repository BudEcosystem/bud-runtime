"""Results processor for extracting and processing evaluation results."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from budeval.commons.logging import logging
from budeval.registry.orchestrator.ansible_orchestrator import AnsibleOrchestrator

from .result_schemas import (
    DatasetResult,
    EvaluationSummary,
    OpenCompassOutputStructure,
    PredictionItem,
    ProcessedEvaluationResults,
    ResultsProcessingError,
)
from .storage.base import StorageAdapter
from .storage.factory import get_storage_adapter


logger = logging.getLogger(__name__)


class ResultsProcessor:
    """Process evaluation results from PVC and store using storage adapter."""

    def __init__(
        self, storage_adapter: Optional[StorageAdapter] = None, extraction_base_path: str = "/tmp/eval_extractions"
    ):
        """Initialize results processor.

        Args:
            storage_adapter: Storage adapter to use for saving results. If None, uses factory.
            extraction_base_path: Base path for extracting files locally
        """
        self.storage = storage_adapter or get_storage_adapter()
        self.extraction_base_path = Path(extraction_base_path)
        self.extraction_base_path.mkdir(parents=True, exist_ok=True)
        self.orchestrator = AnsibleOrchestrator()
        logger.info(
            f"Initialized results processor with {self.storage.__class__.__name__} storage and extraction path: {self.extraction_base_path}"
        )

    def extract_from_pvc(self, job_id: str, namespace: str = "budeval", kubeconfig: Optional[str] = None) -> str:
        """Extract results from PVC using Ansible playbook.

        Args:
            job_id: Job ID to extract results for
            namespace: Kubernetes namespace
            kubeconfig: Optional kubeconfig content

        Returns:
            Local path where results were extracted

        Raises:
            Exception: If extraction fails
        """
        logger.info(f"Starting PVC extraction for job {job_id}")

        # Check if PVC exists before attempting extraction
        import subprocess

        # Remove engine prefix from job_id if present (e.g., "opencompass-uuid" -> "uuid")
        uuid_part = (
            job_id.split("-", 1)[-1]
            if "-" in job_id and job_id.startswith(("opencompass-", "vllm-", "lighteval-"))
            else job_id
        )
        pvc_name = f"{uuid_part}-output-pvc"
        try:
            cmd = ["kubectl", "get", "pvc", pvc_name, "-n", namespace]
            if kubeconfig:
                kubeconfig_path = self.extraction_base_path / f"{job_id}_kubeconfig_check.yaml"
                with open(kubeconfig_path, "w") as f:
                    f.write(kubeconfig)
                cmd.extend(["--kubeconfig", str(kubeconfig_path)])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if kubeconfig and kubeconfig_path.exists():
                kubeconfig_path.unlink()

            if result.returncode != 0:
                raise Exception(
                    f"PVC {pvc_name} not found in namespace {namespace}. Cannot extract results from missing PVC."
                )

            logger.info(f"PVC {pvc_name} found, proceeding with extraction")
        except subprocess.TimeoutExpired as err:
            raise Exception(f"Timeout checking for PVC {pvc_name}") from err
        except Exception as e:
            logger.error(f"Failed to verify PVC {pvc_name} exists: {e}")
            raise Exception(f"Cannot extract results: PVC verification failed - {e}") from e

        local_extract_path = str(self.extraction_base_path)

        # Prepare Ansible variables
        ansible_vars = {
            "job_id": job_id,
            "namespace": namespace,
            "local_extract_path": local_extract_path,
        }

        if kubeconfig:
            # Write kubeconfig to temporary file
            kubeconfig_path = self.extraction_base_path / f"{job_id}_kubeconfig.yaml"
            with open(kubeconfig_path, "w") as f:
                f.write(kubeconfig)
            ansible_vars["kubeconfig_path"] = str(kubeconfig_path)

        try:
            # Run extraction playbook - use the synchronous method and handle it
            import uuid

            temp_id = str(uuid.uuid4())

            result = self.orchestrator._run_ansible_playbook_with_output(
                playbook="extract_results_from_pvc.yml", uuid=temp_id, files={}, extravars=ansible_vars
            )

            # Check if playbook succeeded - ansible_runner result has .rc attribute
            if not result or result.rc != 0:
                error_msg = f"Ansible playbook failed with return code: {result.rc}"
                if hasattr(result, "stdout") and result.stdout:
                    error_msg += f", stdout: {result.stdout.read()}"
                if hasattr(result, "stderr") and result.stderr:
                    error_msg += f", stderr: {result.stderr.read()}"
                raise Exception(error_msg)

            extracted_path = f"{local_extract_path}/{job_id}/outputs"

            # Verify extraction was successful
            if not os.path.exists(extracted_path):
                raise Exception(f"Extraction failed: path {extracted_path} does not exist")

            logger.info(f"Successfully extracted results to {extracted_path}")
            return extracted_path

        except Exception as e:
            logger.error(f"Failed to extract results for job {job_id}: {e}")
            raise
        finally:
            # Clean up kubeconfig file if created
            if kubeconfig:
                kubeconfig_path = self.extraction_base_path / f"{job_id}_kubeconfig.yaml"
                if kubeconfig_path.exists():
                    kubeconfig_path.unlink()

    def _find_timestamp_directory(self, extracted_path: str) -> Optional[str]:
        """Find the timestamp directory in extracted results.

        Args:
            extracted_path: Path where results were extracted

        Returns:
            Name of the timestamp directory or None if not found
        """
        try:
            extracted_dir = Path(extracted_path)
            if not extracted_dir.exists():
                return None

            # Look for directories that match timestamp pattern (YYYYMMDD_HHMMSS)
            for item in extracted_dir.iterdir():
                if item.is_dir() and len(item.name) == 15 and "_" in item.name:
                    return item.name

            return None

        except Exception as e:
            logger.error(f"Error finding timestamp directory: {e}")
            return None

    def _parse_opencompass_structure(self, results_path: Path) -> OpenCompassOutputStructure:
        """Parse OpenCompass output directory structure.

        Args:
            results_path: Path to the timestamp directory

        Returns:
            OpenCompassOutputStructure with file locations
        """
        structure = OpenCompassOutputStructure(timestamp_dir=results_path.name)

        try:
            # Parse configs
            configs_dir = results_path / "configs"
            if configs_dir.exists():
                structure.configs_files = [f.name for f in configs_dir.iterdir() if f.is_file()]

            # Parse predictions
            predictions_dir = results_path / "predictions"
            if predictions_dir.exists():
                for model_dir in predictions_dir.iterdir():
                    if model_dir.is_dir():
                        for dataset_file in model_dir.iterdir():
                            if dataset_file.is_file() and dataset_file.suffix == ".json":
                                dataset_name = dataset_file.stem
                                structure.prediction_files[dataset_name] = str(dataset_file)

            # Parse results
            results_dir = results_path / "results"
            if results_dir.exists():
                for model_dir in results_dir.iterdir():
                    if model_dir.is_dir():
                        for dataset_file in model_dir.iterdir():
                            if dataset_file.is_file() and dataset_file.suffix == ".json":
                                dataset_name = dataset_file.stem
                                structure.result_files[dataset_name] = str(dataset_file)

            # Parse summary files
            summary_dir = results_path / "summary"
            if summary_dir.exists():
                for summary_file in summary_dir.iterdir():
                    if summary_file.is_file():
                        if summary_file.suffix == ".csv":
                            structure.summary_files["csv"] = str(summary_file)
                        elif summary_file.suffix == ".md":
                            structure.summary_files["markdown"] = str(summary_file)
                        elif summary_file.suffix == ".txt":
                            structure.summary_files["text"] = str(summary_file)

            # Parse logs
            logs_dir = results_path / "logs"
            if logs_dir.exists():
                for log_type_dir in logs_dir.iterdir():
                    if log_type_dir.is_dir():
                        log_files = []
                        for model_dir in log_type_dir.iterdir():
                            if model_dir.is_dir():
                                for log_file in model_dir.iterdir():
                                    if log_file.is_file():
                                        log_files.append(str(log_file))
                        structure.log_files[log_type_dir.name] = log_files

            return structure

        except Exception as e:
            logger.error(f"Error parsing OpenCompass structure: {e}")
            return structure

    def _parse_predictions(self, prediction_file_path: str) -> List[PredictionItem]:
        """Parse predictions from JSON file.

        Args:
            prediction_file_path: Path to predictions JSON file

        Returns:
            List of PredictionItem objects
        """
        try:
            with open(prediction_file_path, "r") as f:
                predictions_data = json.load(f)

            predictions = []
            for key, item in predictions_data.items():
                if isinstance(item, dict):
                    prediction = PredictionItem(
                        example_abbr=key,
                        pred=item.get("pred", []),
                        answer=item.get("answer", []),
                        correct=item.get("correct", []),
                        origin_prompt=item.get("origin_prompt"),
                        prediction=item.get("prediction"),
                    )
                    predictions.append(prediction)

            logger.debug(f"Parsed {len(predictions)} predictions from {prediction_file_path}")
            return predictions

        except Exception as e:
            logger.error(f"Failed to parse predictions from {prediction_file_path}: {e}")
            return []

    def _parse_results(self, result_file_path: str) -> Dict:
        """Parse results from JSON file.

        Args:
            result_file_path: Path to results JSON file

        Returns:
            Dictionary with accuracy and details
        """
        try:
            with open(result_file_path, "r") as f:
                results_data = json.load(f)

            logger.debug(f"Parsed results from {result_file_path}")
            return results_data

        except Exception as e:
            logger.error(f"Failed to parse results from {result_file_path}: {e}")
            return {}

    async def process_opencompass_results(
        self, extracted_path: str, job_id: str, model_name: str
    ) -> ProcessedEvaluationResults:
        """Process OpenCompass results from extracted path.

        Args:
            extracted_path: Path where results were extracted
            job_id: Job ID
            model_name: Model name

        Returns:
            ProcessedEvaluationResults object
        """
        logger.info(f"Processing OpenCompass results for job {job_id}")

        # Find timestamp directory
        timestamp_dir = self._find_timestamp_directory(extracted_path)
        if not timestamp_dir:
            raise Exception(f"No timestamp directory found in {extracted_path}")

        results_path = Path(extracted_path) / timestamp_dir

        # Parse directory structure
        structure = self._parse_opencompass_structure(results_path)

        # Process each dataset
        datasets = []
        total_examples = 0
        total_correct = 0
        dataset_accuracies = {}

        for dataset_name in structure.result_files:
            try:
                # Parse results file
                result_file_path = structure.result_files[dataset_name]
                results_data = self._parse_results(result_file_path)

                # Parse predictions file
                predictions = []
                if dataset_name in structure.prediction_files:
                    prediction_file_path = structure.prediction_files[dataset_name]
                    predictions = self._parse_predictions(prediction_file_path)

                # Calculate metrics
                accuracy = results_data.get("accuracy", 0.0)
                num_examples = len(predictions)
                num_correct = int(accuracy * num_examples / 100) if accuracy > 1 else int(accuracy * num_examples)

                # Create dataset result
                dataset_result = DatasetResult(
                    dataset_name=dataset_name,
                    accuracy=accuracy,
                    total_examples=num_examples,
                    correct_examples=num_correct,
                    predictions=predictions,
                    metadata={
                        "result_file": result_file_path,
                        "prediction_file": structure.prediction_files.get(dataset_name),
                    },
                )

                datasets.append(dataset_result)
                total_examples += num_examples
                total_correct += num_correct
                dataset_accuracies[dataset_name] = accuracy

                logger.debug(f"Processed dataset {dataset_name}: {accuracy}% accuracy ({num_correct}/{num_examples})")

            except Exception as e:
                logger.error(f"Failed to process dataset {dataset_name}: {e}")
                continue

        # Calculate overall summary
        overall_accuracy = (total_correct / total_examples * 100) if total_examples > 0 else 0.0

        summary = EvaluationSummary(
            overall_accuracy=overall_accuracy,
            total_datasets=len(datasets),
            total_examples=total_examples,
            total_correct=total_correct,
            dataset_accuracies=dataset_accuracies,
            model_name=model_name,
        )

        # Create final results
        processed_results = ProcessedEvaluationResults(
            job_id=job_id,
            model_name=model_name,
            engine="opencompass",
            datasets=datasets,
            summary=summary,
            raw_output=structure,
            extracted_at=datetime.utcnow(),
            extraction_path=extracted_path,
            output_pvc_name=f"{job_id}-output-pvc",
        )

        logger.info(
            f"Successfully processed results for job {job_id}: {len(datasets)} datasets, {overall_accuracy:.2f}% overall accuracy"
        )
        return processed_results

    async def extract_and_process(
        self, job_id: str, model_name: str, namespace: str = "budeval", kubeconfig: Optional[str] = None
    ) -> ProcessedEvaluationResults:
        """Extract results from PVC and process them.

        Args:
            job_id: Job ID to extract results for
            model_name: Model name
            namespace: Kubernetes namespace
            kubeconfig: Optional kubeconfig content

        Returns:
            ProcessedEvaluationResults object
        """
        try:
            # Extract from PVC
            extracted_path = self.extract_from_pvc(job_id, namespace, kubeconfig)

            # Process results
            results = await self.process_opencompass_results(extracted_path, job_id, model_name)

            # Store results
            await self.storage.save_results(job_id, results.model_dump())

            logger.info(f"Successfully extracted and processed results for job {job_id}")
            return results

        except Exception as e:
            logger.error(f"Failed to extract and process results for job {job_id}: {e}")

            # Save error information
            error = ResultsProcessingError(
                job_id=job_id,
                error_type=type(e).__name__,
                error_message=str(e),
                occurred_at=datetime.utcnow(),
                extraction_path=str(self.extraction_base_path / job_id),
            )

            await self.storage.save_results(f"{job_id}_error", error.model_dump())
            raise

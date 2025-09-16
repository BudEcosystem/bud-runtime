"""Simplified results processor for extracting and processing evaluation results."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from budeval.ansible.orchestrator import AnsibleOrchestrator
from budeval.commons.config import app_settings
from budeval.evals.storage.base import StorageAdapter


logger = logging.getLogger(__name__)


class PredictionItem:
    """Represents a single evaluation prediction with normalized fields."""

    def __init__(self, detail: Optional[Dict[str, Any]] = None, prediction: Optional[Dict[str, Any]] = None):
        """Normalize prediction and detail payloads into consistent attributes."""
        detail = detail or {}
        prediction = prediction or {}

        self.example_abbr = (
            detail.get("example_abbr")
            or prediction.get("example_abbr")
            or prediction.get("idx")
            or prediction.get("index")
            or "unknown"
        )

        self.pred = self._ensure_list(detail.get("pred") or prediction.get("pred") or prediction.get("prediction"))
        self.answer = self._ensure_list(detail.get("answer") or prediction.get("answer") or prediction.get("gold"))

        self.origin_prompt = prediction.get("origin_prompt") or detail.get("origin_prompt")
        self.prediction = prediction.get("prediction") or (self.pred[0] if self.pred else None)

        correct_raw = detail.get("correct") or prediction.get("correct")
        self.correct = self._ensure_bool_list(correct_raw)

        # Derive correctness when not provided explicitly
        if not self.correct and self.pred and self.answer:
            self.correct = [self.pred[0] == self.answer[0]]

        self.is_correct = bool(self.correct[0]) if self.correct else False

    @staticmethod
    def _ensure_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _ensure_bool_list(value: Any) -> List[bool]:
        if value is None:
            return []
        if isinstance(value, list):
            return [bool(v) for v in value]
        return [bool(value)]


class DatasetResult:
    """Results for a single dataset evaluation."""

    def __init__(self, dataset_name: str, accuracy: float, predictions: List[PredictionItem]):
        """Aggregate metrics for a single dataset run."""
        self.dataset_name = dataset_name
        self.accuracy = accuracy
        self.predictions = predictions
        self.total_examples = len(predictions)
        self.correct_examples = sum(1 for p in predictions if p.is_correct)


class EvaluationSummary:
    """Aggregated summary across all datasets."""

    def __init__(self, model_name: str, datasets: List[DatasetResult]):
        """Build aggregate summary statistics across datasets."""
        self.model_name = model_name
        self.total_datasets = len(datasets)
        self.total_examples = sum(d.total_examples for d in datasets)
        self.total_correct = sum(d.correct_examples for d in datasets)
        self.overall_accuracy = (self.total_correct / self.total_examples * 100) if self.total_examples > 0 else 0.0
        self.dataset_accuracies = {d.dataset_name: d.accuracy for d in datasets}


class ProcessedEvaluationResults:
    """Complete processed evaluation results."""

    def __init__(self, job_id: str, model_name: str, engine: str = "opencompass", experiment_id: Optional[str] = None):
        """Capture full evaluation output metadata and datasets for persistence."""
        self.job_id = job_id
        self.model_name = model_name
        self.engine = engine
        self.experiment_id = experiment_id
        self.datasets: List[DatasetResult] = []
        self.summary: Optional[EvaluationSummary] = None
        self.start_time = datetime.now()
        self.end_time = datetime.now()
        self.duration_seconds = 0.0
        self.extracted_at = datetime.now()
        self.extraction_path = ""

    def finalize(self):
        """Finalize the results by creating summary."""
        self.summary = EvaluationSummary(self.model_name, self.datasets)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def model_dump(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "job_id": self.job_id,
            "model_name": self.model_name,
            "engine": self.engine,
            "experiment_id": self.experiment_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "extracted_at": self.extracted_at.isoformat(),
            "extraction_path": self.extraction_path,
            "summary": {
                "model_name": self.summary.model_name,
                "overall_accuracy": self.summary.overall_accuracy,
                "total_datasets": self.summary.total_datasets,
                "total_examples": self.summary.total_examples,
                "total_correct": self.summary.total_correct,
                "dataset_accuracies": self.summary.dataset_accuracies,
            }
            if self.summary
            else {},
            "datasets": [
                {
                    "dataset_name": d.dataset_name,
                    "accuracy": d.accuracy,
                    "total_examples": d.total_examples,
                    "correct_examples": d.correct_examples,
                    "predictions": [
                        {
                            "example_abbr": p.example_abbr,
                            "pred": p.pred,
                            "answer": p.answer,
                            "correct": p.correct,
                            "origin_prompt": p.origin_prompt,
                            "prediction": p.prediction,
                        }
                        for p in d.predictions
                    ],
                }
                for d in self.datasets
            ],
        }


class ResultsProcessor:
    """Simplified processor for evaluation results."""

    def __init__(self, storage_adapter: StorageAdapter):
        """Initialize results processor."""
        self.storage_adapter = storage_adapter
        self.extraction_base_path = app_settings.extraction_base_path
        self.orchestrator = AnsibleOrchestrator()

    def extract_from_pvc(self, job_id: str, namespace: str = "budeval", kubeconfig: Optional[str] = None) -> str:
        """Extract results from shared PVC using Ansible playbook."""
        logger.info(f"Extracting results for job: {job_id}")

        local_extract_path = str(self.extraction_base_path)

        # Run extraction using orchestrator
        result = self.orchestrator.extract_results(
            job_id=job_id, namespace=namespace, local_path=local_extract_path, kubeconfig=kubeconfig
        )

        if not result.get("success"):
            raise Exception(f"Extraction failed: {result.get('error', 'Unknown error')}")

        extracted_path = result["local_path"]

        # Verify extraction was successful
        if not Path(extracted_path).exists():
            raise Exception(f"Extracted path does not exist: {extracted_path}")

        logger.info(f"Results extracted to: {extracted_path}")
        return extracted_path

    def _find_timestamp_directory(self, extracted_path: str) -> Optional[str]:
        """Find the timestamp directory in extracted results."""
        extracted_dir = Path(extracted_path)
        if not extracted_dir.exists():
            return None

        # Look for directories that match timestamp pattern (YYYYMMDD_HHMMSS)
        timestamp_pattern = re.compile(r"\d{8}_\d{6}")

        for item in extracted_dir.iterdir():
            if item.is_dir() and timestamp_pattern.match(item.name):
                return item.name

        return None

    def _load_prediction_entries(self, prediction_file_path: str) -> List[Dict[str, Any]]:
        """Load raw prediction entries from JSON file."""
        try:
            with open(prediction_file_path, "r") as f:
                predictions_data = json.load(f)

            if isinstance(predictions_data, dict):
                sorted_items = sorted(
                    predictions_data.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else str(kv[0])
                )
                return [item for _, item in sorted_items]
            if isinstance(predictions_data, list):
                return predictions_data

            logger.warning(f"Unexpected predictions format in {prediction_file_path}: {type(predictions_data)}")
            return []

        except Exception as e:
            logger.error(f"Failed to load predictions from {prediction_file_path}: {e}")
            return []

    def _parse_results(self, result_file_path: str) -> Dict:
        """Parse results from JSON file."""
        try:
            with open(result_file_path, "r") as f:
                results_data = json.load(f)

            # Extract accuracy - handle different formats
            accuracy = 0.0

            # OpenCompass can store results in different formats
            if isinstance(results_data, dict):
                # Look for accuracy in various keys
                for key in ["accuracy", "acc", "score"]:
                    if key in results_data:
                        accuracy = float(results_data[key])
                        break

                # If it's a nested structure, look deeper
                if accuracy == 0.0:
                    for value in results_data.values():
                        if isinstance(value, (int, float)):
                            accuracy = float(value)
                            break

            elif isinstance(results_data, (int, float)):
                accuracy = float(results_data)

            details = results_data.get("details", []) if isinstance(results_data, dict) else []

            return {"accuracy": accuracy, "details": details}

        except Exception as e:
            logger.error(f"Failed to parse results from {result_file_path}: {e}")
            return {"accuracy": 0.0, "details": []}

    def _build_prediction_items(
        self, prediction_entries: List[Dict[str, Any]], details: List[Dict[str, Any]]
    ) -> List[PredictionItem]:
        """Combine raw prediction entries and result details."""
        items: List[PredictionItem] = []
        max_len = max(len(prediction_entries), len(details))

        for idx in range(max_len):
            detail = details[idx] if idx < len(details) else None
            prediction = prediction_entries[idx] if idx < len(prediction_entries) else None
            items.append(PredictionItem(detail, prediction))

        return items

    async def process_opencompass_results(
        self, extracted_path: str, job_id: str, model_name: str, experiment_id: Optional[str] = None
    ) -> ProcessedEvaluationResults:
        """Process OpenCompass results from extracted path."""
        logger.info(f"Processing OpenCompass results for job: {job_id}")

        # Initialize results
        results = ProcessedEvaluationResults(job_id=job_id, model_name=model_name, experiment_id=experiment_id)
        results.extraction_path = extracted_path

        # Find timestamp directory
        timestamp_dir = self._find_timestamp_directory(extracted_path)
        if not timestamp_dir:
            raise Exception(f"No timestamp directory found in: {extracted_path}")

        results_path = Path(extracted_path) / timestamp_dir
        logger.info(f"Found results in timestamp directory: {timestamp_dir}")

        # Look for predictions and results directories
        predictions_dir = results_path / "predictions"
        results_dir = results_path / "results"

        if not predictions_dir.exists():
            logger.warning(f"Predictions directory not found: {predictions_dir}")
            results.finalize()
            return results

        # Process each dataset
        dataset_files = list(predictions_dir.rglob("*.json"))
        logger.info(f"Found {len(dataset_files)} dataset files")

        for pred_file in dataset_files:
            relative_path = pred_file.relative_to(predictions_dir)
            dataset_name = pred_file.stem
            logger.info(f"Processing dataset: {dataset_name}")

            # Load raw prediction entries
            prediction_entries = self._load_prediction_entries(str(pred_file))

            # Parse results if available
            result_file = results_dir / relative_path
            accuracy = 0.0
            details: List[Dict[str, Any]] = []

            if result_file.exists():
                results_data = self._parse_results(str(result_file))
                accuracy = results_data.get("accuracy", 0.0)
                details = results_data.get("details", [])
            else:
                logger.warning(f"No results file found for {relative_path}")
                details = []

            predictions = self._build_prediction_items(prediction_entries, details)

            # Fallback accuracy when results missing but predictions present
            if accuracy == 0.0 and predictions:
                correct_count = sum(1 for p in predictions if p.is_correct)
                if predictions:
                    accuracy = (correct_count / len(predictions)) * 100

            # Create dataset result
            dataset_result = DatasetResult(dataset_name=dataset_name, accuracy=accuracy, predictions=predictions)

            results.datasets.append(dataset_result)
            logger.info(
                f"Dataset {dataset_name}: {accuracy:.2f}% accuracy ({dataset_result.correct_examples}/{dataset_result.total_examples})"
            )

        # Finalize results
        results.finalize()

        logger.info(f"Processing completed. Overall accuracy: {results.summary.overall_accuracy:.2f}%")
        return results

    async def extract_and_process_results(
        self,
        job_id: str,
        model_name: str,
        namespace: str = "budeval",
        kubeconfig: Optional[str] = None,
        experiment_id: Optional[str] = None,
    ) -> ProcessedEvaluationResults:
        """Extract results from PVC and process them."""
        try:
            # Extract from PVC
            extracted_path = self.extract_from_pvc(job_id, namespace, kubeconfig)

            # Process results
            results = await self.process_opencompass_results(extracted_path, job_id, model_name, experiment_id)

            # Store results
            success = await self.storage_adapter.save_results(job_id, results.model_dump())

            if success:
                logger.info(f"Results successfully stored for job: {job_id}")
            else:
                logger.error(f"Failed to store results for job: {job_id}")

            return results

        except Exception as e:
            logger.error(f"Error processing results for job {job_id}: {e}")
            raise

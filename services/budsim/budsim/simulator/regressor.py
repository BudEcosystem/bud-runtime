import threading
from concurrent.futures import ThreadPoolExecutor
from os import path as osp
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.base import BaseEstimator

from ..commons.config import app_settings


lock = threading.Lock()


class BenchmarkPredictor:
    """A class to load sklearn models and make predictions for various metrics.

    This class is designed to load pre-trained models for predicting mean time to first token (TTFT),
    output token throughput per user, and end-to-end latency based on the provided input features.

    Attributes:
        mean_ttft_pipeline: The pipeline used for predicting mean TTFT.
        mean_ttft_scaler: The scaler used for normalizing input features for mean TTFT.
        mean_ttft_features: The list of input features required for mean TTFT prediction.
        op_tput_puser_pipeline: The pipeline used for predicting output token throughput per user.
        op_tput_puser_scaler: The scaler used for normalizing input features for output token throughput.
        op_tput_puser_features: The list of input features required for output token throughput prediction.
        e2e_latency_pipeline: The pipeline used for predicting end-to-end latency.
        e2e_latency_scaler: The scaler used for normalizing input features for end-to-end latency.
        e2e_latency_features: The list of input features required for end-to-end latency prediction.

    Args:
        engine (str): The engine type for which the models are loaded.
        device (str): The device type for which the models are loaded.
        pretrained_models_dir (Optional[str]): The directory containing the pre-trained models. If not provided,
            the default directory from app settings will be used.
    """

    def __init__(self, engine: str, device: str, pretrained_models_dir: Optional[str] = None) -> None:
        """Initialize the BenchmarkPredictor class by loading the required sklearn models.

        Args:
            engine (str): The engine type for which the models are loaded.
            device (str): The device type for which the models are loaded.
            pretrained_models_dir (Optional[str]): The directory containing the pre-trained models. If not provided,
                the default directory from app settings will be used.
        """
        pretrained_models_dir = pretrained_models_dir or app_settings.benchmark_predictor_models_dir
        mean_ttft_model_path = osp.join(pretrained_models_dir, engine, device, "regressor_mean_ttft_ms.pkl")
        op_tput_puser_model_path = osp.join(
            pretrained_models_dir, engine, device, "regressor_output_token_throughput_per_user_tok_s.pkl"
        )
        e2e_latency_model_path = osp.join(
            pretrained_models_dir, engine, device, "regressor_mean_end_to_end_latency_s.pkl"
        )

        assert osp.exists(pretrained_models_dir), (
            f"Pretrained models directory does not exist: {pretrained_models_dir}"
        )
        assert osp.isfile(mean_ttft_model_path), f"Mean TTFT model for {engine} on {device} does not exist"
        assert osp.isfile(op_tput_puser_model_path), (
            f"Output Token Throughput per User model for {engine} on {device} does not exist"
        )
        assert osp.isfile(e2e_latency_model_path), (
            f"Mean End to End Latency model for {engine} on {device} does not exist"
        )

        self.mean_ttft_pipeline, self.mean_ttft_scaler, self.mean_ttft_features = self.load_model(mean_ttft_model_path)

        self.op_tput_puser_pipeline, self.op_tput_puser_scaler, self.op_tput_puser_features = self.load_model(
            op_tput_puser_model_path
        )

        self.e2e_latency_pipeline, self.e2e_latency_scaler, self.e2e_latency_features = self.load_model(
            e2e_latency_model_path
        )

    def load_model(self, model_path: str) -> None:
        """Load a model from the specified path."""
        if lock.acquire(timeout=60):
            try:
                model = joblib.load(model_path)
                pipeline = model["pipeline"]
                scaler = model["scaler"]
                features = model["input_features"]
                return pipeline, scaler, features
            finally:
                lock.release()
        else:
            raise RuntimeError(f"Failed to acquire lock for {model_path} in 60 seconds")

    def prepare_input(
        self, inp: Dict[str, Any], features: List[str], scaler: Optional[BaseEstimator] = None
    ) -> np.ndarray:
        """Prepare the input data for prediction by ensuring all required features are present and scaling if necessary.

        Args:
            inp (Dict[str, Any]): The input data containing features for prediction.
            features (List[str]): The list of required features for the prediction.
            scaler (Optional[BaseEstimator]): The scaler to apply to the input data.

        Returns:
            np.ndarray: The prepared input data as a numpy array, optionally scaled.

        Raises:
            AssertionError: If any required features are missing from the input.
        """
        missing_features = [feature for feature in features if feature not in inp]
        assert not missing_features, f"Not all features are available in the input: {', '.join(missing_features)}"
        arr = np.array([inp[feature] for feature in features])
        if arr.ndim == 1:
            arr = np.expand_dims(arr, axis=0)
        if scaler is not None:
            return scaler.transform(arr)
        return arr

    def predict_mean_ttft(self, inp: Dict[str, Any]) -> float:
        """Predict the Mean Time to First Token (TTFT) for the given input.

        Args:
            inp (Dict[str, Any]): The input data containing features for prediction.

        Returns:
            float: The predicted Mean TTFT value.
        """
        X = self.prepare_input(inp, self.mean_ttft_features, self.mean_ttft_scaler)
        return float(self.mean_ttft_pipeline.predict(X)[0])

    def predict_op_tput_puser(self, inp: Dict[str, Any]) -> float:
        """Predict the Output Token Throughput per User for the given input.

        Args:
            inp (Dict[str, Any]): The input data containing features for prediction.

        Returns:
            float: The predicted Output Token Throughput per User value.
        """
        X = self.prepare_input(inp, self.op_tput_puser_features, self.op_tput_puser_scaler)
        return float(self.op_tput_puser_pipeline.predict(X)[0])

    def predict_e2e_latency(self, inp: Dict[str, Any]) -> float:
        """Predict the Mean End to End Latency for the given input.

        Args:
            inp (Dict[str, Any]): The input data containing features for prediction.

        Returns:
            float: The predicted Mean End to End Latency value.
        """
        X = self.prepare_input(inp, self.e2e_latency_features, self.e2e_latency_scaler)
        return float(self.e2e_latency_pipeline.predict(X)[0])

    def __call__(self, inp: Dict[str, Any]) -> Tuple[float, float, float]:
        """Predict the output for the given input data.

        Args:
            inp (Dict[str, Any]): Input data for which predictions are to be made.

        Returns:
            Tuple[float, float, float]: The predicted Mean TTFT, Output Token Throughput per User, and Mean End to End Latency.
        """
        with ThreadPoolExecutor() as executor:
            future1 = executor.submit(self.predict_mean_ttft, inp)
            future2 = executor.submit(self.predict_op_tput_puser, inp)
            future3 = executor.submit(self.predict_e2e_latency, inp)

            mean_ttft, op_tput_puser, e2e_latency = future1.result(), future2.result(), future3.result()
            return mean_ttft, op_tput_puser, e2e_latency

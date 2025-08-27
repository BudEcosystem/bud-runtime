"""Kubernetes ConfigMap manager for OpenCompass configurations."""

import json
from typing import Any, Dict, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from budeval.commons.logging import logging

from .config_generator import OpenCompassConfigGenerator


logger = logging.getLogger(__name__)


class ConfigMapManager:
    """Manages Kubernetes ConfigMaps for OpenCompass configurations."""

    def __init__(self, namespace: Optional[str] = None):
        """Initialize ConfigMap manager.

        Args:
            namespace: Kubernetes namespace to use. If None, uses current namespace.
        """
        if namespace is None:
            from budeval.commons.storage_config import StorageConfig

            namespace = StorageConfig.get_current_namespace()
        self.namespace = namespace
        self.api_client = None

    def _get_k8s_client(self, kubeconfig: Optional[str] = None) -> client.CoreV1Api:
        """Get Kubernetes API client.

        Args:
            kubeconfig: Optional kubeconfig content

        Returns:
            Kubernetes CoreV1Api client
        """
        if self.api_client:
            return self.api_client

        try:
            if kubeconfig:
                # Load kubeconfig from string
                import tempfile

                import yaml

                # Parse kubeconfig
                if isinstance(kubeconfig, str):
                    try:
                        kubeconfig_dict = json.loads(kubeconfig)
                    except json.JSONDecodeError:
                        try:
                            kubeconfig_dict = yaml.safe_load(kubeconfig)
                        except yaml.YAMLError as e:
                            logger.error("Invalid kubeconfig format")
                            raise ValueError("Invalid kubeconfig format") from e
                else:
                    kubeconfig_dict = kubeconfig

                # Write to temporary file
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                    yaml.dump(kubeconfig_dict, f)
                    temp_kubeconfig_path = f.name

                # Load config from file
                config.load_kube_config(config_file=temp_kubeconfig_path)

                # Clean up temporary file
                import os

                os.unlink(temp_kubeconfig_path)
            else:
                # Try in-cluster config first, then local config
                try:
                    config.load_incluster_config()
                    logger.info("Using in-cluster Kubernetes configuration")
                except config.ConfigException:
                    config.load_kube_config()
                    logger.info("Using local Kubernetes configuration")

            self.api_client = client.CoreV1Api()
            return self.api_client

        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise

    def create_opencompass_config_map(
        self,
        eval_request_id: str,
        model_name: str,
        api_key: str,
        base_url: str,
        datasets: list[str],
        kubeconfig: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create ConfigMap with OpenCompass configuration.

        Args:
            eval_request_id: Unique evaluation request ID
            model_name: Model name
            api_key: API key
            base_url: API base URL
            datasets: List of datasets to evaluate
            kubeconfig: Optional kubeconfig content
            **kwargs: Additional configuration parameters

        Returns:
            Dict with ConfigMap creation details
        """
        try:
            k8s_client = self._get_k8s_client(kubeconfig)

            # Generate configuration content
            bud_model_content = OpenCompassConfigGenerator.generate_bud_model_config(
                model_name=model_name, api_key=api_key, base_url=base_url, eval_request_id=eval_request_id, **kwargs
            )

            dataset_content = OpenCompassConfigGenerator.generate_dataset_config(datasets)

            # Create simple, self-contained evaluation config with proper dataset imports
            dataset_imports = []
            dataset_list = []

            # Map dataset names to their OpenCompass imports - use simpler approach
            # TODO: need to remove this as datasets , should be passed as args
            dataset_mapping = {
                "mmlu": ("from opencompass.datasets.mmlu import mmlu_datasets", "mmlu_datasets"),
                "gsm8k": ("from opencompass.datasets.gsm8k import gsm8k_datasets", "gsm8k_datasets"),
                "hellaswag": ("from opencompass.datasets.hellaswag import hellaswag_datasets", "hellaswag_datasets"),
                "arc": ("from opencompass.datasets.ARC_c import ARC_c_datasets", "ARC_c_datasets"),
                "winogrande": (
                    "from opencompass.datasets.winogrande import winogrande_datasets",
                    "winogrande_datasets",
                ),
            }

            for dataset in datasets:
                dataset_name = dataset.lower()
                if dataset_name in dataset_mapping:
                    import_stmt, var_name = dataset_mapping[dataset_name]
                    dataset_imports.append(import_stmt)
                    dataset_list.append(var_name)

            # Default to MMLU if no valid datasets found
            if not dataset_imports:
                dataset_imports = ["from opencompass.datasets import mmlu_datasets"]
                dataset_list = ["mmlu_datasets"]

            "\n".join(dataset_imports)
            # For simplicity, just use the first dataset to avoid LazyObject concatenation issues
            dataset_list[0]

            eval_config_content = f"""# Complete evaluation configuration for {eval_request_id}
from opencompass.models import OpenAI

# Model configuration
models = [
    dict(
        abbr='{model_name}',
        type=OpenAI,
        path='{model_name}',
        key='{api_key}',
        query_per_second=1,
        max_out_len=2048,
        max_seq_len=4096,
        openai_api_base='{base_url}',
        batch_size=8,
        temperature=0.0,
        run_cfg=dict(num_gpus=0),
        retry=3,
    ),
]

# Use string dataset names - OpenCompass will resolve them
datasets = ['mmlu_gen']

# Configuration metadata
eval_request_id = '{eval_request_id}'
work_dir = '/workspace/outputs'
"""

            # ConfigMap name
            configmap_name = f"opencompass-config-{eval_request_id.lower()}"

            # Create ConfigMap object
            configmap = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(
                    name=configmap_name,
                    namespace=self.namespace,
                    labels={
                        "app": "budeval",
                        "component": "opencompass-config",
                        "eval-request-id": eval_request_id.lower(),
                        "model": model_name.lower().replace("/", "-").replace("_", "-"),
                    },
                ),
                data={
                    "bud-model.py": bud_model_content,
                    "bud-datasets.py": dataset_content,  # TODO: this won't work , importing datasets
                    "eval_config.py": eval_config_content,
                    "metadata.json": json.dumps(
                        {
                            "eval_request_id": eval_request_id,
                            "model_name": model_name,
                            "api_key_hash": hash(api_key),  # Store hash for verification
                            "base_url": base_url,
                            "datasets": datasets,
                            "created_at": f"{__import__('datetime').datetime.utcnow().isoformat()}Z",
                        },
                        indent=2,
                    ),
                },
            )

            # Create or update ConfigMap
            try:
                # Try to create new ConfigMap
                k8s_client.create_namespaced_config_map(namespace=self.namespace, body=configmap)
                logger.info(f"Created ConfigMap {configmap_name} in namespace {self.namespace}")
                action = "created"
            except ApiException as e:
                if e.status == 409:  # Already exists
                    # Update existing ConfigMap
                    k8s_client.patch_namespaced_config_map(
                        name=configmap_name, namespace=self.namespace, body=configmap
                    )
                    logger.info(f"Updated existing ConfigMap {configmap_name} in namespace {self.namespace}")
                    action = "updated"
                else:
                    raise

            return {
                "configmap_name": configmap_name,
                "namespace": self.namespace,
                "action": action,
                "files": list(configmap.data.keys()),
                "metadata": {
                    "eval_request_id": eval_request_id,
                    "model_name": model_name,
                    "base_url": base_url,
                    "datasets": datasets,
                },
            }

        except Exception as e:
            logger.error(f"Failed to create ConfigMap for eval request {eval_request_id}: {e}")
            raise

    def create_generic_config_map(
        self,
        eval_request_id: str,
        engine: str,
        config_files: Dict[str, str],
        kubeconfig: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create ConfigMap with engine-specific configuration files.

        Args:
            eval_request_id: Unique evaluation request ID
            engine: Engine name (e.g., 'opencompass', 'deepeval')
            config_files: Dictionary mapping filename to file content
            kubeconfig: Optional kubeconfig content
            **kwargs: Additional metadata

        Returns:
            Dict with ConfigMap creation details
        """
        try:
            k8s_client = self._get_k8s_client(kubeconfig)

            # ConfigMap name format: {engine}-config-{eval_request_id}
            configmap_name = f"{engine.lower()}-config-{eval_request_id.lower()}"

            # Create ConfigMap object
            configmap = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name=configmap_name,
                    namespace=self.namespace,
                    labels={
                        "app": "budeval",
                        "type": "evaluation-config",
                        "engine": engine.lower(),
                        "eval-request-id": eval_request_id.lower(),
                    },
                ),
                data=config_files,
            )

            # Create or update ConfigMap
            try:
                # Try to create new ConfigMap
                k8s_client.create_namespaced_config_map(namespace=self.namespace, body=configmap)
                logger.info(f"Created ConfigMap {configmap_name} in namespace {self.namespace}")
                action = "created"
            except ApiException as e:
                if e.status == 409:  # Already exists
                    # Update existing ConfigMap
                    k8s_client.patch_namespaced_config_map(
                        name=configmap_name, namespace=self.namespace, body=configmap
                    )
                    logger.info(f"Updated existing ConfigMap {configmap_name} in namespace {self.namespace}")
                    action = "updated"
                else:
                    raise

            return {
                "configmap_name": configmap_name,
                "namespace": self.namespace,
                "action": action,
                "files": list(configmap.data.keys()),
                "engine": engine,
                "metadata": {
                    "eval_request_id": eval_request_id,
                    "engine": engine,
                    **kwargs,
                },
            }

        except Exception as e:
            logger.error(f"Failed to create ConfigMap for eval request {eval_request_id}: {e}")
            raise

    def delete_opencompass_config_map(self, eval_request_id: str, kubeconfig: Optional[str] = None) -> bool:
        """Delete ConfigMap for an evaluation request.

        Args:
            eval_request_id: Evaluation request ID
            kubeconfig: Optional kubeconfig content

        Returns:
            bool: True if deleted successfully
        """
        try:
            k8s_client = self._get_k8s_client(kubeconfig)
            configmap_name = f"opencompass-config-{eval_request_id.lower()}"

            k8s_client.delete_namespaced_config_map(name=configmap_name, namespace=self.namespace)

            logger.info(f"Deleted ConfigMap {configmap_name} from namespace {self.namespace}")
            return True

        except ApiException as e:
            if e.status == 404:
                logger.warning(f"ConfigMap for eval request {eval_request_id} not found")
                return True  # Already deleted
            else:
                logger.error(f"Failed to delete ConfigMap: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete ConfigMap for eval request {eval_request_id}: {e}")
            return False

    def get_configmap_info(self, eval_request_id: str, kubeconfig: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get information about a ConfigMap.

        Args:
            eval_request_id: Evaluation request ID
            kubeconfig: Optional kubeconfig content

        Returns:
            Dict with ConfigMap info or None if not found
        """
        try:
            k8s_client = self._get_k8s_client(kubeconfig)
            configmap_name = f"opencompass-config-{eval_request_id.lower()}"

            configmap = k8s_client.read_namespaced_config_map(name=configmap_name, namespace=self.namespace)

            metadata_json = configmap.data.get("metadata.json", "{}")
            metadata = json.loads(metadata_json)

            return {
                "name": configmap.metadata.name,
                "namespace": configmap.metadata.namespace,
                "created": configmap.metadata.creation_timestamp.isoformat(),
                "labels": configmap.metadata.labels,
                "files": list(configmap.data.keys()),
                "metadata": metadata,
            }

        except ApiException as e:
            if e.status == 404:
                return None
            else:
                logger.error(f"Failed to get ConfigMap info: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to get ConfigMap info for eval request {eval_request_id}: {e}")
            raise

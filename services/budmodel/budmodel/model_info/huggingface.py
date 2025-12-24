import json
import math
import os
import re
import struct
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import arxiv
import requests
from budmicroframe.commons import logging
from budmicroframe.shared.dapr_service import DaprService
from git import Repo
from huggingface_hub import (
    HfApi,
    HfFileSystem,
    ModelCard,
    auth_check,
    get_hf_file_metadata,
    hf_hub_download,
    hf_hub_url,
    snapshot_download,
)
from huggingface_hub import errors as hf_hub_errors
from lxml import html as lxml_html
from transformers import AutoConfig

from ..commons.config import app_settings
from ..commons.constants import LOCAL_MIN_SIZE_GB, ModelDownloadStatus
from ..commons.helpers import safe_delete
from .base import BaseModelInfo
from .download_history import DownloadHistory
from .exceptions import HubDownloadException, RepoAccessException, SpaceNotAvailableException
from .huggingface_aria2 import HuggingFaceAria2Downloader
from .license import HuggingFaceLicenseExtractor
from .parser import (
    extract_model_card_details,
    get_hf_repo_readme,
    get_model_analysis,
)
from .schemas import (
    AudioConfig,
    EmbeddingConfig,
    LicenseInfo,
    LLMConfig,
    ModelArchitecture,
    ModelDerivatives,
    ModelInfo,
    PaperInfo,
    VisionConfig,
)


logger = logging.get_logger(__name__)


class HuggingFaceModelInfo(BaseModelInfo):
    @classmethod
    def from_pretrained(
        cls, pretrained_model_name_or_path: str, token: Optional[str] = None
    ) -> Tuple[ModelInfo, List[Dict]]:
        """Load a model from Hugging Face Hub."""
        hf_repo_readme = get_hf_repo_readme(pretrained_model_name_or_path, token)

        # Try to get LLM-based model analysis, but continue without it if it fails
        try:
            model_analysis = get_model_analysis(hf_repo_readme)
        except Exception as e:
            logger.warning(
                "LLM-based model analysis failed for %s: %s. Continuing with basic extraction.",
                pretrained_model_name_or_path,
                str(e),
            )
            model_analysis = {}

        # Handle missing README.md gracefully
        model_card = None
        try:
            model_card = ModelCard.load(
                pretrained_model_name_or_path,
                token=token,
            )
        except hf_hub_errors.EntryNotFoundError as e:
            logger.warning(
                "README.md not found for %s, creating minimal ModelCard: %s", pretrained_model_name_or_path, str(e)
            )
        except Exception as e:
            logger.error("Failed to load ModelCard for %s: %s", pretrained_model_name_or_path, str(e))

        if model_card is None:
            # Create a minimal ModelCard if loading failed
            model_card = ModelCard("")

        language = model_card.data.get("language") or []

        if language and not isinstance(language, list):
            language = [language]

        tasks = model_card.data.get("pipeline_tag") or []
        if tasks and not isinstance(tasks, list):
            tasks = [tasks]

        hf_license_extractor = HuggingFaceLicenseExtractor()
        license_details = hf_license_extractor.extract_license(pretrained_model_name_or_path, token)
        try:
            url_details = extract_model_card_details(model_card.content, model=pretrained_model_name_or_path)
        except Exception as e:
            logger.exception("Error getting url details for %s: %s", pretrained_model_name_or_path, e)
            url_details = [None, None]

        # NOTE: commented out perplexity integration
        # try:
        #     # usecase_info = extract_model_card_usecase_info(model_card.content)
        # except Exception as e:
        #     logger.exception("Error getting usecase info for %s: %s", pretrained_model_name_or_path, e)
        #     usecase_info = {}

        # license_faqs = []
        # if license_details["license_url"]:
        #     try:
        #         license_faqs = license_QA(license_details["license_url"])
        #     except Exception as qa_error:
        #         logger.exception(f"Error fetching license FAQs from {license_details['license_url']}: {qa_error}")

        # license_data = {}
        # if license_details["license_url"]:
        #     license_data = generate_license_details(license_details["license_url"])

        hf_author = HuggingfaceUtils.get_hf_logo(pretrained_model_name_or_path, token)

        logger.info(f"hf_author herex: {hf_author}")

        model_tree = cls.get_model_tree(model_card, pretrained_model_name_or_path, token)

        model_info = ModelInfo(
            author=pretrained_model_name_or_path.split("/")[0],
            description=model_analysis.get("description", ""),
            uri=pretrained_model_name_or_path,
            modality="",
            tags=model_card.data.get("tags", []),
            tasks=tasks,
            papers=cls.get_publication_info(model_card.content),
            github_url=url_details[0],
            provider_url=f"https://huggingface.co/{pretrained_model_name_or_path}",
            website_url=url_details[1],
            license=LicenseInfo(
                id=license_details.id,
                license_id=license_details.license_id,
                name=license_details.name,
                url=license_details.url,
                faqs=license_details.faqs,
                type=license_details.type,
                description=license_details.description,
                suitability=license_details.suitability,
            )
            if license_details
            else None,
            logo_url=hf_author,
            # NOTE: commented out perplexity integration
            # use_cases=usecase_info.get("usecases", []),
            # strengths=usecase_info.get("strengths", []),
            # limitations=usecase_info.get("limitations", []),
            use_cases=model_analysis.get("usecases", []),
            strengths=model_analysis.get("advantages", []),
            limitations=model_analysis.get("disadvantages", []),
            model_tree=model_tree,
            languages=language,
            architecture=None,
        )

        model_architecture = cls.get_model_architecture(pretrained_model_name_or_path, token)
        if model_architecture:
            model_info.architecture = ModelArchitecture.model_validate(model_architecture["architecture"])
            model_info.modality = model_architecture["modality"]

        if model_tree.is_adapter and not model_info.modality:
            base_architecture = cls.get_model_architecture(model_tree.base_model[0], token)
            model_info.modality = base_architecture["modality"]
        model_evals = model_analysis.get("evals", [])
        return model_info, model_evals

    @staticmethod
    def get_model_tree(
        model_card: str, pretrained_model_name_or_path: str, token: Optional[str] = None
    ) -> ModelDerivatives:
        """Get the model tree for a Hugging Face model."""
        base_model = model_card.data.get("base_model") or None
        if base_model and not isinstance(base_model, list):
            base_model = [base_model]

        model_tree = ModelDerivatives(base_model=base_model)

        base_model_relation = model_card.data.get("base_model_relation")
        if base_model_relation:
            relation_map = {
                "adapter": "is_adapter",
                "finetune": "is_finetune",
                "merge": "is_merge",
                "quantized": "is_quantization",
            }
            if relation_map.get(base_model_relation):
                setattr(model_tree, relation_map[base_model_relation], True)
                return model_tree

        try:
            hf_fs = HfFileSystem(token=token)

            if any(
                hf_fs.glob(f"{pretrained_model_name_or_path}/{pattern}")
                for pattern in ["quantize_config.json", "**/*.gguf"]
            ):
                model_tree.is_quantization = True
            elif hf_fs.glob(f"{pretrained_model_name_or_path}/adapter_config.json"):
                model_tree.is_adapter = True
            elif (base_model and len(base_model) > 1) or hf_fs.glob(
                f"{pretrained_model_name_or_path}/mergekit_config.yml"
            ):
                model_tree.is_merge = True
            else:
                model_tree.is_finetune = True
        except Exception as e:
            logger.exception("Error getting model tree for %s: %s", pretrained_model_name_or_path, str(e))

        return model_tree

    @staticmethod
    def download_hf_repo_file(pretrained_model_name_or_path, filename, token):
        """Download a specific file from HuggingFace repository."""
        try:
            return hf_hub_download(pretrained_model_name_or_path, filename=filename, token=token)
        except hf_hub_errors.GatedRepoError as e:
            logger.exception("Gated repo for %s: %s", pretrained_model_name_or_path, e)
        except hf_hub_errors.EntryNotFoundError as e:
            logger.warning("Config file %s not found for %s: %s", filename, pretrained_model_name_or_path, e)
        except Exception as e:
            logger.exception(
                "Failed to download config file %s for %s: %s", filename, pretrained_model_name_or_path, e
            )

        return None

    @classmethod
    def get_model_architecture(
        cls, pretrained_model_name_or_path: str, token: Optional[str] = None
    ) -> Optional[ModelArchitecture]:
        """Get the architecture of a Hugging Face model."""
        config_parser = {
            "transformers": ("config.json", cls.parse_transformers_config),
        }
        for config_filename, parser in config_parser.values():
            filepath = cls.download_hf_repo_file(pretrained_model_name_or_path, filename=config_filename, token=token)
            if filepath is not None:
                return parser(pretrained_model_name_or_path, token)

    @classmethod
    def parse_transformers_config(
        cls, pretrained_model_name_or_path: str, token: Optional[str] = None
    ) -> Optional[ModelArchitecture]:
        """Parse the transformers configuration for a Hugging Face model.

        Detects model modality based on config patterns:
        - LLM: Text-only language models
        - MLLM: Multi-modal models (text + image)
        - Audio: Speech-to-text models (e.g., Whisper)
        - Audio LLM: Audio input + text output models (e.g., Qwen2-Audio)
        - Omni: Full multimodal (audio + vision + text, with optional audio output)

        Modality suffixes:
        - _embedding: Model has embedding capability
        - _tts: Model has text-to-speech output capability
        """
        from transformers import AutoConfig

        model_config = AutoConfig.from_pretrained(pretrained_model_name_or_path, token=token, trust_remote_code=True)

        config = model_config.to_dict()
        # check if model_type is present in config
        model_family = config.get("model_type")
        if not model_family:
            raise ValueError("Model family (model_type) cannot be null or empty.")
        model_architecture = ModelArchitecture(
            type="transformers",
            family=model_family,
            **cls.get_llm_model_weights_info(pretrained_model_name_or_path, model_config),
        )

        # Detect audio capabilities
        has_audio_input, has_audio_output = cls.detect_audio_modality(config)

        # Detect vision capabilities
        has_vision = bool(config.get("vision_config"))

        # Also check for vision in nested configs (Qwen2.5-Omni style)
        if not has_vision:
            thinker_config = config.get("thinker_config", {})
            has_vision = bool(thinker_config.get("vision_config"))

        # Determine base modality
        if has_audio_input and has_vision:
            # Omni model: audio + vision + text (e.g., Qwen2.5-Omni, MiniCPM-o)
            config_info = cls.parse_mllm_model_config(config)
            model_architecture.text_config = config_info.get("text_config")
            model_architecture.vision_config = config_info.get("vision_config")
            model_architecture.audio_config = cls.parse_audio_model_config(config)
            modality = "omni"
        elif has_audio_input:
            # Audio model: may be pure audio (Whisper) or audio+text LLM (Qwen2-Audio)
            model_architecture.audio_config = cls.parse_audio_model_config(config)

            # Check if it's a pure speech model or audio-LLM hybrid
            # Pure speech models (Whisper) typically have is_encoder_decoder=True
            # and no separate text_config
            is_pure_speech = config.get("is_encoder_decoder", False) and not config.get("text_config")

            if is_pure_speech:
                modality = "speech_to_text"
            else:
                # Audio-LLM hybrid (Qwen2-Audio, Ultravox, etc.)
                model_architecture.text_config = cls.parse_llm_model_config(config)
                modality = "audio_llm"
        elif has_vision:
            # Multi-modal LLM with vision
            config_info = cls.parse_mllm_model_config(config)
            model_architecture.text_config = config_info.get("text_config")
            model_architecture.vision_config = config_info.get("vision_config")
            modality = "mllm"
        else:
            # Standard LLM
            model_architecture.text_config = cls.parse_llm_model_config(config)
            modality = "llm"

        # Check for embedding capability
        filepath = cls.download_hf_repo_file(
            pretrained_model_name_or_path, filename="1_Pooling/config.json", token=token
        )
        if filepath is not None:
            with open(filepath, "r") as fp:
                pooling_config = json.load(fp)

            model_architecture.embedding_config = cls.parse_embedding_model_config(pooling_config)
            modality += "_embedding"

        # Add TTS suffix if model has audio output capability
        if has_audio_output:
            modality += "_tts"

        return {"architecture": model_architecture, "modality": modality}

    @staticmethod
    def parse_llm_model_config(config: Dict[str, Any]) -> LLMConfig:
        """Parse the LLM model configuration."""
        num_attention_heads = config.get("num_attention_heads") or config.get("num_heads")

        return LLMConfig(
            num_layers=config.get("num_hidden_layers") or config.get("num_layers"),
            hidden_size=config.get("hidden_size") or config.get("d_model"),
            intermediate_size=config.get("intermediate_size") or config.get("d_ff"),
            context_length=config.get("max_position_embeddings") or config.get("n_positions"),
            vocab_size=config.get("vocab_size"),
            torch_dtype=config.get("torch_dtype"),
            num_attention_heads=num_attention_heads,
            num_key_value_heads=config.get("num_key_value_heads") or num_attention_heads,
            rope_scaling=config.get("rope_scaling"),
        )

    @staticmethod
    def parse_mllm_model_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the LLM model configuration."""
        text_config_model = LLMConfig()
        vision_config_model = VisionConfig()

        _text_config = config.get("text_config", {}) or config

        num_attention_heads = _text_config.get("num_attention_heads") or _text_config.get("num_heads")
        text_config_model.num_layers = _text_config.get("num_hidden_layers") or _text_config.get("num_layers")
        text_config_model.hidden_size = _text_config.get("hidden_size") or _text_config.get("d_model")
        text_config_model.intermediate_size = _text_config.get("intermediate_size") or _text_config.get("d_ff")
        text_config_model.context_length = _text_config.get("max_position_embeddings") or _text_config.get(
            "n_positions"
        )
        text_config_model.vocab_size = _text_config.get("vocab_size")
        torch_dtype = _text_config.get("torch_dtype")
        if torch_dtype is not None and not isinstance(torch_dtype, str):
            torch_dtype = str(torch_dtype)
        text_config_model.torch_dtype = torch_dtype
        text_config_model.num_attention_heads = num_attention_heads
        text_config_model.num_key_value_heads = _text_config.get("num_key_value_heads") or num_attention_heads
        text_config_model.rope_scaling = _text_config.get("rope_scaling")

        if "vision_config" in config:
            _vision_config = config.get("vision_config", {})
            vision_config_model.num_layers = _vision_config.get("num_hidden_layers") or _vision_config.get(
                "num_layers"
            )
            vision_config_model.hidden_size = _vision_config.get("hidden_size") or _vision_config.get("d_model")
            vision_config_model.intermediate_size = _vision_config.get("intermediate_size") or _vision_config.get(
                "d_ff"
            )
            vision_config_model.torch_dtype = _vision_config.get("torch_dtype")

        return {"text_config": text_config_model, "vision_config": vision_config_model}

    @staticmethod
    def parse_embedding_model_config(pooling_config: Dict[str, Any]) -> Dict[str, Any]:
        """Parse embedding model configuration from pooling config."""
        return EmbeddingConfig(embedding_dimension=pooling_config.get("word_embedding_dimension"))

    @staticmethod
    def detect_audio_modality(config: Dict[str, Any]) -> Tuple[bool, bool]:
        """Detect audio input and output support from model config.

        Analyzes model configuration to identify audio capabilities based on
        various config patterns found in audio-capable models like Whisper,
        Qwen2-Audio, Ultravox, Voxtral, etc.

        Args:
            config: Model configuration dictionary

        Returns:
            Tuple of (audio_input_supported, audio_output_supported)
        """
        audio_input = False
        audio_output = False

        # Check for audio input indicators
        # Pattern 1: audio_config (Qwen2-Audio, Ultravox, MiniCPM-o, AudioFlamingo3, Voxtral)
        if config.get("audio_config"):
            audio_input = True

        # Pattern 2: audio_encoder_config (MiDashengLM)
        if config.get("audio_encoder_config"):
            audio_input = True

        # Pattern 3: audio_processor (Phi-4-multimodal)
        if config.get("audio_processor"):
            audio_input = True

        # Pattern 4: audio token markers (present in all audio models)
        if config.get("audio_token_index") or config.get("audio_token_id"):
            audio_input = True

        # Pattern 5: Check encoder_config for speech/audio model types (Granite Speech)
        encoder_config = config.get("encoder_config", {})
        encoder_type = encoder_config.get("model_type", "").lower()
        if "speech" in encoder_type or "audio" in encoder_type:
            audio_input = True

        # Pattern 6: Check model_type for audio keywords
        model_type = config.get("model_type", "").lower()
        audio_model_types = ["whisper", "audio", "speech", "voxtral", "omni"]
        if any(kw in model_type for kw in audio_model_types):
            audio_input = True

        # Pattern 7: Check architectures for audio keywords
        for arch in config.get("architectures", []):
            arch_lower = arch.lower()
            if any(kw in arch_lower for kw in ["whisper", "audio", "speech", "voxtral", "omni"]):
                audio_input = True
                break

        # Pattern 8: Check nested thinker_config for audio (Qwen2.5-Omni style)
        thinker_config = config.get("thinker_config", {})
        if thinker_config.get("audio_config"):
            audio_input = True

        # Check for audio output (TTS) capability
        # Pattern 1: tts_config (MiniCPM-o, Qwen2.5-Omni)
        if config.get("tts_config"):
            audio_output = True

        # Pattern 2: enable_audio_output flag (Qwen2.5-Omni)
        if config.get("enable_audio_output"):
            audio_output = True

        # Pattern 3: token2wav_config (Qwen2.5-Omni vocoder)
        if config.get("token2wav_config"):
            audio_output = True

        # Pattern 4: talker_config (Qwen2.5-Omni)
        if config.get("talker_config"):
            audio_output = True

        return audio_input, audio_output

    @classmethod
    def parse_audio_model_config(cls, config: Dict[str, Any]) -> AudioConfig:
        """Parse audio model configuration from various config patterns.

        Handles different audio config patterns found in models like:
        - Whisper: root-level audio fields
        - Qwen2-Audio: audio_config object
        - Ultravox: audio_config with whisper-style nested config
        - Granite Speech: encoder_config
        - Phi-4: audio_processor
        - MiDashengLM: audio_encoder_config

        Args:
            config: Model configuration dictionary

        Returns:
            AudioConfig with extracted audio parameters
        """
        audio_config = AudioConfig()

        # Try to get audio config from various sources
        _audio_config: Dict[str, Any] = {}

        # Priority 1: audio_config (most common)
        if config.get("audio_config"):
            _audio_config = config["audio_config"]
        # Priority 2: audio_encoder_config (MiDashengLM)
        elif config.get("audio_encoder_config"):
            _audio_config = config["audio_encoder_config"]
        # Priority 3: encoder_config (Granite Speech)
        elif config.get("encoder_config"):
            encoder = config["encoder_config"]
            if "speech" in encoder.get("model_type", "").lower() or "audio" in encoder.get("model_type", "").lower():
                _audio_config = encoder
        # Priority 4: audio_processor config (Phi-4)
        elif config.get("audio_processor"):
            processor = config["audio_processor"]
            if isinstance(processor, dict) and processor.get("config"):
                _audio_config = processor["config"]
        # Priority 5: thinker_config.audio_config (Qwen2.5-Omni)
        elif config.get("thinker_config", {}).get("audio_config"):
            _audio_config = config["thinker_config"]["audio_config"]
        # Priority 6: Root level for Whisper-style models
        elif config.get("model_type", "").lower() == "whisper":
            _audio_config = config

        # Extract common audio parameters
        audio_config.num_layers = (
            _audio_config.get("encoder_layers")
            or _audio_config.get("num_hidden_layers")
            or _audio_config.get("num_layers")
            or _audio_config.get("depth")
        )

        audio_config.hidden_size = (
            _audio_config.get("hidden_size")
            or _audio_config.get("d_model")
            or _audio_config.get("embed_dim")
            or _audio_config.get("attention_dim")
        )

        audio_config.num_attention_heads = (
            _audio_config.get("encoder_attention_heads")
            or _audio_config.get("num_attention_heads")
            or _audio_config.get("num_heads")
            or _audio_config.get("attention_heads")
        )

        audio_config.num_mel_bins = _audio_config.get("num_mel_bins") or _audio_config.get("n_mels")

        audio_config.sample_rate = _audio_config.get("sample_rate")

        audio_config.max_source_positions = _audio_config.get("max_source_positions")

        torch_dtype = _audio_config.get("torch_dtype")
        if torch_dtype is not None and not isinstance(torch_dtype, str):
            torch_dtype = str(torch_dtype)
        audio_config.torch_dtype = torch_dtype

        return audio_config

    @staticmethod
    def get_llm_model_weights_info(pretrained_model_name_or_path: str, config: AutoConfig) -> Dict[str, Any]:
        """Get llm model weights info."""
        from llm_benchmark.hardware.constants import DeviceInfo
        from llm_benchmark.model import analysis as llm_analysis

        # from transformers import AutoModel  # TODO: Uncomment this when memory issue is fixed

        weights_info = {"num_params": None, "model_weights_size": None, "kv_cache_size": None}
        # model = AutoModel.from_config(config) # TODO: Uncomment this when memory issue is fixed

        try:
            gpu_info = DeviceInfo.NVIDIA_A100_80GB_PCIE.value
            device_config_dict = {
                "name": gpu_info.name,
                "mem_per_GPU_in_GB": gpu_info.mem_per_GPU_in_GB,
                "hbm_bandwidth_in_GB_per_sec": gpu_info.hbm_bandwidth_in_GB_per_sec,
                "intra_node_bandwidth_in_GB_per_sec": gpu_info.intra_node_bandwidth_in_GB_per_sec,
                "intra_node_min_message_latency": gpu_info.intra_node_min_message_latency,
                "peak_fp16_TFLOPS": gpu_info.peak_fp16_TFLOPS,
                "peak_i8_TFLOPS": gpu_info.peak_i8_TFLOPS,
                "peak_i4_TFLOPS": gpu_info.peak_i4_TFLOPS,
                "inter_node_bandwidth_in_GB_per_sec": gpu_info.inter_node_bandwidth_in_GB_per_sec,
                "available_count": 1,
            }
            analysis_report = llm_analysis.infer(
                model_name=pretrained_model_name_or_path,
                device_config=device_config_dict,
            )
        except Exception as e:
            logger.exception("Failed to get model weights info for %s: %s", pretrained_model_name_or_path, e)
            return weights_info

        total_num_params = ComputeModelParams(pretrained_model_name_or_path).calculate_total_params()
        if total_num_params != 0:
            weights_info["num_params"] = total_num_params
        else:
            weights_info["num_params"] = analysis_report.get("num_active_params_total")

        weights_info["model_weights_size"] = analysis_report.get("weight_memory_per_gpu")
        weights_info["kv_cache_size"] = analysis_report.get("kv_cache_memory_per_gpu")

        return weights_info

    @staticmethod
    def get_publication_info(model_card: str) -> List[PaperInfo]:
        """Get publication info."""
        papers = []
        pattern = (
            r"(?i)arxiv:\s*(\d{4}\.\d{5}(?:v\d+)?)|https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{5}(?:v\d+)?)"
            r"|https?://huggingface\.co/papers/(\d{4}\.\d{5})"
        )
        try:
            matches = re.findall(pattern, model_card)
            if not matches:
                return []
            ids = [m[0] or m[1] or m[2] for m in matches]
            search = arxiv.Search(id_list=ids)
            for res in search.results():
                papers.append(PaperInfo(title=res.title, authors=[str(a) for a in res.authors], url=res.entry_id))
        except Exception as e:
            logger.error("Error getting papers: %s", e)
        return papers

    @staticmethod
    def get_github_url(model_card: str) -> Optional[str]:
        """Get github url."""
        pattern = r"https?://(?:www\.)?github\.com/[^\s,)]*(?=[\s,)]|$)"
        try:
            matches = re.findall(pattern, model_card)
            return matches[0] if matches else None
        except Exception as e:
            logger.error("Error getting GitHub URL: %s", e)
            return None

    @staticmethod
    def download_from_hf_hub(model_name_or_path: str, rel_dir: str = None, hf_token: str = None):
        """Download model from huggingface hub."""
        assert model_name_or_path, "Model name or path is required and cannot be empty."
        local_dir = os.path.join(app_settings.model_download_dir, rel_dir) if rel_dir else app_settings.hf_home_dir
        os.makedirs(local_dir, exist_ok=True)

        try:
            org, model_name = model_name_or_path.split("/")
        except ValueError as e:
            logger.exception("Invalid model path format. Expected format: 'organization/model_name'")
            raise ValueError("Model name must be in the format 'organization/model_name'.") from e

        logger.debug(f"Downloading model {model_name_or_path} to: {local_dir}")

        # Commented out since download name is managed by budserve and it is specific to the user
        # try:
        #     if os.path.exists(download_path) and os.path.isdir(download_path):
        #         logger.debug("Model found locally at: %s", download_path)
        #         return download_path
        # except Exception as e:
        #     logger.warning("Local model check failed for %s: %s", model_name_or_path, e)

        try:
            # Calculate free space
            free_space = DownloadHistory.get_available_space()
            model_size = HuggingfaceUtils.get_hf_model_size(model_name_or_path, hf_token)
            logger.debug(f"Space details - Free: {free_space}, Model Size: {model_size}")
            if model_size > free_space:
                raise SpaceNotAvailableException(f"Space not available to download {model_name_or_path}")
        except SpaceNotAvailableException as e:
            logger.error(str(e))
            raise e
        except Exception as e:
            logger.error("Unexpected error during size calculation: %s", e)
            raise e

        try:
            # Create a new download record with `running` status
            download_record = DownloadHistory.create_download_history(rel_dir, model_size)
            # Download the model
            model_path = snapshot_download(repo_id=model_name_or_path, token=hf_token, local_dir=local_dir)
            logger.debug("Model downloaded to: %s", model_path)

            # Update the record to `completed` and set the path
            DownloadHistory.update_download_status(rel_dir, ModelDownloadStatus.COMPLETED)
            return model_path
        except hf_hub_errors.GatedRepoError as e:
            logger.error("Access denied to gated repo %s:", model_name_or_path)
            if download_record:
                safe_delete(local_dir)
                DownloadHistory.delete_download_history(rel_dir)
            raise HubDownloadException(f"Access denied to gated repo: {model_name_or_path}") from e
        except hf_hub_errors.RepositoryNotFoundError as e:
            logger.error("Repository not found or access issue for %s:", model_name_or_path)
            if download_record:
                safe_delete(local_dir)
                DownloadHistory.delete_download_history(rel_dir)
            raise HubDownloadException(f"Repository not found: {model_name_or_path}") from e
        except Exception as e:
            logger.exception("Unexpected error during model download: %s", e)
            if download_record:
                safe_delete(local_dir)
                DownloadHistory.delete_download_history(rel_dir)
            raise HubDownloadException(f"Error during snapshot download: {e}") from e

    def list_repository_files(self, model_name: str, token: Optional[str] = None) -> Tuple[List[Dict], int]:
        """List all files in a Hugging Face repository with their sizes.

        Args:
            model_name (str): The name of the Hugging Face model
            token (Optional[str]): The Hugging Face token

        Returns:
            List[Dict]: List of dictionaries containing file information
        """
        try:
            api = HfApi()
            model_info = api.model_info(model_name, token=token, files_metadata=True)

            # Get file information
            file_info = []
            total_size = 0

            # Process each file
            for index, sibling in enumerate(model_info.siblings, 1):
                size = getattr(sibling, "size", 0) or 0
                path = Path(sibling.rfilename)

                file_info.append(
                    {
                        "index": index,
                        "filename": path.name,
                        "path": str(path.parent),
                        "size_bytes": size,
                    }
                )

                total_size += size

            return file_info, total_size
        except Exception as e:
            logger.error("Error listing repository files: %s", e)
            return [], 0

    @staticmethod
    def get_file_size(model_name: str, filename: str, token: Optional[str] = None) -> int:
        """Get file size in bytes from Hugging Face."""
        try:
            url = hf_hub_url(repo_id=model_name, filename=filename)
            hf_file_metadata = get_hf_file_metadata(url=url, token=token)
            return hf_file_metadata.size
        except Exception as e:
            logger.exception("Error getting file size for %s: %s", filename, e)
            raise e

    def download_repository_files(
        self, model_uri: str, output_dir: str, token: Optional[str] = None, workflow_id: Optional[str] = None
    ) -> None:
        """List and download files individually from a Hugging Face repository.

        Args:
            model_name (str): Name of the Hugging Face model
            output_dir (str): Directory where files should be downloaded
            token (str, optional): Hugging Face API token for private repos
        """
        local_dir = (
            os.path.join(app_settings.model_download_dir, output_dir) if output_dir else app_settings.hf_home_dir
        )
        os.makedirs(local_dir, exist_ok=True)

        try:
            org, model_name = model_uri.split("/")
        except ValueError as e:
            logger.exception("Invalid model path format. Expected format: 'organization/model_name'")
            raise ValueError("Model name must be in the format 'organization/model_name'.") from e
        logger.debug("Downloading model %s to: %s", model_uri, local_dir)

        try:
            # Calculate model size
            model_size = HuggingfaceUtils.get_hf_model_size(model_uri, token)
            logger.debug("Model size: %s bytes", model_size)
        except Exception as e:
            logger.error("Unexpected error during size calculation: %s", e)
            raise e

        download_record_created = False
        try:
            # List files in the repository first to validate access
            files, total_size = self.list_repository_files(model_uri, token)
            logger.debug("Found %s files in the repository with total size %s", len(files), total_size)

            if not files:
                raise HubDownloadException("No files found in repository: %s", model_uri)

            # Atomically check and reserve space for the download
            try:
                DownloadHistory.atomic_space_reservation(output_dir, model_size)
                download_record_created = True
            except SpaceNotAvailableException as e:
                logger.error("Space reservation failed: %s", str(e))
                raise e

            # Download each file - use aria2 if enabled
            if app_settings.use_aria2_for_huggingface:
                try:
                    self._download_files_with_aria2(files, model_uri, local_dir, token, workflow_id)
                except Exception as aria2_error:
                    logger.warning("Aria2 download failed, falling back to standard download: %s", str(aria2_error))
                    # Fall back to standard download
                    self._download_files_standard(files, model_uri, local_dir, token, workflow_id, output_dir)
            else:
                # Standard download method
                self._download_files_standard(files, model_uri, local_dir, token, workflow_id, output_dir)

            # Update the record to `completed` only after all files are downloaded
            DownloadHistory.update_download_status(output_dir, ModelDownloadStatus.COMPLETED)
            logger.debug("Model downloaded successfully to: %s", local_dir)

            return output_dir
        except hf_hub_errors.GatedRepoError as e:
            logger.error("Access denied to gated repo %s:", model_uri)
            safe_delete(local_dir)
            if download_record_created:
                DownloadHistory.delete_download_history(output_dir)
            raise HubDownloadException(f"Access denied to gated repo: {model_uri}") from e
        except hf_hub_errors.RepositoryNotFoundError as e:
            logger.error("Repository not found or access issue for %s:", model_uri)
            safe_delete(local_dir)
            if download_record_created:
                DownloadHistory.delete_download_history(output_dir)
            raise HubDownloadException(f"Repository not found: {model_uri}") from e
        except Exception as e:
            logger.exception("Unexpected error during model download: %s", e)
            safe_delete(local_dir)
            if download_record_created:
                DownloadHistory.delete_download_history(output_dir)
            raise HubDownloadException(f"Error during snapshot download: {e}") from e

    def _download_files_with_aria2(
        self,
        files: list[dict],
        model_uri: str,
        local_dir: str,
        token: Optional[str],
        workflow_id: Optional[str],
    ) -> None:
        """Download files using aria2 with I/O monitoring.

        Args:
            files: List of file information dictionaries
            model_uri: HuggingFace model URI
            local_dir: Local directory to save files
            token: HuggingFace API token
            workflow_id: Workflow ID for progress tracking
        """
        logger.info("Using aria2 for HuggingFace download with I/O monitoring")

        # Initialize aria2 downloader with config settings
        aria2_downloader = HuggingFaceAria2Downloader(
            enable_io_monitoring=app_settings.enable_io_monitoring,
            io_check_interval=app_settings.io_check_interval,
            min_speed=app_settings.aria2_min_speed,
            max_speed=app_settings.aria2_max_speed,
        )

        # Prepare file list for download
        filenames = []
        for file_info in files:
            filename = (
                os.path.join(file_info["path"], file_info["filename"])
                if file_info["path"] != "."
                else file_info["filename"]
            )
            filenames.append(filename)

        # Download files sequentially with I/O monitoring
        # (could be enhanced for smart parallel downloads later)
        for i, filename in enumerate(filenames, 1):
            logger.info(f"Downloading file {i}/{len(filenames)} via aria2: {filename}")

            # Update workflow progress
            if workflow_id:
                file_info = next(
                    f
                    for f in files
                    if (os.path.join(f["path"], f["filename"]) if f["path"] != "." else f["filename"]) == filename
                )
                self.update_workflow_eta_state_store(workflow_id, i, file_info["size_bytes"], filename, local_dir)

            # Download using aria2
            aria2_downloader.download_file(
                repo_id=model_uri,
                filename=filename,
                local_dir=local_dir,
                token=token,
                workflow_id=workflow_id,
            )

    def _download_files_standard(
        self,
        files: list[dict],
        model_uri: str,
        local_dir: str,
        token: Optional[str],
        workflow_id: Optional[str],
        output_dir: str,
    ) -> None:
        """Download files using standard hf_hub_download.

        Args:
            files: List of file information dictionaries
            model_uri: HuggingFace model URI
            local_dir: Local directory to save files
            token: HuggingFace API token
            workflow_id: Workflow ID for progress tracking
            output_dir: Output directory name for progress tracking
        """
        logger.info("Using standard HuggingFace download method")

        for current_file_count, file_info in enumerate(files, 1):
            filename = (
                os.path.join(file_info["path"], file_info["filename"])
                if file_info["path"] != "."
                else file_info["filename"]
            )
            file_size = file_info["size_bytes"]

            # Update workflow eta in state store
            if workflow_id:
                self.update_workflow_eta_state_store(workflow_id, current_file_count, file_size, filename, output_dir)

            self.download_file(filename, model_uri, local_dir, token)

    @staticmethod
    def download_file(filename: str, model_uri: str, output_dir: str, token: Optional[str] = None) -> str:
        """Download individual file from Hugging Face repository.

        Args:
            filename (str): Name of the file to download
            output_dir (str): Directory where file should be downloaded
            token (str, optional): Hugging Face API token for private repos

        Returns:
            str: Path to the downloaded file
        """
        logger.debug("Downloading file: %s", filename)

        local_path = hf_hub_download(
            repo_id=model_uri,
            filename=filename,
            local_dir=output_dir,
            token=token,
            local_dir_use_symlinks=False,
            force_download=True,
        )
        logger.debug("File downloaded successfully to: %s", local_path)

        return local_path

    @staticmethod
    def update_workflow_eta_state_store(
        workflow_id: str, current_file_count: int, current_file_size: int, current_file_name: str, output_dir: str
    ) -> None:
        """Update the workflow ETA."""
        try:
            # Update state store workflow eta
            state_store_key = f"eta_{workflow_id}"
            eta_ttl = 86400  # 24 hours
            logger.debug("Updating workflow eta in state store: %s", state_store_key)

            dapr_service = DaprService()
            state_store_data = dapr_service.get_state(
                store_name=app_settings.statestore_name,
                key=state_store_key,
            ).json()

            state_store_data["steps_data"]["model_download"]["current_file"] = current_file_count
            state_store_data["steps_data"]["model_download"]["current_file_name"] = current_file_name
            state_store_data["steps_data"]["model_download"]["current_file_size"] = current_file_size
            state_store_data["steps_data"]["model_download"]["output_path"] = output_dir

            # Save state store data
            dapr_service.save_to_statestore(
                store_name=app_settings.statestore_name,
                key=state_store_key,
                value=state_store_data,
                ttl=eta_ttl,
            )

        except Exception as e:
            logger.exception("Error updating workflow eta in state store: %s", e)


class HuggingfaceUtils:
    @staticmethod
    def get_model_size_fallback(model_uri: str) -> Union[float, None]:
        """Retrieve the model size in GB based on the model parameters.

        Parameters:
            model_uri (str): The Hugging Face model URI (e.g., "meta-llama/Llama-3.3-70B-Instruct").

        Returns:
            float: The model size in GB, or None if it cannot be determined.
        """
        api = HfApi()

        # Retrieve model info
        model_info = api.model_info(model_uri)

        # Initialize model size in GB
        model_size_gb = 0

        # Check for safetensors and gguf attributes and calculate size
        if hasattr(model_info, "safetensors") and model_info.safetensors and model_info.safetensors.total:
            model_size_in_billions = model_info.safetensors.total / 1e9
            model_size_gb = (model_size_in_billions * 2) * 1.1
        elif hasattr(model_info, "gguf") and model_info.gguf and model_info.gguf.get("total"):
            model_size_in_billions = model_info.gguf["total"] / 1e9
            model_size_gb = (model_size_in_billions * 2) * 1.1
        else:
            return None

        return model_size_gb

    @staticmethod
    def get_hf_model_size(model_uri: str, token: str) -> float:
        """Calculate the total size of all files in a Hugging Face model repository using GitPython.

        If unable to calculate, fallback to using model metadata.

        Parameters:
            model_uri (str): The Hugging Face model URI (e.g., "intfloat/multilingual-e5-large").
            token (str): The Hugging Face API token for authentication.

        Returns:
            float: The total size of all files in GB.

        Raises:
            ModelSizeNotFoundError: If the model size cannot be determined by both methods.
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                auth_url = f"https://user:{token}@huggingface.co/{model_uri}"
                # Clone the repository without checking out files
                Repo.clone_from(auth_url, temp_dir, no_checkout=True)
                repo = Repo(temp_dir)
                lfs_files = repo.git.lfs("ls-files", "-s")

                # Extract file sizes
                file_sizes = []
                for line in lfs_files.splitlines():
                    match = re.search(r"\((\d+(\.\d+)?)\s*(GB|MB|KB)\)", line)
                    if match:
                        size = float(match.group(1))
                        unit = match.group(3)
                        if unit == "MB":
                            size /= 1024
                        elif unit == "KB":
                            size /= 1024 * 1024
                        file_sizes.append(size)

                return sum(file_sizes)

        except Exception as e:
            logger.debug(f"Primary size calculation failed: {e}. Falling back to metadata...")

            # Use the fallback method
            fallback_size = HuggingfaceUtils.get_model_size_fallback(model_uri)
            if fallback_size is not None:
                return fallback_size

            # Raise custom exception if fallback also fails
            raise Exception(
                f"Unable to determine model size for {model_uri} using both primary and fallback methods."
            ) from e

    @staticmethod
    def has_access_to_repo(repo_id: str, token: Union[str, None] = None, repo_type: Optional[str] = None) -> bool:
        """Check if the user has access to a specific repository on Hugging Face Hub.

        Parameters:
            repo_id (str): The repository to check for access. Format: "user/repo_name".
            token (Union[str, None], optional): User access token. Defaults to None.
            repo_type (str, optional): The type of the repository. Defaults to "model".

        Returns:
            bool: True if access is granted, False otherwise.
        """
        try:
            # Perform the access check
            auth_check(repo_id, repo_type=repo_type, token=token)
            return True  # Access is granted
        except hf_hub_errors.GatedRepoError as e:
            logger.debug(
                f"Gated repository: Access to '{repo_id}' is restricted. Please ensure you have the required permissions."
            )
            raise RepoAccessException("Gated repository: Access denied") from e
        except hf_hub_errors.RepositoryNotFoundError as e:
            logger.debug(
                f"Repository not found: The repository '{repo_id}' does not exist or is private, and you do not have access."
            )
            raise RepoAccessException("repository does not exist or is private") from e
        except Exception as e:
            logger.debug(f"Unable to verify huggingface Repo access: {e}")
            raise RepoAccessException("Unable to verify huggingface Repo access") from e

    @staticmethod
    def analyze_large_files(file_list: List[Dict]) -> Dict[str, int]:
        """Analyze large files in the file list."""
        threshold_bytes = LOCAL_MIN_SIZE_GB * (1024**3)

        # Filter and count files larger than threshold
        large_file_count = sum(1 for file in file_list if file["size_bytes"] >= threshold_bytes)

        # Calculate total size in bytes
        total_size_bytes = sum(file["size_bytes"] for file in file_list if file["size_bytes"] >= threshold_bytes)

        return {"large_file_count": large_file_count, "total_size_bytes": total_size_bytes}

    @staticmethod
    def scrap_hf_logo(hf_url):
        """Scrape HuggingFace logo from the given URL."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        hf_url = "https://huggingface.co/" + hf_url
        try:
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            # Send the HTTP request
            response = requests.get(hf_url, headers=headers, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            # Parse the HTML content
            tree = lxml_html.fromstring(response.content)
            # Try to get the image using the XPath
            xpath_selector = "/html/body/div/main/header/div/div[1]/div[1]/a/img"
            img_elements = tree.xpath(xpath_selector)
            # If XPath didn't work, try the CSS selector
            if not img_elements:
                css_selector = "body > div > main > header > div > div.mb-2.items-center.leading-none.md\\:flex.xl\\:mb-4 > div.relative.mr-4.flex.size-16.flex-none.items-end.justify-start.rounded-lg.max-md\\:mb-1\\.5.sm\\:size-20 > img"
                img_elements = tree.cssselect(css_selector)
            # If we found the image element, get its src attribute
            if img_elements:
                img_url = img_elements[0].get("src")
                # If the URL is relative, make it absolute
                if img_url and img_url.startswith("/"):
                    img_url = f"https://huggingface.co{img_url}"
                return img_url
            else:
                logger.warning("Image element not found with the provided selectors")
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching the page: {e}")
            return None
        except Exception as e:
            logger.warning(f"An unexpected error occurred: {e}")
            return None

    @staticmethod
    def get_org_name(hf_uri: str, token: Optional[str] = None) -> Optional[str]:
        """Extract the organization name from the Hugging Face URI.

        Handles exceptions gracefully.
        """
        api = HfApi(token=token)

        try:
            # Fetch model info
            model_info = api.model_info(hf_uri)
            org_name = model_info.id.split("/")[0]
            return org_name

        except hf_hub_errors.RepositoryNotFoundError:
            logger.warning(f"Model '{hf_uri}' not found.")
            return None

        except hf_hub_errors.GatedRepoError as e:
            logger.warning(f"gated repo Error: {e}")
            return None

        except Exception as e:
            logger.warning(f"Unexpected error: {e}")
            return None

    @staticmethod
    def get_hf_logo(hf_uri: str, token: Optional[str] = None) -> str:
        """Save the HF organization logo locally if not already saved.

        - Checks if the logo is already saved.
        - If not, scrapes and saves it.
        - Returns the local path or None if the logo was not found.
        """
        # from budapp.commons.config import app_settings

        org_name = HuggingfaceUtils.get_org_name(hf_uri, token)

        if org_name is None:
            return ""

        # Scrap the logo if not present
        img_url = HuggingfaceUtils.scrap_hf_logo(org_name)

        if img_url is not None:
            return img_url
        else:
            logger.warning(f"No logo found for: {org_name}")
            return ""


class ComputeModelParams:
    """Class to compute total parameters from SafeTensors metadata (local or Hugging Face)."""

    def __init__(self, model_path: str):
        """Initialize the ComputeModelParams class."""
        self.model_path = model_path
        self.is_local = os.path.exists(model_path)

    def calculate_total_params(self) -> int:
        """Compute total parameters from SafeTensors files."""
        logger.info(f"Starting parameter calculation for: {self.model_path}")

        safetensor_files = self._get_safetensors_files()
        if not safetensor_files:
            logger.warning("No .safetensors files found.")
            return 0

        total_params = 0
        for file_path in safetensor_files:
            logger.info(f"Processing: {file_path}")
            try:
                metadata = self._extract_metadata(file_path)
                param_count = sum(math.prod(info["shape"]) for info in metadata.values() if "shape" in info)
                total_params += param_count
            except Exception as e:
                logger.error(f"Skipping {file_path} due to error: {e}")

        logger.info(f"Total parameters: {total_params}")
        return total_params

    def _get_safetensors_files(self) -> List[str]:
        """Fetch SafeTensors file paths from a local directory or Hugging Face repository."""
        if not self.is_local:
            model_info = HuggingFaceModelInfo()
            try:
                logger.info(f"Fetching SafeTensors from Hugging Face repo: {self.model_path}")
                repo_files, _ = model_info.list_repository_files(self.model_path)

                return [
                    hf_hub_url(self.model_path, file_info["filename"])
                    for file_info in repo_files
                    if file_info["filename"].endswith(".safetensors")
                ]
            except Exception as e:
                logger.error(f"Failed to fetch from Hugging Face: {e}")
                return []
        else:
            if not os.path.isdir(self.model_path):
                logger.error(f"Directory not found: {self.model_path}")
                raise RuntimeError(f"Directory not found: {self.model_path}")
            return [
                os.path.join(self.model_path, f) for f in os.listdir(self.model_path) if f.endswith(".safetensors")
            ]

    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from SafeTensors file (local or remote)."""
        try:
            if file_path.startswith("https://"):
                headers = {"Range": "bytes=0-7"}
                response = requests.get(file_path, headers=headers, timeout=30)
                response.raise_for_status()

                header_size = struct.unpack("<Q", response.content)[0]
                headers = {"Range": f"bytes=8-{7 + header_size}"}
                response = requests.get(file_path, headers=headers, timeout=30)
                response.raise_for_status()

                return response.json()
            else:
                with open(file_path, "rb") as f:
                    header_size = struct.unpack("<Q", f.read(8))[0]
                    metadata = json.loads(f.read(header_size).decode("utf-8"))
                    return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            raise


if __name__ == "__main__":
    model_info = HuggingFaceModelInfo()
    logger.info("model_info: %s", model_info.from_pretrained("sdadas/mmlw-e5-base"))

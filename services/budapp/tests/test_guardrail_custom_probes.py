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
#  -----------------------------------------------------------------------------

"""Tests for guardrail custom probe functionality."""

import pytest
from uuid import uuid4

from pydantic import ValidationError

from budapp.guardrails.schemas import (
    GuardrailCustomProbeCreate,
    GuardrailCustomProbeUpdate,
    ClassifierConfig,
    LLMConfig,
    HeadMapping,
    PolicyConfig,
    CategoryDef,
)
from budapp.commons.constants import ScannerTypeEnum, ProbeTypeEnum


class TestClassifierConfig:
    """Tests for ClassifierConfig schema."""

    def test_classifier_config_valid(self):
        """Test valid classifier config."""
        config = ClassifierConfig(
            head_mappings=[
                HeadMapping(head_name="default", target_labels=["SAFE", "UNSAFE"])
            ]
        )
        assert len(config.head_mappings) == 1
        assert config.head_mappings[0].target_labels == ["SAFE", "UNSAFE"]

    def test_classifier_config_with_post_processing(self):
        """Test classifier config with post processing."""
        config = ClassifierConfig(
            head_mappings=[
                HeadMapping(head_name="default", target_labels=["JAILBREAK"])
            ],
            post_processing=[
                {"sanitize.label_rename": {"map": {"JAILBREAK": "malicious"}}}
            ]
        )
        assert config.post_processing is not None
        assert len(config.post_processing) == 1

    def test_classifier_config_requires_head_mappings(self):
        """Test that classifier config requires head_mappings."""
        with pytest.raises(ValidationError):
            ClassifierConfig()

    def test_head_mapping_default_head_name(self):
        """Test that head_name defaults to 'default'."""
        mapping = HeadMapping(target_labels=["LABEL1", "LABEL2"])
        assert mapping.head_name == "default"
        assert mapping.target_labels == ["LABEL1", "LABEL2"]

    def test_head_mapping_custom_head_name(self):
        """Test head mapping with custom head name."""
        mapping = HeadMapping(head_name="custom_head", target_labels=["A", "B", "C"])
        assert mapping.head_name == "custom_head"
        assert len(mapping.target_labels) == 3


class TestLLMConfig:
    """Tests for LLMConfig schema."""

    def test_llm_config_valid(self):
        """Test valid LLM config."""
        config = LLMConfig(
            handler="gpt_safeguard",
            policy=PolicyConfig(
                task="Classify content for safety",
                instructions="Evaluate content...",
                categories=[
                    CategoryDef(id="safe", description="Safe content", violation=False),
                    CategoryDef(id="unsafe", description="Unsafe content", violation=True),
                ]
            )
        )
        assert config.handler == "gpt_safeguard"
        assert len(config.policy.categories) == 2

    def test_llm_config_default_handler(self):
        """Test LLM config uses default handler."""
        config = LLMConfig(
            policy=PolicyConfig(
                task="Test task",
                instructions="Test instructions",
                categories=[
                    CategoryDef(id="test", description="Test", violation=False),
                ]
            )
        )
        assert config.handler == "gpt_safeguard"

    def test_llm_config_requires_policy(self):
        """Test that LLM config requires policy."""
        with pytest.raises(ValidationError):
            LLMConfig()

    def test_policy_config_with_examples(self):
        """Test policy config with examples."""
        from budapp.guardrails.schemas import ExampleDef
        config = LLMConfig(
            policy=PolicyConfig(
                task="Classify content",
                instructions="Evaluate...",
                categories=[
                    CategoryDef(id="safe", description="Safe", violation=False),
                ],
                examples=[
                    ExampleDef(input="Hello", output={"category": "safe"}),
                ]
            )
        )
        assert config.policy.examples is not None
        assert len(config.policy.examples) == 1
        assert config.policy.examples[0].input == "Hello"

    def test_category_def_with_escalate(self):
        """Test category definition with escalate flag."""
        category = CategoryDef(
            id="dangerous",
            description="Dangerous content",
            violation=True,
            escalate=True
        )
        assert category.escalate is True


class TestGuardrailCustomProbeCreate:
    """Tests for GuardrailCustomProbeCreate schema."""

    def test_create_classifier_probe_valid(self):
        """Test creating a valid classifier probe."""
        probe = GuardrailCustomProbeCreate(
            name="Test Classifier",
            description="Test description",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=uuid4(),
            model_config_data=ClassifierConfig(
                head_mappings=[HeadMapping(head_name="default", target_labels=["JAILBREAK"])]
            ),
        )
        assert probe.name == "Test Classifier"
        assert probe.scanner_type == ScannerTypeEnum.CLASSIFIER
        assert probe.description == "Test description"

    def test_create_llm_probe_valid(self):
        """Test creating a valid LLM probe."""
        probe = GuardrailCustomProbeCreate(
            name="Test LLM Scanner",
            scanner_type=ScannerTypeEnum.LLM,
            model_id=uuid4(),
            model_config_data=LLMConfig(
                policy=PolicyConfig(
                    task="Classify content",
                    instructions="Evaluate...",
                    categories=[
                        CategoryDef(id="safe", description="Safe", violation=False),
                    ]
                )
            ),
        )
        assert probe.name == "Test LLM Scanner"
        assert probe.scanner_type == ScannerTypeEnum.LLM

    def test_create_probe_without_description(self):
        """Test that probe creation allows optional description."""
        probe = GuardrailCustomProbeCreate(
            name="Test",
            scanner_type=ScannerTypeEnum.CLASSIFIER,
            model_id=uuid4(),
            model_config_data=ClassifierConfig(
                head_mappings=[HeadMapping(target_labels=["TEST"])]
            ),
        )
        assert probe.description is None

    def test_classifier_scanner_requires_classifier_config(self):
        """Test that classifier scanner requires ClassifierConfig."""
        with pytest.raises(ValidationError) as exc_info:
            GuardrailCustomProbeCreate(
                name="Test",
                scanner_type=ScannerTypeEnum.CLASSIFIER,
                model_id=uuid4(),
                model_config_data=LLMConfig(
                    policy=PolicyConfig(
                        task="Test",
                        instructions="Test",
                        categories=[CategoryDef(id="test", description="Test", violation=False)]
                    )
                ),
            )
        assert "Classifier scanner requires ClassifierConfig" in str(exc_info.value)

    def test_llm_scanner_requires_llm_config(self):
        """Test that LLM scanner requires LLMConfig."""
        with pytest.raises(ValidationError) as exc_info:
            GuardrailCustomProbeCreate(
                name="Test",
                scanner_type=ScannerTypeEnum.LLM,
                model_id=uuid4(),
                model_config_data=ClassifierConfig(
                    head_mappings=[HeadMapping(target_labels=["TEST"])]
                ),
            )
        assert "LLM scanner requires LLMConfig" in str(exc_info.value)

    def test_create_probe_requires_name(self):
        """Test that probe creation requires name."""
        with pytest.raises(ValidationError):
            GuardrailCustomProbeCreate(
                scanner_type=ScannerTypeEnum.CLASSIFIER,
                model_id=uuid4(),
                model_config_data=ClassifierConfig(
                    head_mappings=[HeadMapping(target_labels=["TEST"])]
                ),
            )

    def test_create_probe_requires_model_id(self):
        """Test that probe creation requires model_id."""
        with pytest.raises(ValidationError):
            GuardrailCustomProbeCreate(
                name="Test",
                scanner_type=ScannerTypeEnum.CLASSIFIER,
                model_config_data=ClassifierConfig(
                    head_mappings=[HeadMapping(target_labels=["TEST"])]
                ),
            )

    def test_create_probe_requires_scanner_type(self):
        """Test that probe creation requires scanner_type."""
        with pytest.raises(ValidationError):
            GuardrailCustomProbeCreate(
                name="Test",
                model_id=uuid4(),
                model_config_data=ClassifierConfig(
                    head_mappings=[HeadMapping(target_labels=["TEST"])]
                ),
            )


class TestGuardrailCustomProbeUpdate:
    """Tests for GuardrailCustomProbeUpdate schema."""

    def test_update_probe_partial(self):
        """Test partial update of probe."""
        update = GuardrailCustomProbeUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.description is None
        assert update.model_config_data is None

    def test_update_probe_config_only(self):
        """Test updating only config."""
        update = GuardrailCustomProbeUpdate(
            model_config_data=ClassifierConfig(
                head_mappings=[HeadMapping(target_labels=["NEW_LABEL"])]
            )
        )
        assert update.name is None
        assert update.model_config_data is not None

    def test_update_probe_description_only(self):
        """Test updating only description."""
        update = GuardrailCustomProbeUpdate(description="Updated description")
        assert update.name is None
        assert update.description == "Updated description"
        assert update.model_config_data is None

    def test_update_probe_all_fields(self):
        """Test updating all fields."""
        update = GuardrailCustomProbeUpdate(
            name="Updated Name",
            description="Updated Description",
            model_config_data=LLMConfig(
                policy=PolicyConfig(
                    task="Updated task",
                    instructions="Updated instructions",
                    categories=[CategoryDef(id="new", description="New", violation=False)]
                )
            )
        )
        assert update.name == "Updated Name"
        assert update.description == "Updated Description"
        assert update.model_config_data is not None

    def test_update_probe_empty(self):
        """Test creating empty update (all None)."""
        update = GuardrailCustomProbeUpdate()
        assert update.name is None
        assert update.description is None
        assert update.model_config_data is None


class TestProbeTypeEnum:
    """Tests for ProbeTypeEnum."""

    def test_probe_types(self):
        """Test probe type enum values."""
        assert ProbeTypeEnum.PROVIDER.value == "provider"
        assert ProbeTypeEnum.MODEL_SCANNER.value == "model_scanner"
        assert ProbeTypeEnum.CUSTOM.value == "custom"

    def test_probe_type_is_string_enum(self):
        """Test that ProbeTypeEnum is a string enum."""
        assert isinstance(ProbeTypeEnum.PROVIDER, str)
        assert ProbeTypeEnum.PROVIDER == "provider"


class TestScannerTypeEnum:
    """Tests for ScannerTypeEnum."""

    def test_scanner_types(self):
        """Test scanner type enum values."""
        assert ScannerTypeEnum.CLASSIFIER.value == "classifier"
        assert ScannerTypeEnum.LLM.value == "llm"

    def test_scanner_type_is_string_enum(self):
        """Test that ScannerTypeEnum is a string enum."""
        assert isinstance(ScannerTypeEnum.CLASSIFIER, str)
        assert ScannerTypeEnum.CLASSIFIER == "classifier"

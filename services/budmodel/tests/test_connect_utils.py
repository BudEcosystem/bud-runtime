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

"""Tests for BudConnect utilities and mapping functions."""

import pytest

from budmodel.commons.connect_utils import BudConnectMapper
from budmodel.commons.constants import ModelExtractionStatus


class TestBudConnectMapper:
    """Test BudConnectMapper mapping functions."""

    def test_map_to_model_info_with_null_tasks(self):
        """Test mapping handles null tasks field correctly."""
        cloud_data = {
            "uri": "anthropic/claude-sonnet-4-5",
            "provider_name": "Anthropic",
            "description": "A state-of-the-art model",
            "modality": ["text_input", "text_output"],
            "tasks": None,  # This should not cause validation error
            "tags": [],
            "use_cases": ["coding", "analysis"],
            "advantages": ["fast", "accurate"],
            "disadvantages": ["expensive"],
            "languages": None,
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["tasks"] == []
        assert result["languages"] == []
        assert result["uri"] == "anthropic/claude-sonnet-4-5"

    def test_map_to_model_info_with_null_lists(self):
        """Test mapping handles all null list fields correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": None,
            "tags": None,
            "use_cases": None,
            "advantages": None,
            "disadvantages": None,
            "languages": None,
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        # All null list fields should become empty lists
        assert result["tasks"] == []
        assert result["tags"] == []
        assert result["use_cases"] == []
        assert result["strengths"] == []
        assert result["limitations"] == []
        assert result["languages"] == []

    def test_map_to_model_info_with_empty_lists(self):
        """Test mapping handles empty list fields correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": [],
            "tags": [],
            "use_cases": [],
            "advantages": [],
            "disadvantages": [],
            "languages": [],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        # Empty lists should remain empty lists
        assert result["tasks"] == []
        assert result["tags"] == []
        assert result["use_cases"] == []
        assert result["strengths"] == []
        assert result["limitations"] == []
        assert result["languages"] == []

    def test_map_to_model_info_with_populated_lists(self):
        """Test mapping handles populated list fields correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input", "text_output"],
            "tasks": ["text-generation", "chat"],
            "tags": ["nlp", "llm"],
            "use_cases": ["coding", "writing"],
            "advantages": ["fast", "accurate"],
            "disadvantages": ["expensive"],
            "languages": ["en", "es"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["tasks"] == ["text-generation", "chat"]
        assert result["tags"] == ["nlp", "llm"]
        assert result["use_cases"] == ["coding", "writing"]
        assert result["strengths"] == ["fast", "accurate"]
        assert result["limitations"] == ["expensive"]
        assert result["languages"] == ["en", "es"]

    def test_map_to_model_info_with_null_modality(self):
        """Test mapping handles null modality field correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": None,  # Should default to text_input,text_output
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["modality"] == "text_input,text_output"

    def test_map_to_model_info_with_empty_modality(self):
        """Test mapping handles empty modality list correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": [],  # Should default to text_input,text_output
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["modality"] == "text_input,text_output"

    def test_map_to_model_info_with_null_provider_name(self):
        """Test mapping handles null provider_name correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": None,  # Should default to "Unknown"
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["author"] == "Unknown"

    def test_map_to_model_info_with_empty_provider_name(self):
        """Test mapping handles empty string provider_name correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "",  # Should default to "Unknown"
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["author"] == "Unknown"

    def test_map_to_model_info_with_null_description(self):
        """Test mapping handles null description correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": None,  # Should default to empty string
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["description"] == ""

    def test_map_to_model_info_with_empty_description(self):
        """Test mapping handles empty string description correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "",  # Should remain empty string
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["description"] == ""

    def test_map_to_model_info_with_papers(self):
        """Test mapping handles papers correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
            "papers": [
                {
                    "title": "Test Paper",
                    "authors": ["Author 1", "Author 2"],
                    "url": "https://example.com/paper",
                }
            ],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert "papers" in result
        assert len(result["papers"]) == 1
        assert result["papers"][0]["title"] == "Test Paper"
        assert result["papers"][0]["authors"] == ["Author 1", "Author 2"]

    def test_map_to_model_info_with_null_papers(self):
        """Test mapping handles null papers correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
            "papers": None,
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        # Papers should not be included if null
        assert "papers" not in result

    def test_map_to_model_info_with_architecture(self):
        """Test mapping handles architecture correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
            "architecture": {
                "type": "transformer",
                "family": "llama",
                "num_params": 7000000000,
                "model_weights_size": 14000000000,
            },
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert "architecture" in result
        assert result["architecture"]["type"] == "transformer"
        assert result["architecture"]["num_params"] == 7000000000

    def test_map_to_model_info_with_model_tree(self):
        """Test mapping handles model_tree correctly."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
            "model_tree": {
                "base_model": "llama-2-7b",
                "is_finetune": True,
                "is_adapter": False,
                "is_quantization": False,
                "is_merge": False,
            },
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert "model_tree" in result
        assert result["model_tree"]["base_model"] == "llama-2-7b"
        assert result["model_tree"]["is_finetune"] is True

    def test_map_to_model_info_extraction_status(self):
        """Test that extraction_status is always set to COMPLETED."""
        cloud_data = {
            "uri": "test/model",
            "provider_name": "TestProvider",
            "description": "Test description",
            "modality": ["text_input"],
            "tasks": ["text-generation"],
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        assert result["extraction_status"] == ModelExtractionStatus.COMPLETED

    def test_map_to_model_info_complete_response(self):
        """Test mapping with a complete budconnect response (like anthropic/claude-sonnet-4-5)."""
        cloud_data = {
            "uri": "anthropic/claude-sonnet-4-5",
            "provider_name": "Anthropic",
            "description": "Claude Sonnet 4.5 is a state-of-the-art coding and agent-building model",
            "modality": ["text_input", "text_output", "image_input"],
            "tags": [],
            "tasks": None,  # This is the key field causing the issue
            "use_cases": [
                "Building complex AI agents for extended tasks.",
                "Real-world software development and debugging.",
            ],
            "advantages": [
                "Achieves state-of-the-art performance on SWE-bench Verified",
                "Leads OSWorld benchmark with 61.4% accuracy",
            ],
            "disadvantages": [
                "CBRN classifiers may inadvertently flag normal content",
                "Research preview features are temporary",
            ],
            "languages": None,
            "github_url": None,
            "website_url": None,
            "logo_url": None,
        }

        result = BudConnectMapper.map_to_model_info(cloud_data)

        # Verify all required fields are present and valid
        assert result["uri"] == "anthropic/claude-sonnet-4-5"
        assert result["author"] == "Anthropic"
        assert "Claude Sonnet 4.5" in result["description"]
        assert result["modality"] == "text_input, text_output, image_input"
        assert result["tasks"] == []  # Should be empty list, not None
        assert result["tags"] == []
        assert len(result["use_cases"]) == 2
        assert len(result["strengths"]) == 2
        assert len(result["limitations"]) == 2
        assert result["languages"] == []  # Should be empty list, not None
        assert result["extraction_status"] == ModelExtractionStatus.COMPLETED

    def test_extract_evaluation_data_with_evaluations(self):
        """Test extraction of evaluation data."""
        cloud_data = {
            "evaluations": [
                {"name": "MMLU", "score": 0.85, "metric_type": "accuracy"},
                {"name": "HumanEval", "score": 0.72},
            ]
        }

        result = BudConnectMapper.extract_evaluation_data(cloud_data)

        assert len(result) == 2
        assert result[0]["name"] == "MMLU"
        assert result[0]["score"] == 0.85
        assert result[1]["metric_type"] == "accuracy"

    def test_extract_evaluation_data_with_null_evaluations(self):
        """Test extraction handles null evaluations."""
        cloud_data = {"evaluations": None}

        result = BudConnectMapper.extract_evaluation_data(cloud_data)

        assert result == []

    def test_extract_evaluation_data_with_missing_evaluations(self):
        """Test extraction handles missing evaluations key."""
        cloud_data = {}

        result = BudConnectMapper.extract_evaluation_data(cloud_data)

        assert result == []

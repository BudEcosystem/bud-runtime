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

"""TDD Tests for Template Loader and Startup Sync.

These tests follow TDD methodology - written BEFORE implementation.
Tests are expected to fail until the implementation is complete.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# ============================================================================
# Template Schema Tests
# ============================================================================


class TestTemplateSchema:
    """Tests for Template Pydantic schemas."""

    def test_template_component_schema_valid(self) -> None:
        """Test TemplateComponentSchema with valid data."""
        from budusecases.templates.schemas import TemplateComponentSchema

        data = {
            "name": "llm",
            "display_name": "Language Model",
            "description": "Main LLM component",
            "type": "model",
            "required": True,
            "default_component": "llama-3-8b",
            "compatible_components": ["llama-3-8b", "mistral-7b"],
        }
        schema = TemplateComponentSchema.model_validate(data)
        assert schema.name == "llm"
        assert schema.type == "model"
        assert schema.required is True
        assert len(schema.compatible_components) == 2

    def test_template_component_schema_optional_fields(self) -> None:
        """Test TemplateComponentSchema with optional fields."""
        from budusecases.templates.schemas import TemplateComponentSchema

        data = {
            "name": "reranker",
            "display_name": "Reranker",
            "type": "reranker",
            "required": False,
        }
        schema = TemplateComponentSchema.model_validate(data)
        assert schema.name == "reranker"
        assert schema.required is False
        assert schema.default_component is None
        assert schema.compatible_components == []

    def test_template_parameter_schema_integer(self) -> None:
        """Test TemplateParameterSchema for integer parameter."""
        from budusecases.templates.schemas import TemplateParameterSchema

        data = {
            "type": "integer",
            "default": 512,
            "min": 128,
            "max": 2048,
            "description": "Chunk size for documents",
        }
        schema = TemplateParameterSchema.model_validate(data)
        assert schema.type == "integer"
        assert schema.default == 512
        assert schema.min == 128
        assert schema.max == 2048

    def test_template_parameter_schema_float(self) -> None:
        """Test TemplateParameterSchema for float parameter."""
        from budusecases.templates.schemas import TemplateParameterSchema

        data = {
            "type": "float",
            "default": 0.7,
            "min": 0.0,
            "max": 2.0,
            "description": "Temperature for LLM",
        }
        schema = TemplateParameterSchema.model_validate(data)
        assert schema.type == "float"
        assert schema.default == 0.7

    def test_template_parameter_schema_string(self) -> None:
        """Test TemplateParameterSchema for string parameter."""
        from budusecases.templates.schemas import TemplateParameterSchema

        data = {
            "type": "string",
            "default": "You are a helpful assistant.",
            "description": "System prompt",
        }
        schema = TemplateParameterSchema.model_validate(data)
        assert schema.type == "string"
        assert schema.default == "You are a helpful assistant."

    def test_template_parameter_schema_boolean(self) -> None:
        """Test TemplateParameterSchema for boolean parameter."""
        from budusecases.templates.schemas import TemplateParameterSchema

        data = {
            "type": "boolean",
            "default": False,
            "description": "Enable feature",
        }
        schema = TemplateParameterSchema.model_validate(data)
        assert schema.type == "boolean"
        assert schema.default is False

    def test_template_resources_schema(self) -> None:
        """Test TemplateResourcesSchema."""
        from budusecases.templates.schemas import TemplateResourcesSchema

        data = {
            "minimum": {"cpu": 4, "memory": "16Gi", "gpu": 0},
            "recommended": {"cpu": 8, "memory": "32Gi", "gpu": 1, "gpu_memory": "24Gi"},
        }
        schema = TemplateResourcesSchema.model_validate(data)
        assert schema.minimum["cpu"] == 4
        assert schema.recommended["gpu"] == 1

    def test_template_schema_full(self) -> None:
        """Test TemplateSchema with full template data."""
        from budusecases.templates.schemas import TemplateSchema

        data = {
            "name": "simple-rag",
            "display_name": "Simple RAG",
            "version": "1.0.0",
            "description": "A simple RAG application",
            "category": "rag",
            "tags": ["rag", "retrieval"],
            "components": [
                {
                    "name": "llm",
                    "display_name": "Language Model",
                    "type": "model",
                    "required": True,
                    "compatible_components": ["llama-3-8b"],
                },
                {
                    "name": "embedder",
                    "display_name": "Embedding Model",
                    "type": "embedder",
                    "required": True,
                    "compatible_components": ["bge-large-en"],
                },
            ],
            "parameters": {
                "chunk_size": {
                    "type": "integer",
                    "default": 512,
                    "description": "Chunk size",
                },
            },
            "resources": {
                "minimum": {"cpu": 4, "memory": "16Gi"},
                "recommended": {"cpu": 8, "memory": "32Gi"},
            },
            "deployment_order": ["embedder", "llm"],
        }
        schema = TemplateSchema.model_validate(data)
        assert schema.name == "simple-rag"
        assert schema.version == "1.0.0"
        assert len(schema.components) == 2
        assert "chunk_size" in schema.parameters
        assert schema.deployment_order == ["embedder", "llm"]

    def test_template_schema_minimal(self) -> None:
        """Test TemplateSchema with minimal required fields."""
        from budusecases.templates.schemas import TemplateSchema

        data = {
            "name": "minimal",
            "display_name": "Minimal Template",
            "version": "1.0.0",
            "description": "Minimal template",
            "components": [
                {
                    "name": "llm",
                    "display_name": "LLM",
                    "type": "model",
                    "required": True,
                }
            ],
        }
        schema = TemplateSchema.model_validate(data)
        assert schema.name == "minimal"
        assert schema.category is None
        assert schema.tags == []
        assert schema.parameters == {}
        assert schema.resources is None
        assert schema.deployment_order == []


# ============================================================================
# Template Loader Tests
# ============================================================================


class TestTemplateLoader:
    """Tests for TemplateLoader class."""

    @pytest.fixture
    def temp_templates_dir(self) -> str:
        """Create a temporary directory with test templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid template file
            valid_template = {
                "name": "test-rag",
                "display_name": "Test RAG",
                "version": "1.0.0",
                "description": "Test RAG application",
                "category": "rag",
                "components": [
                    {
                        "name": "llm",
                        "display_name": "LLM",
                        "type": "model",
                        "required": True,
                        "compatible_components": ["llama-3-8b"],
                    }
                ],
                "parameters": {
                    "chunk_size": {
                        "type": "integer",
                        "default": 512,
                        "description": "Chunk size",
                    }
                },
            }
            with open(os.path.join(tmpdir, "test-rag.yaml"), "w") as f:
                yaml.dump(valid_template, f)

            # Create another valid template
            chatbot_template = {
                "name": "test-chatbot",
                "display_name": "Test Chatbot",
                "version": "1.0.0",
                "description": "Test chatbot",
                "category": "conversational",
                "components": [
                    {
                        "name": "llm",
                        "display_name": "LLM",
                        "type": "model",
                        "required": True,
                    }
                ],
            }
            with open(os.path.join(tmpdir, "test-chatbot.yaml"), "w") as f:
                yaml.dump(chatbot_template, f)

            yield tmpdir

    @pytest.fixture
    def invalid_templates_dir(self) -> str:
        """Create a directory with an invalid template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an invalid template (missing required fields)
            invalid_template = {
                "name": "invalid",
                # Missing display_name, version, description, components
            }
            with open(os.path.join(tmpdir, "invalid.yaml"), "w") as f:
                yaml.dump(invalid_template, f)

            yield tmpdir

    def test_loader_initialization(self, temp_templates_dir: str) -> None:
        """Test TemplateLoader initialization."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=temp_templates_dir)
        assert loader.templates_path == Path(temp_templates_dir)

    def test_loader_default_path(self) -> None:
        """Test TemplateLoader with default path from settings."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader()
        # Should use default path from settings
        assert loader.templates_path is not None

    def test_load_single_template(self, temp_templates_dir: str) -> None:
        """Test loading a single template file."""
        from budusecases.templates.loader import TemplateLoader
        from budusecases.templates.schemas import TemplateSchema

        loader = TemplateLoader(templates_path=temp_templates_dir)
        template = loader.load_template("test-rag.yaml")

        assert template is not None
        assert isinstance(template, TemplateSchema)
        assert template.name == "test-rag"
        assert template.version == "1.0.0"

    def test_load_nonexistent_template(self, temp_templates_dir: str) -> None:
        """Test loading a template that doesn't exist."""
        from budusecases.templates.loader import TemplateLoader, TemplateNotFoundError

        loader = TemplateLoader(templates_path=temp_templates_dir)

        with pytest.raises(TemplateNotFoundError):
            loader.load_template("nonexistent.yaml")

    def test_load_all_templates(self, temp_templates_dir: str) -> None:
        """Test loading all templates from directory."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=temp_templates_dir)
        templates = loader.load_all_templates()

        assert len(templates) == 2
        template_names = {t.name for t in templates}
        assert "test-rag" in template_names
        assert "test-chatbot" in template_names

    def test_load_invalid_template(self, invalid_templates_dir: str) -> None:
        """Test loading an invalid template raises error."""
        from budusecases.templates.loader import TemplateLoader, TemplateValidationError

        loader = TemplateLoader(templates_path=invalid_templates_dir)

        with pytest.raises(TemplateValidationError):
            loader.load_template("invalid.yaml")

    def test_load_all_with_skip_invalid(self, invalid_templates_dir: str) -> None:
        """Test loading all templates with skip_invalid option."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=invalid_templates_dir)
        templates = loader.load_all_templates(skip_invalid=True)

        # Should return empty list since all templates are invalid
        assert len(templates) == 0

    def test_load_empty_directory(self) -> None:
        """Test loading from empty directory."""
        from budusecases.templates.loader import TemplateLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = TemplateLoader(templates_path=tmpdir)
            templates = loader.load_all_templates()
            assert templates == []

    def test_get_template_by_name(self, temp_templates_dir: str) -> None:
        """Test getting a template by its name."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=temp_templates_dir)
        template = loader.get_template_by_name("test-rag")

        assert template is not None
        assert template.name == "test-rag"

    def test_get_template_by_name_not_found(self, temp_templates_dir: str) -> None:
        """Test getting nonexistent template by name returns None."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=temp_templates_dir)
        template = loader.get_template_by_name("nonexistent")

        assert template is None

    def test_list_template_names(self, temp_templates_dir: str) -> None:
        """Test listing all template names."""
        from budusecases.templates.loader import TemplateLoader

        loader = TemplateLoader(templates_path=temp_templates_dir)
        names = loader.list_template_names()

        assert len(names) == 2
        assert "test-rag" in names
        assert "test-chatbot" in names


# ============================================================================
# Template Sync Service Tests
# ============================================================================


class TestTemplateSyncService:
    """Tests for TemplateSyncService class."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        return session

    @pytest.fixture
    def temp_templates_dir(self) -> str:
        """Create a temporary directory with test templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template = {
                "name": "sync-test",
                "display_name": "Sync Test",
                "version": "1.0.0",
                "description": "Template for sync testing",
                "category": "test",
                "components": [
                    {
                        "name": "llm",
                        "display_name": "LLM",
                        "type": "model",
                        "required": True,
                    }
                ],
            }
            with open(os.path.join(tmpdir, "sync-test.yaml"), "w") as f:
                yaml.dump(template, f)
            yield tmpdir

    def test_sync_service_initialization(self, mock_session: MagicMock, temp_templates_dir: str) -> None:
        """Test TemplateSyncService initialization."""
        from budusecases.templates.sync import TemplateSyncService

        service = TemplateSyncService(session=mock_session, templates_path=temp_templates_dir)
        assert service.session == mock_session

    def test_sync_templates_creates_new(self, mock_session: MagicMock, temp_templates_dir: str) -> None:
        """Test syncing creates new templates in database."""
        from budusecases.templates.sync import TemplateSyncService

        # Mock that no templates exist in DB
        mock_session.execute = MagicMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        service = TemplateSyncService(session=mock_session, templates_path=temp_templates_dir)
        result = service.sync_templates()

        assert result.created == 1
        assert result.updated == 0
        assert result.deleted == 0
        mock_session.commit.assert_called()

    def test_sync_templates_updates_existing(self, mock_session: MagicMock, temp_templates_dir: str) -> None:
        """Test syncing updates existing templates with version changes."""
        from budusecases.templates.models import Template
        from budusecases.templates.sync import TemplateSyncService

        # Mock an existing template in DB with older version
        existing_template = MagicMock(spec=Template)
        existing_template.name = "sync-test"
        existing_template.version = "0.9.0"  # Older version
        mock_session.execute = MagicMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_template))
        )

        service = TemplateSyncService(session=mock_session, templates_path=temp_templates_dir)
        result = service.sync_templates()

        assert result.updated == 1
        assert result.created == 0
        mock_session.commit.assert_called()

    def test_sync_templates_no_change(self, mock_session: MagicMock, temp_templates_dir: str) -> None:
        """Test syncing when template version matches."""
        from budusecases.templates.models import Template
        from budusecases.templates.sync import TemplateSyncService

        # Mock an existing template in DB with same version
        existing_template = MagicMock(spec=Template)
        existing_template.name = "sync-test"
        existing_template.version = "1.0.0"  # Same version
        mock_session.execute = MagicMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_template))
        )

        service = TemplateSyncService(session=mock_session, templates_path=temp_templates_dir)
        result = service.sync_templates()

        assert result.updated == 0
        assert result.created == 0

    def test_sync_templates_delete_orphans(self, mock_session: MagicMock) -> None:
        """Test syncing deletes templates not in YAML files."""
        from budusecases.templates.models import Template
        from budusecases.templates.sync import TemplateSyncService

        with tempfile.TemporaryDirectory() as tmpdir:
            # No YAML files - empty directory

            # Mock templates that exist in DB but not in files
            orphan_template = MagicMock(spec=Template)
            orphan_template.name = "orphan-template"
            mock_session.execute = MagicMock(
                return_value=MagicMock(
                    scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[orphan_template])))
                )
            )

            service = TemplateSyncService(session=mock_session, templates_path=tmpdir)
            result = service.sync_templates(delete_orphans=True)

            assert result.deleted == 1


# ============================================================================
# Template Model Tests
# ============================================================================


class TestTemplateModel:
    """Tests for Template SQLAlchemy model."""

    def test_template_model_creation(self) -> None:
        """Test creating a Template model instance."""
        from uuid import uuid4

        from budusecases.templates.models import Template

        template = Template(
            id=uuid4(),
            name="test-template",
            display_name="Test Template",
            version="1.0.0",
            description="A test template",
            category="test",
            tags=["test", "sample"],
            parameters={
                "chunk_size": {"type": "integer", "default": 512},
            },
            resources={
                "minimum": {"cpu": 4, "memory": "16Gi"},
            },
            deployment_order=["llm"],
        )

        assert template.name == "test-template"
        assert template.version == "1.0.0"
        assert template.category == "test"
        assert len(template.tags) == 2

    def test_template_component_model_creation(self) -> None:
        """Test creating a TemplateComponent model instance."""
        from uuid import uuid4

        from budusecases.templates.models import TemplateComponent

        component = TemplateComponent(
            id=uuid4(),
            template_id=uuid4(),
            name="llm",
            display_name="Language Model",
            description="Main LLM",
            component_type="model",
            required=True,
            default_component="llama-3-8b",
            compatible_components=["llama-3-8b", "mistral-7b"],
            sort_order=0,
        )

        assert component.name == "llm"
        assert component.component_type == "model"
        assert component.required is True

    def test_template_relationship_with_components(self) -> None:
        """Test Template relationship with TemplateComponents."""
        from uuid import uuid4

        from budusecases.templates.models import Template, TemplateComponent

        template_id = uuid4()
        template = Template(
            id=template_id,
            name="test-template",
            display_name="Test",
            version="1.0.0",
            description="Test",
        )

        component = TemplateComponent(
            id=uuid4(),
            template_id=template_id,
            name="llm",
            display_name="LLM",
            component_type="model",
            required=True,
            sort_order=0,
        )

        # In actual usage, this relationship would be managed by SQLAlchemy
        # Here we just verify the model structure
        assert template.id == component.template_id


# ============================================================================
# Startup Sync Tests
# ============================================================================


class TestStartupSync:
    """Tests for startup synchronization behavior."""

    @pytest.fixture
    def mock_session_maker(self) -> MagicMock:
        """Create a mock session maker."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=None)

        maker = MagicMock(return_value=session)
        return maker

    def test_startup_sync_when_enabled(self, mock_session_maker: MagicMock) -> None:
        """Test that sync runs on startup when enabled."""
        from budusecases.templates.startup import sync_templates_on_startup

        with patch("budusecases.templates.startup.TemplateSyncService") as mock_service:
            mock_service_instance = MagicMock()
            mock_service.return_value = mock_service_instance

            sync_templates_on_startup(
                session_maker=mock_session_maker,
                enabled=True,
            )

            mock_service_instance.sync_templates.assert_called_once()

    def test_startup_sync_when_disabled(self, mock_session_maker: MagicMock) -> None:
        """Test that sync does not run when disabled."""
        from budusecases.templates.startup import sync_templates_on_startup

        with patch("budusecases.templates.startup.TemplateSyncService") as mock_service:
            sync_templates_on_startup(
                session_maker=mock_session_maker,
                enabled=False,
            )

            mock_service.return_value.sync_templates.assert_not_called()

    def test_startup_sync_handles_errors(self, mock_session_maker: MagicMock) -> None:
        """Test that startup sync handles errors gracefully."""
        from budusecases.templates.startup import sync_templates_on_startup

        with patch("budusecases.templates.startup.TemplateSyncService") as mock_service:
            mock_service.return_value.sync_templates.side_effect = Exception("DB error")

            # Should not raise, just log the error
            sync_templates_on_startup(
                session_maker=mock_session_maker,
                enabled=True,
            )


# ============================================================================
# Template CRUD Tests
# ============================================================================


class TestTemplateCRUD:
    """Tests for Template CRUD operations."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create a mock database session."""
        session = MagicMock()
        return session

    def test_create_template(self, mock_session: MagicMock) -> None:
        """Test creating a template via CRUD."""
        from budusecases.templates.crud import TemplateDataManager

        manager = TemplateDataManager(session=mock_session)
        manager.create_template(
            name="new-template",
            display_name="New Template",
            version="1.0.0",
            description="A new template",
            category="test",
            tags=["test"],
            parameters={},
            resources=None,
            deployment_order=[],
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_template_by_id(self, mock_session: MagicMock) -> None:
        """Test getting a template by ID."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        template_id = uuid4()
        mock_template = MagicMock(spec=Template)
        mock_template.id = template_id
        mock_session.get.return_value = mock_template

        manager = TemplateDataManager(session=mock_session)
        result = manager.get_template(template_id)

        assert result == mock_template
        mock_session.get.assert_called_once()

    def test_get_template_by_name(self, mock_session: MagicMock) -> None:
        """Test getting a template by name."""
        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        mock_template = MagicMock(spec=Template)
        mock_template.name = "test-template"
        mock_session.execute.return_value.scalars.return_value.first.return_value = mock_template

        manager = TemplateDataManager(session=mock_session)
        result = manager.get_template_by_name("test-template")

        assert result == mock_template

    def test_list_templates(self, mock_session: MagicMock) -> None:
        """Test listing templates with pagination."""
        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        mock_templates = [MagicMock(spec=Template) for _ in range(3)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_templates

        manager = TemplateDataManager(session=mock_session)
        results = manager.list_templates(page=1, page_size=10)

        assert len(results) == 3

    def test_list_templates_by_category(self, mock_session: MagicMock) -> None:
        """Test listing templates filtered by category."""
        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        mock_templates = [MagicMock(spec=Template)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_templates

        manager = TemplateDataManager(session=mock_session)
        results = manager.list_templates(category="rag")

        assert len(results) == 1

    def test_update_template(self, mock_session: MagicMock) -> None:
        """Test updating a template."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        template_id = uuid4()
        mock_template = MagicMock(spec=Template)
        mock_template.id = template_id
        mock_session.get.return_value = mock_template

        manager = TemplateDataManager(session=mock_session)
        manager.update_template(template_id, version="2.0.0")

        assert mock_template.version == "2.0.0"
        mock_session.flush.assert_called_once()

    def test_delete_template(self, mock_session: MagicMock) -> None:
        """Test deleting a template."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import Template

        template_id = uuid4()
        mock_template = MagicMock(spec=Template)
        mock_session.get.return_value = mock_template

        manager = TemplateDataManager(session=mock_session)
        result = manager.delete_template(template_id)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_template)

    def test_delete_nonexistent_template(self, mock_session: MagicMock) -> None:
        """Test deleting a template that doesn't exist."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager

        mock_session.get.return_value = None

        manager = TemplateDataManager(session=mock_session)
        result = manager.delete_template(uuid4())

        assert result is False

    def test_add_template_component(self, mock_session: MagicMock) -> None:
        """Test adding a component to a template."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager

        template_id = uuid4()

        manager = TemplateDataManager(session=mock_session)
        manager.add_template_component(
            template_id=template_id,
            name="llm",
            display_name="Language Model",
            component_type="model",
            required=True,
            sort_order=0,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_get_template_components(self, mock_session: MagicMock) -> None:
        """Test getting components for a template."""
        from uuid import uuid4

        from budusecases.templates.crud import TemplateDataManager
        from budusecases.templates.models import TemplateComponent

        template_id = uuid4()
        mock_components = [MagicMock(spec=TemplateComponent) for _ in range(2)]
        mock_session.execute.return_value.scalars.return_value.all.return_value = mock_components

        manager = TemplateDataManager(session=mock_session)
        results = manager.get_template_components(template_id)

        assert len(results) == 2

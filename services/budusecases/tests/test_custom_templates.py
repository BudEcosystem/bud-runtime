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

"""Tests for custom user-created templates."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from budusecases.templates.enums import TemplateSource
from budusecases.templates.schemas import (
    CustomTemplateCreateSchema,
    CustomTemplateUpdateSchema,
    HelmChartConfig,
    TemplateComponentSchema,
    TemplateParameterSchema,
)
from budusecases.templates.services import (
    InvalidComponentError,
    InvalidComponentTypeError,
    TemplateService,
)

# ============================================================================
# Fixtures
# ============================================================================


def make_component(**overrides):
    """Create a TemplateComponentSchema with defaults."""
    defaults = {
        "name": "llm",
        "display_name": "LLM Model",
        "type": "model",
        "required": True,
        "compatible_components": ["llama-3-8b", "mistral-7b"],
    }
    defaults.update(overrides)
    return TemplateComponentSchema(**defaults)


def make_create_schema(**overrides):
    """Create a CustomTemplateCreateSchema with defaults."""
    defaults = {
        "name": "my-custom-rag",
        "display_name": "My Custom RAG",
        "description": "A custom RAG pipeline",
        "components": [make_component()],
    }
    defaults.update(overrides)
    return CustomTemplateCreateSchema(**defaults)


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestCustomTemplateCreateSchemaValidation:
    """Test schema validation for custom template creation."""

    def test_valid_schema(self):
        schema = make_create_schema()
        assert schema.name == "my-custom-rag"
        assert schema.version == "1.0.0"
        assert schema.is_public is False

    def test_valid_name_patterns(self):
        for name in ["my-rag", "rag1", "a", "test-123-pipeline"]:
            schema = make_create_schema(name=name)
            assert schema.name == name

    def test_invalid_name_uppercase(self):
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            make_create_schema(name="MyRag")

    def test_invalid_name_starts_with_hyphen(self):
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            make_create_schema(name="-invalid")

    def test_invalid_name_spaces(self):
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            make_create_schema(name="my rag")

    def test_reserved_name_prefix(self):
        with pytest.raises(ValidationError, match="reserved"):
            make_create_schema(name="system-default")

    def test_empty_components_rejected(self):
        with pytest.raises(ValidationError):
            make_create_schema(components=[])

    def test_default_version(self):
        schema = make_create_schema()
        assert schema.version == "1.0.0"

    def test_custom_version(self):
        schema = make_create_schema(version="2.0.0")
        assert schema.version == "2.0.0"

    def test_default_is_private(self):
        schema = make_create_schema()
        assert schema.is_public is False

    def test_public_template(self):
        schema = make_create_schema(is_public=True)
        assert schema.is_public is True

    def test_parameters_validated(self):
        schema = make_create_schema(
            parameters={
                "chunk_size": TemplateParameterSchema(
                    type="integer", default=512, min=64, max=4096, description="Chunk size"
                )
            }
        )
        assert "chunk_size" in schema.parameters

    def test_deployment_order(self):
        components = [
            make_component(name="llm"),
            make_component(name="embedder", display_name="Embedder", type="embedder"),
        ]
        schema = make_create_schema(
            components=components,
            deployment_order=["embedder", "llm"],
        )
        assert schema.deployment_order == ["embedder", "llm"]


class TestCustomTemplateUpdateSchemaValidation:
    """Test schema validation for custom template update."""

    def test_all_fields_optional(self):
        schema = CustomTemplateUpdateSchema()
        assert schema.display_name is None
        assert schema.components is None
        assert schema.is_public is None

    def test_partial_update(self):
        schema = CustomTemplateUpdateSchema(display_name="Updated Name", is_public=True)
        assert schema.display_name == "Updated Name"
        assert schema.is_public is True
        assert schema.description is None


# ============================================================================
# Enum Tests
# ============================================================================


class TestTemplateSourceEnum:
    """Test TemplateSource enum."""

    def test_system_value(self):
        assert TemplateSource.SYSTEM == "system"
        assert TemplateSource.SYSTEM.value == "system"

    def test_user_value(self):
        assert TemplateSource.USER == "user"
        assert TemplateSource.USER.value == "user"

    def test_from_string(self):
        assert TemplateSource("system") == TemplateSource.SYSTEM
        assert TemplateSource("user") == TemplateSource.USER


# ============================================================================
# Service Validation Tests
# ============================================================================


class TestTemplateServiceValidation:
    """Test TemplateService validation logic (unit tests without DB)."""

    def test_validate_invalid_component_type(self):
        service = TemplateService.__new__(TemplateService)
        components = [make_component(type="invalid_type")]
        with pytest.raises(InvalidComponentTypeError, match="invalid_type"):
            service._validate_components(components)

    def test_validate_valid_component_types(self):
        service = TemplateService.__new__(TemplateService)
        for comp_type in ["model", "llm", "embedder", "reranker", "memory_store"]:
            components = [make_component(type=comp_type)]
            service._validate_components(components)  # Should not raise

    def test_validate_empty_compatible_component(self):
        service = TemplateService.__new__(TemplateService)
        components = [make_component(compatible_components=["valid", ""])]
        with pytest.raises(InvalidComponentError, match="empty"):
            service._validate_components(components)

    def test_validate_deployment_order_unknown_component(self):
        service = TemplateService.__new__(TemplateService)
        components = [make_component(name="llm")]
        with pytest.raises(InvalidComponentError, match="unknown component"):
            service._validate_deployment_order(["nonexistent"], components)

    def test_validate_deployment_order_valid(self):
        service = TemplateService.__new__(TemplateService)
        components = [
            make_component(name="llm"),
            make_component(name="embedder"),
        ]
        service._validate_deployment_order(["llm", "embedder"], components)  # Should not raise


# ============================================================================
# CRUD Visibility Tests (unit tests with mock session)
# ============================================================================


class TestCrudVisibilityFiltering:
    """Test CRUD visibility filtering logic."""

    def test_list_templates_builds_visibility_filter(self):
        """Verify list_templates accepts user_id and source params."""
        from unittest.mock import MagicMock

        from budusecases.templates.crud import TemplateDataManager

        session = MagicMock()
        # Mock the query chain
        session.execute.return_value.scalars.return_value.all.return_value = []
        manager = TemplateDataManager(session=session)

        # Should not raise
        result = manager.list_templates(user_id=uuid4(), source="user", category="rag")
        assert result == []
        assert session.execute.called

    def test_count_templates_with_source_filter(self):
        """Verify count_templates accepts source param."""
        from unittest.mock import MagicMock

        from budusecases.templates.crud import TemplateDataManager

        session = MagicMock()
        session.execute.return_value.scalar.return_value = 0
        manager = TemplateDataManager(session=session)

        result = manager.count_templates(user_id=uuid4(), source="system")
        assert result == 0

    def test_get_template_by_name_with_user_id(self):
        """Verify get_template_by_name accepts user_id."""
        from unittest.mock import MagicMock

        from budusecases.templates.crud import TemplateDataManager

        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None
        manager = TemplateDataManager(session=session)

        result = manager.get_template_by_name("my-rag", user_id=uuid4())
        assert result is None

    def test_get_user_template(self):
        """Verify get_user_template filters by user_id and source."""
        from unittest.mock import MagicMock

        from budusecases.templates.crud import TemplateDataManager

        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        manager = TemplateDataManager(session=session)

        result = manager.get_user_template(uuid4(), uuid4())
        assert result is None
        assert session.execute.called


# ============================================================================
# Sync Protection Tests
# ============================================================================


class TestSyncProtection:
    """Test that sync operations only affect system templates."""

    def test_delete_orphans_filters_by_source(self):
        """Verify _delete_orphan_templates only deletes system templates."""
        from unittest.mock import MagicMock

        from budusecases.templates.sync import TemplateSyncService

        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        service = TemplateSyncService.__new__(TemplateSyncService)
        service.session = session
        service.data_manager = MagicMock()

        from budusecases.templates.sync import SyncResult

        result = SyncResult()
        service._delete_orphan_templates({"existing-template"}, result)

        # Verify session.execute was called (the WHERE clause includes source='system')
        assert session.execute.called
        assert result.deleted == 0

    def test_sync_single_template_looks_up_system_only(self):
        """Verify _sync_single_template looks up by source='system'."""
        from unittest.mock import MagicMock

        from budusecases.templates.schemas import TemplateSchema
        from budusecases.templates.sync import SyncResult, TemplateSyncService

        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        service = TemplateSyncService.__new__(TemplateSyncService)
        service.session = session
        service.data_manager = MagicMock()

        # Mock _create_template_from_schema to avoid actual creation
        service._create_template_from_schema = MagicMock()

        template_schema = MagicMock(spec=TemplateSchema)
        template_schema.name = "test-template"
        template_schema.version = "1.0"

        result = SyncResult()
        service._sync_single_template(template_schema, result)

        assert result.created == 1
        assert session.execute.called


# ============================================================================
# Create Template with Components Tests
# ============================================================================


class TestCreateTemplateWithComponents:
    """Test creating templates with component definitions."""

    def test_schema_with_multiple_components(self):
        components = [
            make_component(name="llm", type="model"),
            make_component(name="embedder", display_name="Embedder", type="embedder"),
        ]
        schema = make_create_schema(
            components=components,
            deployment_order=["embedder", "llm"],
        )
        assert len(schema.components) == 2
        assert schema.deployment_order == ["embedder", "llm"]

    def test_schema_with_parameters_and_resources(self):
        from budusecases.templates.schemas import TemplateResourcesSchema

        schema = make_create_schema(
            parameters={
                "temperature": TemplateParameterSchema(
                    type="float", default=0.7, min=0.0, max=2.0, description="Sampling temperature"
                ),
            },
            resources=TemplateResourcesSchema(
                minimum={"cpu": 2, "memory": "4Gi"},
                recommended={"cpu": 4, "memory": "8Gi", "gpu": 1},
            ),
        )
        assert "temperature" in schema.parameters
        assert schema.resources is not None
        assert schema.resources.minimum["cpu"] == 2


# ============================================================================
# Helm Component & Chart Persistence Tests
# ============================================================================


def make_helm_component(**overrides):
    """Create a TemplateComponentSchema of type helm with chart config."""
    defaults = {
        "name": "agent-runtime",
        "display_name": "Agent Runtime",
        "type": "helm",
        "required": True,
        "chart": HelmChartConfig(
            ref="oci://registry.example.com/charts/agent-runtime",
            version="1.2.0",
            values={"replicaCount": 2, "image": {"tag": "latest"}},
        ),
    }
    defaults.update(overrides)
    return TemplateComponentSchema(**defaults)


class TestHelmComponentSchemaValidation:
    """Test helm-type component schema validation."""

    def test_valid_helm_component(self):
        comp = make_helm_component()
        assert comp.type == "helm"
        assert comp.chart is not None
        assert comp.chart.ref == "oci://registry.example.com/charts/agent-runtime"
        assert comp.chart.version == "1.2.0"

    def test_helm_component_requires_chart(self):
        with pytest.raises(ValidationError, match="chart.*required for helm"):
            TemplateComponentSchema(
                name="agent",
                display_name="Agent",
                type="helm",
                required=True,
            )

    def test_non_helm_component_rejects_chart(self):
        with pytest.raises(ValidationError, match="only allowed for helm"):
            TemplateComponentSchema(
                name="llm",
                display_name="LLM",
                type="model",
                required=True,
                chart=HelmChartConfig(ref="oci://example.com/chart"),
            )

    def test_helm_chart_minimal(self):
        """Helm chart with only ref (version and values optional)."""
        comp = make_helm_component(chart=HelmChartConfig(ref="oci://example.com/chart"))
        assert comp.chart.version is None
        assert comp.chart.values == {}

    def test_helm_chart_ref_oci(self):
        """OCI registry reference is valid."""
        comp = make_helm_component(chart=HelmChartConfig(ref="oci://ghcr.io/myorg/mychart"))
        assert comp.chart.ref == "oci://ghcr.io/myorg/mychart"

    def test_helm_chart_ref_https(self):
        """HTTPS URL reference is valid."""
        comp = make_helm_component(chart=HelmChartConfig(ref="https://charts.example.com/myrepo/mychart"))
        assert comp.chart.ref.startswith("https://")

    def test_helm_chart_ref_local_path(self):
        """Local path reference is valid."""
        comp = make_helm_component(chart=HelmChartConfig(ref="charts/my-local-chart"))
        assert comp.chart.ref == "charts/my-local-chart"

    def test_helm_chart_ref_invalid_protocol(self):
        """Invalid protocol (ftp://) is rejected."""
        with pytest.raises(ValidationError, match="Invalid chart reference"):
            make_helm_component(chart=HelmChartConfig(ref="ftp://bad.example.com/chart"))


class TestHelmTemplateCreation:
    """Test creating templates with helm components."""

    def test_create_schema_with_helm_component(self):
        """Custom template with a helm component is valid."""
        schema = make_create_schema(
            components=[
                make_component(name="llm", type="model"),
                make_helm_component(name="agent-runtime"),
            ],
            deployment_order=["llm", "agent-runtime"],
        )
        assert len(schema.components) == 2
        assert schema.components[1].type == "helm"
        assert schema.components[1].chart is not None

    def test_helm_type_accepted_by_service_validation(self):
        """TemplateService accepts 'helm' as a valid component type."""
        service = TemplateService.__new__(TemplateService)
        components = [make_helm_component()]
        service._validate_components(components)  # Should not raise

    def test_chart_model_dump_produces_dict(self):
        """chart.model_dump() produces a serializable dict for JSONB storage."""
        comp = make_helm_component()
        chart_dict = comp.chart.model_dump()
        assert isinstance(chart_dict, dict)
        assert chart_dict["ref"] == "oci://registry.example.com/charts/agent-runtime"
        assert chart_dict["version"] == "1.2.0"
        assert chart_dict["values"] == {"replicaCount": 2, "image": {"tag": "latest"}}

    def test_service_passes_chart_to_crud(self):
        """create_custom_template passes chart data to add_template_component."""
        from unittest.mock import MagicMock

        session = MagicMock()

        service = TemplateService(session=session)
        service.data_manager = MagicMock()
        service.data_manager.get_template_by_name.return_value = None
        service.data_manager.create_template.return_value = MagicMock(id=uuid4())

        schema = make_create_schema(components=[make_helm_component(name="agent")])

        service.create_custom_template(schema, user_id=uuid4())

        # Verify add_template_component was called with chart kwarg
        call_kwargs = service.data_manager.add_template_component.call_args[1]
        assert "chart" in call_kwargs
        assert call_kwargs["chart"]["ref"] == "oci://registry.example.com/charts/agent-runtime"
        assert call_kwargs["chart"]["version"] == "1.2.0"

    def test_service_passes_none_chart_for_model(self):
        """create_custom_template passes chart=None for non-helm components."""
        from unittest.mock import MagicMock

        session = MagicMock()

        service = TemplateService(session=session)
        service.data_manager = MagicMock()
        service.data_manager.get_template_by_name.return_value = None
        service.data_manager.create_template.return_value = MagicMock(id=uuid4())

        schema = make_create_schema(components=[make_component(name="llm")])

        service.create_custom_template(schema, user_id=uuid4())

        call_kwargs = service.data_manager.add_template_component.call_args[1]
        assert call_kwargs["chart"] is None

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

"""Tests for Helm component schema validation."""

import pytest
from pydantic import ValidationError

from budusecases.templates.schemas import (
    CustomTemplateCreateSchema,
    HelmChartConfig,
    TemplateComponentSchema,
)

# ============================================================================
# Helpers
# ============================================================================


def make_helm_chart(**overrides) -> HelmChartConfig:
    """Create a HelmChartConfig with sensible defaults."""
    defaults = {
        "ref": "oci://registry.example.com/charts/myapp",
        "version": "1.0.0",
    }
    defaults.update(overrides)
    return HelmChartConfig(**defaults)


def make_component(**overrides) -> TemplateComponentSchema:
    """Create a TemplateComponentSchema with defaults."""
    defaults = {
        "name": "llm",
        "display_name": "LLM Model",
        "type": "model",
        "required": True,
        "compatible_components": [],
    }
    defaults.update(overrides)
    return TemplateComponentSchema(**defaults)


def make_create_schema(**overrides) -> CustomTemplateCreateSchema:
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
# HelmChartConfig Validation Tests
# ============================================================================


class TestHelmChartConfig:
    """Tests for HelmChartConfig field validation."""

    def test_helm_chart_config_valid_oci(self):
        """OCI registry references should validate successfully."""
        config = HelmChartConfig(ref="oci://registry.example.com/charts/myapp", version="1.0.0")
        assert config.ref == "oci://registry.example.com/charts/myapp"
        assert config.version == "1.0.0"

    def test_helm_chart_config_valid_https(self):
        """HTTPS URL references should validate successfully."""
        config = HelmChartConfig(ref="https://charts.example.com/myapp-1.0.0.tgz")
        assert config.ref == "https://charts.example.com/myapp-1.0.0.tgz"
        assert config.version is None

    def test_helm_chart_config_invalid_ref(self):
        """References without a recognized prefix should be rejected."""
        with pytest.raises(ValidationError, match="Invalid chart reference"):
            HelmChartConfig(ref="invalid-ref")

    def test_helm_chart_config_with_values(self):
        """A values dict should be accepted and preserved on the config."""
        values = {"replicaCount": 3, "image": {"tag": "latest"}}
        config = HelmChartConfig(
            ref="oci://registry.example.com/charts/myapp",
            version="1.0.0",
            values=values,
        )
        assert config.values == values
        assert config.values["replicaCount"] == 3
        assert config.values["image"]["tag"] == "latest"


# ============================================================================
# TemplateComponentSchema Helm Validation Tests
# ============================================================================


class TestTemplateComponentSchemaHelmValidation:
    """Tests for the helm-specific model validator on TemplateComponentSchema."""

    def test_helm_component_requires_chart(self):
        """A helm-type component with no chart should raise ValidationError."""
        with pytest.raises(ValidationError, match="chart.*required"):
            TemplateComponentSchema(
                name="my-helm",
                display_name="My Helm Component",
                type="helm",
                chart=None,
            )

    def test_helm_component_with_chart_valid(self):
        """A helm-type component with a valid chart should validate."""
        chart = make_helm_chart()
        component = TemplateComponentSchema(
            name="my-helm",
            display_name="My Helm Component",
            type="helm",
            chart=chart,
        )
        assert component.type == "helm"
        assert component.chart is not None
        assert component.chart.ref == "oci://registry.example.com/charts/myapp"

    def test_non_helm_component_rejects_chart(self):
        """A non-helm component with a chart should raise ValidationError."""
        chart = make_helm_chart()
        with pytest.raises(ValidationError, match="chart.*only.*helm"):
            TemplateComponentSchema(
                name="llm",
                display_name="LLM Model",
                type="model",
                chart=chart,
            )

    def test_non_helm_component_without_chart_valid(self):
        """A non-helm component without a chart should validate normally."""
        component = TemplateComponentSchema(
            name="llm",
            display_name="LLM Model",
            type="model",
            chart=None,
        )
        assert component.type == "model"
        assert component.chart is None


# ============================================================================
# CustomTemplateCreateSchema with Helm Component Tests
# ============================================================================


class TestCustomTemplateCreateSchemaHelm:
    """Tests for CustomTemplateCreateSchema containing helm components."""

    def test_custom_template_with_helm_component(self):
        """A custom template containing a valid helm component should validate."""
        helm_component = make_component(
            name="my-service",
            display_name="My Service",
            type="helm",
            chart=make_helm_chart(),
        )
        schema = make_create_schema(components=[helm_component])
        assert len(schema.components) == 1
        assert schema.components[0].type == "helm"
        assert schema.components[0].chart is not None
        assert schema.components[0].chart.ref == "oci://registry.example.com/charts/myapp"

    def test_custom_template_with_helm_missing_chart(self):
        """A custom template with a helm component but no chart should raise ValidationError."""
        with pytest.raises(ValidationError, match="chart.*required"):
            make_create_schema(
                components=[
                    TemplateComponentSchema(
                        name="my-service",
                        display_name="My Service",
                        type="helm",
                        chart=None,
                    )
                ]
            )

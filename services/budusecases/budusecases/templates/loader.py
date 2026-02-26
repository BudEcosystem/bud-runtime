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

"""Template Loader for YAML files."""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schemas import TemplateSchema

logger = logging.getLogger(__name__)


class TemplateNotFoundError(Exception):
    """Raised when a template file is not found."""

    pass


class TemplateValidationError(Exception):
    """Raised when a template file fails validation."""

    pass


class TemplateLoader:
    """Loads and validates YAML template files."""

    def __init__(self, templates_path: str | None = None) -> None:
        """Initialize the template loader.

        Args:
            templates_path: Path to templates directory. If not provided,
                           uses default from settings.
        """
        if templates_path is None:
            from budusecases.commons.config import app_settings

            templates_path = app_settings.templates_path

        self.templates_path = Path(templates_path)
        self._cache: dict[str, TemplateSchema] = {}

    def load_template(self, filename: str) -> TemplateSchema:
        """Load a single template from a YAML file.

        Args:
            filename: Name of the YAML file to load.

        Returns:
            Parsed and validated TemplateSchema.

        Raises:
            TemplateNotFoundError: If the file doesn't exist.
            TemplateValidationError: If the file fails validation.
        """
        file_path = self.templates_path / filename
        if not file_path.exists():
            raise TemplateNotFoundError(f"Template file not found: {filename}")

        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            template = TemplateSchema.model_validate(data)
            self._cache[template.name] = template
            return template

        except yaml.YAMLError as e:
            raise TemplateValidationError(f"Invalid YAML in {filename}: {e}") from e
        except ValidationError as e:
            raise TemplateValidationError(f"Template validation failed for {filename}: {e}") from e

    def load_all_templates(self, skip_invalid: bool = False) -> list[TemplateSchema]:
        """Load all templates from the templates directory.

        Args:
            skip_invalid: If True, skip invalid templates instead of raising.

        Returns:
            List of loaded and validated templates.

        Raises:
            TemplateValidationError: If any template fails validation and
                                    skip_invalid is False.
        """
        templates: list[TemplateSchema] = []

        if not self.templates_path.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_path}")
            return templates

        for yaml_file in self.templates_path.glob("*.yaml"):
            try:
                template = self.load_template(yaml_file.name)
                templates.append(template)
            except (TemplateNotFoundError, TemplateValidationError) as e:
                if skip_invalid:
                    logger.warning(f"Skipping invalid template {yaml_file.name}: {e}")
                else:
                    raise

        # Also check .yml extension
        for yaml_file in self.templates_path.glob("*.yml"):
            try:
                template = self.load_template(yaml_file.name)
                templates.append(template)
            except (TemplateNotFoundError, TemplateValidationError) as e:
                if skip_invalid:
                    logger.warning(f"Skipping invalid template {yaml_file.name}: {e}")
                else:
                    raise

        return templates

    def get_template_by_name(self, name: str) -> TemplateSchema | None:
        """Get a template by its name from cache or by loading all templates.

        Args:
            name: Template name to look up.

        Returns:
            Template if found, None otherwise.
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        # Load all templates if cache is empty
        if not self._cache:
            self.load_all_templates(skip_invalid=True)

        return self._cache.get(name)

    def list_template_names(self) -> list[str]:
        """List all template names available in the templates directory.

        Returns:
            List of template names.
        """
        # Load all templates if cache is empty
        if not self._cache:
            self.load_all_templates(skip_invalid=True)

        return list(self._cache.keys())

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()

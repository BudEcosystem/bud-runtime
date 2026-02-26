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

"""Template Sync Service for synchronizing YAML templates to database."""

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crud import TemplateDataManager
from .loader import TemplateLoader
from .models import Template
from .schemas import TemplateSchema

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a template sync operation."""

    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class TemplateSyncService:
    """Service for synchronizing YAML templates to the database."""

    def __init__(
        self,
        session: Session,
        templates_path: str | None = None,
    ) -> None:
        """Initialize the sync service.

        Args:
            session: SQLAlchemy database session.
            templates_path: Path to templates directory.
        """
        self.session = session
        self.loader = TemplateLoader(templates_path=templates_path)
        self.data_manager = TemplateDataManager(session=session)

    def sync_templates(self, delete_orphans: bool = False) -> SyncResult:
        """Synchronize YAML templates to the database.

        This method:
        1. Loads all templates from YAML files
        2. Creates or updates templates in the database
        3. Optionally deletes templates not in YAML files

        Args:
            delete_orphans: If True, delete templates in DB but not in YAML.

        Returns:
            SyncResult with counts of operations performed.
        """
        result = SyncResult()

        # Load all templates from YAML files
        yaml_templates = self.loader.load_all_templates(skip_invalid=True)
        yaml_template_names = {t.name for t in yaml_templates}

        # Process each YAML template
        for template_schema in yaml_templates:
            try:
                self._sync_single_template(template_schema, result)
            except Exception as e:
                logger.error(f"Error syncing template {template_schema.name}: {e}")
                result.errors.append(f"{template_schema.name}: {str(e)}")

        # Handle orphan deletion
        if delete_orphans:
            self._delete_orphan_templates(yaml_template_names, result)

        self.session.commit()
        return result

    def _sync_single_template(self, template_schema: TemplateSchema, result: SyncResult) -> None:
        """Sync a single template to the database.

        Only looks up system templates — user-created templates with the
        same name are left untouched.

        Args:
            template_schema: Template schema from YAML.
            result: SyncResult to update with operation counts.
        """
        # Only look up system templates, not user-created ones
        stmt = select(Template).where(
            Template.name == template_schema.name,
            Template.source == "system",
        )
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing is None:
            # Create new template
            self._create_template_from_schema(template_schema)
            result.created += 1
            logger.info(f"Created template: {template_schema.name}")

        elif existing.version != template_schema.version:
            # Update existing template
            self._update_template_from_schema(existing, template_schema)
            result.updated += 1
            logger.info(
                f"Updated template: {template_schema.name} (v{existing.version} -> v{template_schema.version})"
            )

        else:
            # Same version, skip
            result.skipped += 1
            logger.debug(f"Skipped template (same version): {template_schema.name}")

    def _create_template_from_schema(self, schema: TemplateSchema) -> Template:
        """Create a template and its components from a schema.

        Args:
            schema: Template schema from YAML.

        Returns:
            Created Template instance.
        """
        # Convert parameter schemas to dicts
        parameters = {name: param.model_dump() for name, param in schema.parameters.items()}

        # Convert resources if present
        resources = schema.resources.model_dump() if schema.resources else None

        # Convert access config if present
        access = schema.access.model_dump() if schema.access else None

        template = self.data_manager.create_template(
            name=schema.name,
            display_name=schema.display_name,
            version=schema.version,
            description=schema.description,
            category=schema.category,
            tags=schema.tags,
            parameters=parameters,
            resources=resources,
            deployment_order=schema.deployment_order,
            access=access,
            source="system",
            is_public=True,
        )

        # Create components
        for idx, comp_schema in enumerate(schema.components):
            self.data_manager.add_template_component(
                template_id=template.id,
                name=comp_schema.name,
                display_name=comp_schema.display_name,
                description=comp_schema.description,
                component_type=comp_schema.type,
                required=comp_schema.required,
                default_component=comp_schema.default_component,
                compatible_components=comp_schema.compatible_components,
                chart=comp_schema.chart.model_dump() if comp_schema.chart else None,
                sort_order=idx,
            )

        return template

    def _update_template_from_schema(self, existing: Template, schema: TemplateSchema) -> None:
        """Update an existing template from a schema.

        Args:
            existing: Existing Template instance.
            schema: Updated template schema from YAML.
        """
        # Convert parameter schemas to dicts
        parameters = {name: param.model_dump() for name, param in schema.parameters.items()}

        # Convert resources if present
        resources = schema.resources.model_dump() if schema.resources else None

        # Convert access config if present
        access = schema.access.model_dump() if schema.access else None

        # Update template attributes
        self.data_manager.update_template(
            existing.id,
            display_name=schema.display_name,
            version=schema.version,
            description=schema.description,
            category=schema.category,
            tags=schema.tags,
            parameters=parameters,
            resources=resources,
            deployment_order=schema.deployment_order,
            access=access,
        )

        # Delete and recreate components
        self.data_manager.delete_template_components(existing.id)

        for idx, comp_schema in enumerate(schema.components):
            self.data_manager.add_template_component(
                template_id=existing.id,
                name=comp_schema.name,
                display_name=comp_schema.display_name,
                description=comp_schema.description,
                component_type=comp_schema.type,
                required=comp_schema.required,
                default_component=comp_schema.default_component,
                compatible_components=comp_schema.compatible_components,
                chart=comp_schema.chart.model_dump() if comp_schema.chart else None,
                sort_order=idx,
            )

    def _delete_orphan_templates(self, yaml_names: set[str], result: SyncResult) -> None:
        """Delete system templates in DB that are not in YAML files.

        Only deletes system-sourced templates. User-created templates
        are never deleted by sync.

        Args:
            yaml_names: Set of template names from YAML files.
            result: SyncResult to update with deletion count.
        """
        stmt = select(Template).where(
            ~Template.name.in_(yaml_names),
            Template.source == "system",
        )
        orphans = self.session.execute(stmt).scalars().all()

        for template in orphans:
            self.data_manager.delete_template(template.id)
            result.deleted += 1
            logger.info(f"Deleted orphan template: {template.name}")

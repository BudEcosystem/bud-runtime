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

"""Template Service for custom template CRUD orchestration."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .crud import TemplateDataManager
from .models import Template
from .schemas import CustomTemplateCreateSchema, CustomTemplateUpdateSchema

logger = logging.getLogger(__name__)

VALID_COMPONENT_TYPES = {"model", "llm", "embedder", "reranker", "memory_store", "helm"}


class TemplateNameConflictError(Exception):
    """Raised when a template name already exists for the user."""

    pass


class InvalidComponentTypeError(Exception):
    """Raised when a component has an invalid type."""

    pass


class InvalidComponentError(Exception):
    """Raised when a component definition is invalid."""

    pass


class TemplateNotOwnedError(Exception):
    """Raised when a user tries to modify a template they don't own."""

    pass


class TemplateService:
    """Service for custom template CRUD orchestration."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.data_manager = TemplateDataManager(session=session)

    def create_custom_template(
        self,
        schema: CustomTemplateCreateSchema,
        user_id: UUID,
    ) -> Template:
        """Create a custom user template.

        Args:
            schema: Template creation schema.
            user_id: Owner user UUID.

        Returns:
            Created Template instance.

        Raises:
            TemplateNameConflictError: If name already exists for this user.
            InvalidComponentTypeError: If a component has an invalid type.
            InvalidComponentError: If a component definition is invalid.
        """
        self._validate_template(schema)

        # Check name uniqueness for this user
        existing = self.data_manager.get_template_by_name(schema.name, user_id=user_id)
        if existing is not None and existing.user_id == user_id:
            raise TemplateNameConflictError(f"Template name '{schema.name}' already exists for this user")

        # Convert parameter schemas to dicts
        parameters: dict[str, Any] = {name: param.model_dump() for name, param in schema.parameters.items()}
        resources = schema.resources.model_dump() if schema.resources else None
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
            source="user",
            user_id=user_id,
            is_public=schema.is_public,
        )

        # Create components
        for idx, comp in enumerate(schema.components):
            self.data_manager.add_template_component(
                template_id=template.id,
                name=comp.name,
                display_name=comp.display_name,
                description=comp.description,
                component_type=comp.type,
                required=comp.required,
                default_component=comp.default_component,
                compatible_components=comp.compatible_components,
                chart=comp.chart.model_dump() if comp.chart else None,
                sort_order=idx,
            )

        self.session.commit()
        return template

    def update_custom_template(
        self,
        template_id: UUID,
        schema: CustomTemplateUpdateSchema,
        user_id: UUID,
    ) -> Template:
        """Update a custom user template.

        Args:
            template_id: Template UUID.
            schema: Partial update schema.
            user_id: Requesting user UUID.

        Returns:
            Updated Template instance.

        Raises:
            TemplateNotOwnedError: If user doesn't own the template.
            InvalidComponentTypeError: If a component has an invalid type.
            InvalidComponentError: If a component definition is invalid.
        """
        template = self.data_manager.get_user_template(template_id, user_id)
        if template is None:
            raise TemplateNotOwnedError(f"Template {template_id} not found or not owned by user")

        # Validate components if provided
        if schema.components is not None:
            self._validate_components(schema.components)
            if schema.deployment_order is not None:
                self._validate_deployment_order(schema.deployment_order, schema.components)

        # Build update kwargs from non-None fields
        update_kwargs: dict[str, Any] = {}
        if schema.display_name is not None:
            update_kwargs["display_name"] = schema.display_name
        if schema.version is not None:
            update_kwargs["version"] = schema.version
        if schema.description is not None:
            update_kwargs["description"] = schema.description
        if schema.category is not None:
            update_kwargs["category"] = schema.category
        if schema.tags is not None:
            update_kwargs["tags"] = schema.tags
        if schema.parameters is not None:
            update_kwargs["parameters"] = {name: param.model_dump() for name, param in schema.parameters.items()}
        if schema.resources is not None:
            update_kwargs["resources"] = schema.resources.model_dump()
        if schema.deployment_order is not None:
            update_kwargs["deployment_order"] = schema.deployment_order
        if schema.is_public is not None:
            update_kwargs["is_public"] = schema.is_public
        if schema.access is not None:
            update_kwargs["access"] = schema.access.model_dump()

        if update_kwargs:
            self.data_manager.update_template(template_id, **update_kwargs)

        # Replace components if provided
        if schema.components is not None:
            self.data_manager.delete_template_components(template_id)
            for idx, comp in enumerate(schema.components):
                self.data_manager.add_template_component(
                    template_id=template_id,
                    name=comp.name,
                    display_name=comp.display_name,
                    description=comp.description,
                    component_type=comp.type,
                    required=comp.required,
                    default_component=comp.default_component,
                    compatible_components=comp.compatible_components,
                    chart=comp.chart.model_dump() if comp.chart else None,
                    sort_order=idx,
                )

        self.session.commit()

        # Refresh to get updated data
        return self.data_manager.get_template(template_id)

    def delete_custom_template(
        self,
        template_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Delete a custom user template.

        Args:
            template_id: Template UUID.
            user_id: Requesting user UUID.

        Returns:
            True if deleted.

        Raises:
            TemplateNotOwnedError: If user doesn't own the template.
        """
        template = self.data_manager.get_user_template(template_id, user_id)
        if template is None:
            raise TemplateNotOwnedError(f"Template {template_id} not found or not owned by user")

        result = self.data_manager.delete_template(template_id)
        self.session.commit()
        return result

    def _validate_template(self, schema: CustomTemplateCreateSchema) -> None:
        """Validate a custom template creation schema."""
        self._validate_components(schema.components)
        if schema.deployment_order:
            self._validate_deployment_order(schema.deployment_order, schema.components)

    def _validate_components(self, components: list) -> None:
        """Validate component definitions."""
        for comp in components:
            if comp.type not in VALID_COMPONENT_TYPES:
                raise InvalidComponentTypeError(
                    f"Invalid component type '{comp.type}'. Valid types: {sorted(VALID_COMPONENT_TYPES)}"
                )
            for compat in comp.compatible_components:
                if not compat or not compat.strip():
                    raise InvalidComponentError(f"Component '{comp.name}' has empty compatible_components entry")

    def _validate_deployment_order(self, deployment_order: list[str], components: list) -> None:
        """Validate that deployment order references existing component names."""
        component_names = {c.name for c in components}
        for name in deployment_order:
            if name not in component_names:
                raise InvalidComponentError(
                    f"deployment_order references unknown component '{name}'. Available: {sorted(component_names)}"
                )

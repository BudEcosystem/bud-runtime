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

"""CRUD operations for Template models."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Template, TemplateComponent


class TemplateDataManager:
    """Data manager for Template CRUD operations."""

    def __init__(self, session: Session) -> None:
        """Initialize the data manager.

        Args:
            session: SQLAlchemy database session.
        """
        self.session = session

    def create_template(
        self,
        name: str,
        display_name: str,
        version: str,
        description: str,
        category: str | None = None,
        tags: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        resources: dict[str, Any] | None = None,
        deployment_order: list[str] | None = None,
        access: dict[str, Any] | None = None,
        source: str = "system",
        user_id: UUID | None = None,
        is_public: bool = True,
    ) -> Template:
        """Create a new template.

        Args:
            name: Template identifier.
            display_name: Human-readable name.
            version: Template version.
            description: Template description.
            category: Optional category for filtering.
            tags: Optional list of tags.
            parameters: Optional parameter definitions.
            resources: Optional resource requirements.
            deployment_order: Optional deployment order list.
            access: Optional access mode configuration (UI/API).
            source: Template source ('system' or 'user').
            user_id: Optional owner user UUID.
            is_public: Whether the template is publicly visible.

        Returns:
            Created Template instance.
        """
        template = Template(
            name=name,
            display_name=display_name,
            version=version,
            description=description,
            category=category,
            tags=tags or [],
            parameters=parameters or {},
            resources=resources,
            deployment_order=deployment_order or [],
            access=access,
            source=source,
            user_id=user_id,
            is_public=is_public,
        )
        self.session.add(template)
        self.session.flush()
        return template

    def get_template(self, template_id: UUID) -> Template | None:
        """Get a template by ID.

        Args:
            template_id: Template UUID.

        Returns:
            Template if found, None otherwise.
        """
        return self.session.get(Template, template_id)

    def get_template_by_name(self, name: str, user_id: UUID | None = None) -> Template | None:
        """Get a template by name.

        When user_id is provided, prefers the user's own template over
        a system template with the same name.

        Args:
            name: Template name.
            user_id: Optional requesting user UUID for scoped lookup.

        Returns:
            Template if found, None otherwise.
        """
        stmt = select(Template).where(Template.name == name)

        if user_id is not None:
            # Also filter for visibility: public or owned by user
            stmt = stmt.where(
                or_(Template.is_public == True, Template.user_id == user_id)  # noqa: E712
            )
            # Prefer user's own template (user_id match sorts first)
            stmt = stmt.order_by((Template.user_id == user_id).desc())

        result = self.session.execute(stmt).scalars().first()
        return result

    def list_templates(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        tag: str | None = None,
        user_id: UUID | None = None,
        source: str | None = None,
    ) -> Sequence[Template]:
        """List templates with optional filtering and pagination.

        When user_id is provided, returns public templates plus the user's
        own private templates. Without user_id, returns only public templates.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            category: Optional category filter.
            tag: Optional tag filter.
            user_id: Optional requesting user UUID for visibility filtering.
            source: Optional source filter ('system' or 'user').

        Returns:
            List of templates matching the criteria.
        """
        stmt = select(Template)

        # Visibility filtering
        if user_id is not None:
            stmt = stmt.where(
                or_(Template.is_public == True, Template.user_id == user_id)  # noqa: E712
            )
        else:
            stmt = stmt.where(Template.is_public == True)  # noqa: E712

        if source:
            stmt = stmt.where(Template.source == source)

        if category:
            stmt = stmt.where(Template.category == category)

        if tag:
            stmt = stmt.where(Template.tags.contains([tag]))

        stmt = stmt.order_by(Template.name)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        return self.session.execute(stmt).scalars().all()

    def count_templates(
        self,
        category: str | None = None,
        tag: str | None = None,
        user_id: UUID | None = None,
        source: str | None = None,
    ) -> int:
        """Count templates matching the criteria.

        Args:
            category: Optional category filter.
            tag: Optional tag filter.
            user_id: Optional requesting user UUID for visibility filtering.
            source: Optional source filter ('system' or 'user').

        Returns:
            Count of matching templates.
        """
        from sqlalchemy import func

        stmt = select(func.count(Template.id))

        # Visibility filtering
        if user_id is not None:
            stmt = stmt.where(
                or_(Template.is_public == True, Template.user_id == user_id)  # noqa: E712
            )
        else:
            stmt = stmt.where(Template.is_public == True)  # noqa: E712

        if source:
            stmt = stmt.where(Template.source == source)

        if category:
            stmt = stmt.where(Template.category == category)

        if tag:
            stmt = stmt.where(Template.tags.contains([tag]))

        result = self.session.execute(stmt).scalar()
        return result or 0

    def update_template(self, template_id: UUID, **kwargs: Any) -> Template | None:
        """Update a template's attributes.

        Args:
            template_id: Template UUID.
            **kwargs: Attributes to update.

        Returns:
            Updated Template if found, None otherwise.
        """
        template = self.get_template(template_id)
        if template is None:
            return None

        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)

        self.session.flush()
        return template

    def delete_template(self, template_id: UUID) -> bool:
        """Delete a template.

        Args:
            template_id: Template UUID.

        Returns:
            True if deleted, False if not found.
        """
        template = self.get_template(template_id)
        if template is None:
            return False

        self.session.delete(template)
        self.session.flush()
        return True

    def add_template_component(
        self,
        template_id: UUID,
        name: str,
        display_name: str,
        component_type: str,
        required: bool,
        sort_order: int,
        description: str | None = None,
        default_component: str | None = None,
        compatible_components: list[str] | None = None,
        chart: dict[str, Any] | None = None,
    ) -> TemplateComponent:
        """Add a component to a template.

        Args:
            template_id: Parent template UUID.
            name: Component identifier.
            display_name: Human-readable name.
            component_type: Type of component.
            required: Whether the component is required.
            sort_order: Display order.
            description: Optional description.
            default_component: Optional default component name.
            compatible_components: Optional list of compatible components.
            chart: Optional Helm chart configuration (for helm-type components).

        Returns:
            Created TemplateComponent instance.
        """
        component = TemplateComponent(
            template_id=template_id,
            name=name,
            display_name=display_name,
            description=description,
            component_type=component_type,
            required=required,
            default_component=default_component,
            compatible_components=compatible_components or [],
            chart=chart,
            sort_order=sort_order,
        )
        self.session.add(component)
        self.session.flush()
        return component

    def get_template_components(self, template_id: UUID) -> Sequence[TemplateComponent]:
        """Get all components for a template.

        Args:
            template_id: Template UUID.

        Returns:
            List of template components ordered by sort_order.
        """
        stmt = (
            select(TemplateComponent)
            .where(TemplateComponent.template_id == template_id)
            .order_by(TemplateComponent.sort_order)
        )
        return self.session.execute(stmt).scalars().all()

    def delete_template_components(self, template_id: UUID) -> int:
        """Delete all components for a template.

        Args:
            template_id: Template UUID.

        Returns:
            Number of components deleted.
        """
        from sqlalchemy import delete

        stmt = delete(TemplateComponent).where(TemplateComponent.template_id == template_id)
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount

    def get_user_template(self, template_id: UUID, user_id: UUID) -> Template | None:
        """Get a template owned by a specific user.

        Args:
            template_id: Template UUID.
            user_id: Owner user UUID.

        Returns:
            Template if found and owned by user, None otherwise.
        """
        stmt = select(Template).where(
            Template.id == template_id,
            Template.user_id == user_id,
            Template.source == "user",
        )
        return self.session.execute(stmt).scalar_one_or_none()

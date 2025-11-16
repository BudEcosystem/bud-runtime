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

"""The crud package, containing essential business logic, services, and routing configurations for the model ops."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, asc, delete, desc, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError

from budapp.commons import logging
from budapp.commons.constants import (
    BaseModelRelationEnum,
    CloudModelStatusEnum,
    EndpointStatusEnum,
    ModalityEnum,
    ModelEndpointEnum,
    ModelProviderTypeEnum,
    ModelStatusEnum,
)
from budapp.commons.db_utils import DataManagerUtils
from budapp.commons.exceptions import DatabaseException
from budapp.endpoint_ops.models import DeploymentPricing, Endpoint
from budapp.model_ops.models import CloudModel, Model, PaperPublished
from budapp.model_ops.models import Provider as ProviderModel
from budapp.model_ops.models import QuantizationMethod as QuantizationMethodModel


logger = logging.get_logger(__name__)


class ProviderDataManager(DataManagerUtils):
    """Data manager for the Provider model."""

    async def get_all_providers_by_type(self, provider_types: List[str]) -> List[ProviderModel]:
        """Get all providers from the database."""
        stmt = select(ProviderModel).filter(ProviderModel.type.in_(provider_types))
        return self.scalars_all(stmt)

    async def get_all_providers(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> Tuple[List[ProviderModel], int]:
        """Get all providers from the database."""
        # Handle capabilities filter separately for array containment
        capabilities_filter = None
        if "capabilities" in filters:
            if not isinstance(filters["capabilities"], list):
                filters["capabilities"] = [filters["capabilities"]]
            capabilities_filter = filters.pop("capabilities")

        await self.validate_fields(ProviderModel, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(ProviderModel, filters)
            stmt = select(ProviderModel).filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(ProviderModel).filter(and_(*search_conditions))
        else:
            stmt = select(ProviderModel).filter_by(**filters)
            count_stmt = select(func.count()).select_from(ProviderModel).filter_by(**filters)

        # Apply capabilities filter using array containment operator
        if capabilities_filter:
            stmt = stmt.filter(ProviderModel.capabilities.contains(capabilities_filter))
            count_stmt = count_stmt.filter(ProviderModel.capabilities.contains(capabilities_filter))

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(ProviderModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    async def soft_delete_non_supported_providers(self, provider_types: List[str]) -> None:
        """Soft delete providers by setting is_active to False.

        Args:
            provider_types (List[str]): List of provider types to keep active.

        Returns:
            None
        """
        try:
            stmt = update(ProviderModel).where(~ProviderModel.type.in_(provider_types)).values(is_active=False)
            self.session.execute(stmt)
            self.session.commit()
        except SQLAlchemyError as e:
            logger.exception(f"Failed to soft delete non-supported providers: {e}")
            raise DatabaseException("Unable to soft delete non-supported providers") from e


class PaperPublishedDataManager(DataManagerUtils):
    """Data manager for the PaperPublished model."""

    async def delete_paper_by_urls(self, model_id: UUID, paper_urls: Optional[Dict[str, List[Any]]] = None) -> None:
        """Delete multiple model instances based on the model id and paper urls."""
        try:
            # Build the query with filters
            query = self.session.query(PaperPublished).filter_by(**{"model_id": model_id})

            # Add paper_urls
            if paper_urls:
                for key, values in paper_urls.items():
                    query = query.filter(getattr(PaperPublished, key).in_(values))

            # Delete records
            query.delete(synchronize_session=False)

            # Commit the transaction
            self.session.commit()
            logger.debug(f"Successfully deleted records from {PaperPublished.__name__} with paper_urls: {paper_urls}")
        except (Exception, SQLAlchemyError) as e:
            # Rollback the transaction on error
            self.session.rollback()
            logger.exception(f"Failed to delete records from {PaperPublished.__name__}: {e}")
            raise DatabaseException(f"Unable to delete records from {PaperPublished.__name__}") from e


class ModelDataManager(DataManagerUtils):
    """Data manager for the Model model."""

    async def list_model_tags(
        self,
        search_value: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Model], int]:
        """Search tags by name with pagination, or fetch all tags if no search value is provided."""
        # Ensure only valid JSON arrays are processed
        tags_subquery = (
            select(func.jsonb_array_elements(Model.tags).label("tag"))
            .where(Model.status == ModelStatusEnum.ACTIVE)
            .where(Model.tags.is_not(None))  # Exclude null tags
            .where(func.jsonb_typeof(Model.tags) == "array")  # Ensure tags is a JSON array
        ).subquery()

        # Extract name and color as jsonb
        distinct_tags_query = (
            select(
                func.jsonb_extract_path_text(tags_subquery.c.tag, "name").label("name"),
                func.jsonb_extract_path_text(tags_subquery.c.tag, "color").label("color"),
            )
            .where(func.jsonb_typeof(tags_subquery.c.tag) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "color").is_not(None))  # Valid colors
        ).subquery()

        # Apply DISTINCT to get unique tags by name, selecting the first color
        distinct_on_name_query = (
            select(
                distinct_tags_query.c.name,
                distinct_tags_query.c.color,
            )
            .distinct(distinct_tags_query.c.name)
            .order_by(distinct_tags_query.c.name, distinct_tags_query.c.color)  # Ensure deterministic order
        )

        # Apply search filter if provided
        if search_value:
            distinct_on_name_query = distinct_on_name_query.where(distinct_tags_query.c.name.ilike(f"{search_value}%"))

        # Add pagination
        distinct_tags_with_pagination = distinct_on_name_query.offset(offset).limit(limit)

        # Execute the paginated query
        tags_result = self.session.execute(distinct_tags_with_pagination)

        # Count total distinct tag names
        distinct_count_query = (
            select(func.count(func.distinct(distinct_tags_query.c.name)))
            .where(func.jsonb_typeof(tags_subquery.c.tag) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tags_subquery.c.tag, "color").is_not(None))  # Valid colors
        )

        # Apply search filter to the count query
        if search_value:
            distinct_count_query = distinct_count_query.where(
                func.jsonb_extract_path_text(tags_subquery.c.tag, "name").ilike(f"{search_value}%")
            )

        # Execute the count query
        distinct_count_result = self.session.execute(distinct_count_query)
        total_count = distinct_count_result.scalar()

        return tags_result, total_count

    async def list_model_tasks(
        self,
        search_value: str = "",
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[Model], int]:
        """Search tasks by name with pagination, or fetch all tasks if no search value is provided."""
        # Ensure only valid JSON arrays are processed
        tasks_subquery = (
            select(func.jsonb_array_elements(Model.tasks).label("task"))
            .where(Model.status == ModelStatusEnum.ACTIVE)
            .where(Model.tasks.is_not(None))  # Exclude null tasks
            .where(func.jsonb_typeof(Model.tasks) == "array")  # Ensure tasks is a JSON array
        ).subquery()

        # Extract name and color as jsonb
        distinct_tasks_query = (
            select(
                func.jsonb_extract_path_text(tasks_subquery.c.task, "name").label("name"),
                func.jsonb_extract_path_text(tasks_subquery.c.task, "color").label("color"),
            )
            .where(func.jsonb_typeof(tasks_subquery.c.task) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tasks_subquery.c.task, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tasks_subquery.c.task, "color").is_not(None))  # Valid colors
        ).subquery()

        # Apply DISTINCT to get unique tasks by name, selecting the first color
        distinct_on_name_query = (
            select(
                distinct_tasks_query.c.name,
                distinct_tasks_query.c.color,
            )
            .distinct(distinct_tasks_query.c.name)
            .order_by(distinct_tasks_query.c.name, distinct_tasks_query.c.color)  # Ensure deterministic order
        )

        # Apply search filter if provided
        if search_value:
            distinct_on_name_query = distinct_on_name_query.where(
                distinct_tasks_query.c.name.ilike(f"{search_value}%")
            )

        # Add pagination
        distinct_tasks_with_pagination = distinct_on_name_query.offset(offset).limit(limit)

        # Execute the paginated query
        tasks_result = self.session.execute(distinct_tasks_with_pagination)

        # Count total distinct task names
        distinct_count_query = (
            select(func.count(func.distinct(distinct_tasks_query.c.name)))
            .where(func.jsonb_typeof(tasks_subquery.c.task) == "object")  # Ensure valid JSONB objects
            .where(func.jsonb_extract_path_text(tasks_subquery.c.task, "name").is_not(None))  # Valid names
            .where(func.jsonb_extract_path_text(tasks_subquery.c.task, "color").is_not(None))  # Valid colors
        )

        # Apply search filter to the count query
        if search_value:
            distinct_count_query = distinct_count_query.where(
                func.jsonb_extract_path_text(tasks_subquery.c.task, "name").ilike(f"{search_value}%")
            )

        # Execute the count query
        distinct_count_result = self.session.execute(distinct_count_query)
        total_count = distinct_count_result.scalar()

        return tasks_result, total_count

    async def get_all_models(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Model], int]:
        """List all models in the database."""
        # Convert base_model to list if it is a string
        base_model = filters.pop("base_model", None)
        base_model = [base_model] if base_model else None

        # Extract base_model_relation for explicit handling
        base_model_relation = filters.pop("base_model_relation", None)

        # Extract exclude_adapters flag
        exclude_adapters = filters.pop("exclude_adapters", False)

        # Tags and tasks are not filterable
        # Also remove from filters dict
        explicit_conditions = []
        json_filters = {"tags": filters.pop("tags", []), "tasks": filters.pop("tasks", [])}
        explicit_filters = {
            "modality": filters.pop("modality", []),
            "author": filters.pop("author", []),
            "model_size_min": filters.pop("model_size_min", None),
            "model_size_max": filters.pop("model_size_max", None),
            "base_model": base_model,
            "base_model_relation": base_model_relation,
            "exclude_adapters": exclude_adapters,
        }

        # Validate the remaining filters
        await self.validate_fields(Model, filters)

        if json_filters["tags"]:
            # Either TagA or TagB exist in tag field
            tag_conditions = or_(
                *[Model.tags.cast(JSONB).contains([{"name": tag_name}]) for tag_name in json_filters["tags"]]
            )
            explicit_conditions.append(tag_conditions)

        if json_filters["tasks"]:
            # Either TaskA or TaskB exist in task field
            task_conditions = or_(
                *[Model.tasks.cast(JSONB).contains([{"name": task_name}]) for task_name in json_filters["tasks"]]
            )
            explicit_conditions.append(task_conditions)

        if explicit_filters["modality"]:
            # Check any of modality present in the field
            modality_condition = Model.modality.overlap(explicit_filters["modality"])
            explicit_conditions.append(modality_condition)

        if explicit_filters["author"]:
            # Check any of author present in the field
            author_condition = Model.author.in_(explicit_filters["author"])
            explicit_conditions.append(author_condition)

        if explicit_filters["base_model"]:
            # Check any of base_model present in the field
            base_model_condition = Model.base_model.contains(explicit_filters["base_model"])
            explicit_conditions.append(base_model_condition)

        if explicit_filters["model_size_min"] is not None or explicit_filters["model_size_max"] is not None:
            # Add model size range condition
            size_conditions = []
            if explicit_filters["model_size_min"] is not None:
                size_conditions.append(Model.model_size >= explicit_filters["model_size_min"])
            if explicit_filters["model_size_max"] is not None:
                size_conditions.append(Model.model_size <= explicit_filters["model_size_max"])
            size_condition = and_(*size_conditions)
            explicit_conditions.append(size_condition)

        if explicit_filters["base_model_relation"] is not None:
            # Add base_model_relation filter
            base_model_relation_condition = Model.base_model_relation == explicit_filters["base_model_relation"]
            explicit_conditions.append(base_model_relation_condition)

        if explicit_filters["exclude_adapters"]:
            # Exclude adapter-type models (used in deploy flow)
            # Adapters should only be added via the separate "Add Adapter" flow
            exclude_adapter_condition = Model.base_model_relation != BaseModelRelationEnum.ADAPTER
            explicit_conditions.append(exclude_adapter_condition)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(Model, filters)
            stmt = (
                select(
                    Model,
                    func.count(Endpoint.id)
                    .filter(Endpoint.status != EndpointStatusEnum.DELETED)
                    .label("endpoints_count"),
                )
                .select_from(Model)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(Model.status == ModelStatusEnum.ACTIVE)
                .outerjoin(Endpoint, Endpoint.model_id == Model.id)
                .group_by(Model.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(Model)
                .filter(or_(*search_conditions, *explicit_conditions))
                .filter(Model.status == ModelStatusEnum.ACTIVE)
            )
        else:
            stmt = (
                select(
                    Model,
                    func.count(Endpoint.id)
                    .filter(Endpoint.status != EndpointStatusEnum.DELETED)
                    .label("endpoints_count"),
                )
                .select_from(Model)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(Model.status == ModelStatusEnum.ACTIVE)
                .outerjoin(Endpoint, Endpoint.model_id == Model.id)
                .group_by(Model.id)
            )
            count_stmt = (
                select(func.count())
                .select_from(Model)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(Model.status == ModelStatusEnum.ACTIVE)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Model, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def list_all_model_authors(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> Tuple[List[Model], int]:
        """Get all authors from the database."""
        await self.validate_fields(Model, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(Model, filters)
            stmt = (
                select(Model)
                .distinct(Model.author)
                .filter(and_(*search_conditions, Model.author.is_not(None), Model.status == ModelStatusEnum.ACTIVE))
            )
            count_stmt = select(func.count().label("count")).select_from(
                select(Model.author)
                .distinct()
                .filter(and_(*search_conditions, Model.author.is_not(None), Model.status == ModelStatusEnum.ACTIVE))
                .alias("distinct_authors")
            )
        else:
            stmt = (
                select(Model)
                .distinct(Model.author)
                .filter_by(**filters)
                .filter(Model.author.is_not(None), Model.status == ModelStatusEnum.ACTIVE)
            )
            count_stmt = select(func.count().label("count")).select_from(
                select(Model.author)
                .distinct()
                .filter(Model.author.is_not(None), Model.status == ModelStatusEnum.ACTIVE)
                .alias("distinct_authors")
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Model, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    async def get_model_tree_count(self, uri: str) -> List[dict]:
        """Get the model tree count."""
        stmt = (
            select(Model.base_model_relation, func.count(Model.id).label("count"))
            .filter(
                Model.base_model.contains([uri]),
                Model.status == ModelStatusEnum.ACTIVE,
                Model.base_model_relation.is_not(None),
            )
            .group_by(Model.base_model_relation)
        )

        return self.execute_all(stmt)

    async def get_models_by_uris(self, uris: List[str]) -> List[Model]:
        """Get models by uris."""
        stmt = select(Model).filter(Model.uri.in_(uris), Model.status == ModelStatusEnum.ACTIVE)
        return self.scalars_all(stmt)

    async def get_stale_model_recommendation(self, older_than: datetime) -> Optional[Model]:
        """Get model that needs cluster recommendation update.

        Args:
            older_than: datetime to compare against recommended_cluster_sync_at

        Returns:
            Model if found and needs update (stale or never synced), None otherwise
        """
        query = (
            select(Model)
            .where(
                and_(
                    Model.status == ModelStatusEnum.ACTIVE,
                    or_(
                        Model.recommended_cluster_sync_at.is_(None),  # Never synced
                        Model.recommended_cluster_sync_at < older_than,
                    ),
                )
            )
            .order_by(
                Model.recommended_cluster_sync_at.asc().nulls_first()  # Prioritize never synced models
            )
            .limit(1)
        )

        result = self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_deprecated_cloud_models(self, uris: List[str]) -> List[Model]:
        """Get deprecated cloud models."""
        stmt = select(Model).where(~Model.uri.in_(uris), Model.provider_type == ModelProviderTypeEnum.CLOUD_MODEL)
        return self.scalars_all(stmt)

    async def soft_delete_deprecated_models(self, ids: List[str]) -> None:
        """Soft delete deprecated models by setting is_active to False.

        Args:
            ids (List[str]): List of ids to soft delete.

        Returns:
            None
        """
        try:
            stmt = update(Model).where(Model.id.in_(ids)).values(status=ModelStatusEnum.DELETED)
            self.session.execute(stmt)
            self.session.commit()
        except SQLAlchemyError as e:
            logger.exception(f"Failed to soft delete deprecated models: {e}")
            raise DatabaseException("Unable to soft delete deprecated models") from e

    async def get_published_models_catalog(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search_term: Optional[str] = None,
    ) -> Tuple[List[Any], int]:
        """Get published models for catalog with pricing information."""
        # Base query joining Model, Endpoint, DeploymentPricing, and Provider
        base_query = (
            select(
                Model,
                Endpoint,
                DeploymentPricing.input_cost,
                DeploymentPricing.output_cost,
                DeploymentPricing.currency,
                DeploymentPricing.per_tokens,
                ProviderModel.icon,
            )
            .join(Endpoint, Endpoint.model_id == Model.id)
            .outerjoin(
                DeploymentPricing,
                and_(DeploymentPricing.endpoint_id == Endpoint.id, DeploymentPricing.is_current),
            )
            .outerjoin(ProviderModel, ProviderModel.id == Model.provider_id)
            .filter(
                Endpoint.is_published,
                Endpoint.status != EndpointStatusEnum.DELETED,
                Model.status != ModelStatusEnum.DELETED,
            )
        )

        # Apply filters
        if "modality" in filters and filters["modality"]:
            # Handle multiple modalities with OR condition
            modality_conditions = []
            for modality in filters["modality"]:
                modality_conditions.append(Model.modality.contains([modality]))
            base_query = base_query.filter(or_(*modality_conditions))

        if "status" in filters and filters["status"]:
            base_query = base_query.filter(Model.status == filters["status"])

        # Apply search if provided
        if search_term:
            ts_query = func.plainto_tsquery("english", search_term)
            search_conditions = or_(
                func.to_tsvector("english", Model.name).op("@@")(ts_query),
                func.to_tsvector("english", func.coalesce(Model.description, "")).op("@@")(ts_query),
                func.array_to_string(Model.use_cases, " ").ilike(f"%{search_term}%"),
            )
            base_query = base_query.filter(search_conditions)

        # Count query
        count_query = select(func.count(func.distinct(Model.id))).select_from(base_query.subquery())
        count = self.execute_scalar(count_query)

        # Apply ordering
        if order_by:
            for field, direction in order_by:
                if field == "published_date":
                    order_func = desc if direction == "desc" else asc
                    base_query = base_query.order_by(order_func(Endpoint.published_date))
                elif field == "name":
                    order_func = desc if direction == "desc" else asc
                    base_query = base_query.order_by(order_func(Model.name))
                elif field == "created_at":
                    order_func = desc if direction == "desc" else asc
                    base_query = base_query.order_by(order_func(Model.created_at))
        else:
            # Default ordering by published date desc
            base_query = base_query.order_by(desc(Endpoint.published_date))

        # Apply pagination
        base_query = base_query.limit(limit).offset(offset)

        # Execute query
        result = self.session.execute(base_query)
        return result.all(), count

    async def get_published_model_detail(self, endpoint_id: UUID) -> Optional[Any]:
        """Get detailed information for a published model by endpoint ID."""
        query = (
            select(
                Model,
                Endpoint,
                DeploymentPricing.input_cost,
                DeploymentPricing.output_cost,
                DeploymentPricing.currency,
                DeploymentPricing.per_tokens,
                ProviderModel.icon,
            )
            .join(Endpoint, Endpoint.model_id == Model.id)
            .outerjoin(
                DeploymentPricing,
                and_(DeploymentPricing.endpoint_id == Endpoint.id, DeploymentPricing.is_current),
            )
            .outerjoin(ProviderModel, ProviderModel.id == Model.provider_id)
            .filter(
                Endpoint.id == endpoint_id,
                Endpoint.is_published,
                Endpoint.status != EndpointStatusEnum.DELETED,
                Model.status != ModelStatusEnum.DELETED,
            )
        )

        result = self.session.execute(query)
        return result.first()


class CloudModelDataManager(DataManagerUtils):
    """Data manager for the CloudModel model."""

    async def get_all_cloud_models_by_source_uris(self, provider: str, uris: List[str]) -> List[CloudModel]:
        """Get all cloud models from the database."""
        stmt = select(CloudModel).filter(CloudModel.uri.in_(uris), CloudModel.source == provider)
        return self.scalars_all(stmt)

    async def get_all_cloud_models(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> Tuple[List[CloudModel], int]:
        """Get all cloud models from the database."""
        # Tags and tasks are not filterable
        # Also remove from filters dict
        explicit_conditions = []
        json_filters = {"tags": filters.pop("tags", []), "tasks": filters.pop("tasks", [])}
        explicit_filters = {
            "modality": filters.pop("modality", []),
            "supported_endpoints": filters.pop("supported_endpoints", []),
            "author": filters.pop("author", []),
            "model_size_min": filters.pop("model_size_min", None),
            "model_size_max": filters.pop("model_size_max", None),
        }

        # Validate the remaining filters
        await self.validate_fields(CloudModel, filters)

        if json_filters["tags"]:
            # Either TagA or TagB exist in tag field
            tag_conditions = or_(
                *[CloudModel.tags.cast(JSONB).contains([{"name": tag_name}]) for tag_name in json_filters["tags"]]
            )
            explicit_conditions.append(tag_conditions)

        if json_filters["tasks"]:
            # Either TaskA or TaskB exist in task field
            task_conditions = or_(
                *[CloudModel.tasks.cast(JSONB).contains([{"name": task_name}]) for task_name in json_filters["tasks"]]
            )
            explicit_conditions.append(task_conditions)

        if explicit_filters["modality"]:
            requested_modalities = [
                modality.value if isinstance(modality, ModalityEnum) else modality
                for modality in explicit_filters["modality"]
            ]
            modality_condition = CloudModel.modality.contains(requested_modalities)
            explicit_conditions.append(modality_condition)

        if explicit_filters["supported_endpoints"]:
            requested_endpoints = [
                endpoint.value if isinstance(endpoint, ModelEndpointEnum) else endpoint
                for endpoint in explicit_filters["supported_endpoints"]
            ]
            endpoint_condition = CloudModel.supported_endpoints.contains(requested_endpoints)
            explicit_conditions.append(endpoint_condition)

        if explicit_filters["author"]:
            # Check any of author present in the field
            author_condition = CloudModel.author.in_(explicit_filters["author"])
            explicit_conditions.append(author_condition)

        if explicit_filters["model_size_min"] is not None or explicit_filters["model_size_max"] is not None:
            # Add model size range condition
            size_conditions = []
            if explicit_filters["model_size_min"] is not None:
                size_conditions.append(CloudModel.model_size >= explicit_filters["model_size_min"])
            if explicit_filters["model_size_max"] is not None:
                size_conditions.append(CloudModel.model_size <= explicit_filters["model_size_max"])
            size_condition = and_(*size_conditions)
            explicit_conditions.append(size_condition)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(CloudModel, filters)
            stmt = (
                select(CloudModel)
                .filter(and_(or_(*search_conditions), CloudModel.status == CloudModelStatusEnum.ACTIVE))
                .where(or_(*explicit_conditions))
            )
            count_stmt = (
                select(func.count())
                .select_from(CloudModel)
                .filter(and_(or_(*search_conditions), CloudModel.status == CloudModelStatusEnum.ACTIVE))
                .where(or_(*explicit_conditions))
            )
        else:
            stmt = (
                select(CloudModel)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(CloudModel.status == CloudModelStatusEnum.ACTIVE)
            )
            count_stmt = (
                select(func.count())
                .select_from(CloudModel)
                .filter_by(**filters)
                .where(and_(*explicit_conditions))
                .filter(CloudModel.status == CloudModelStatusEnum.ACTIVE)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(CloudModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

    async def get_all_recommended_tags(
        self,
        offset: int = 0,
        limit: int = 10,
    ) -> Tuple[List[CloudModel], int]:
        """Get all recommended tags from the database."""
        stmt = (
            (
                select(
                    func.jsonb_array_elements(CloudModel.tags).op("->>")("name").label("name"),
                    func.jsonb_array_elements(CloudModel.tags).op("->>")("color").label("color"),
                    func.count().label("count"),
                )
                .select_from(CloudModel)
                .where(CloudModel.tags.is_not(None), CloudModel.status == CloudModelStatusEnum.ACTIVE)
                .group_by(
                    func.jsonb_array_elements(CloudModel.tags).op("->>")("name"),
                    func.jsonb_array_elements(CloudModel.tags).op("->>")("color"),
                )
            )
            .union_all(
                select(
                    func.jsonb_array_elements(CloudModel.tasks).op("->>")("name").label("name"),
                    func.jsonb_array_elements(CloudModel.tasks).op("->>")("color").label("color"),
                    func.count().label("count"),
                )
                .select_from(CloudModel)
                .where(CloudModel.tasks.is_not(None))
                .group_by(
                    func.jsonb_array_elements(CloudModel.tasks).op("->>")("name"),
                    func.jsonb_array_elements(CloudModel.tasks).op("->>")("color"),
                )
            )
            .order_by(desc("count"), "name")
            .offset(offset)
            .limit(limit)
        )

        count_stmt = select(func.count()).select_from(stmt)

        count = self.execute_scalar(count_stmt)

        result = self.execute_all(stmt)

        return result, count

    async def remove_non_supported_cloud_models(self, uris: List[str]) -> None:
        """Remove cloud models by setting is_active to False.

        Args:
            uris (List[str]): List of uris to keep active.

        Returns:
            None
        """
        try:
            stmt = delete(CloudModel).where(~CloudModel.uri.in_(uris))
            self.session.execute(stmt)
            self.session.commit()
        except SQLAlchemyError as e:
            logger.exception(f"Failed to remove non-supported cloud models: {e}")
            raise DatabaseException("Unable to remove non-supported cloud models") from e


class ModelLicensesDataManager(DataManagerUtils):
    """Data manager for the ModelLicenses model."""

    pass


class ModelSecurityScanResultDataManager(DataManagerUtils):
    """Data manager for the ModelSecurityScanResult model."""

    pass


class QuantizationMethodDataManager(DataManagerUtils):
    """Data manager for the QuantizationMethod model."""

    async def get_all_quantization_methods(
        self,
        offset: int,
        limit: int,
        filters: Dict[str, Any] = {},
        order_by: List[Tuple[str, str]] = [],
        search: bool = False,
    ) -> Tuple[List[QuantizationMethodModel], int]:
        """List all quantization methods in the database."""
        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(QuantizationMethodModel, filters)
            stmt = select(
                QuantizationMethodModel,
            ).filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(QuantizationMethodModel).filter(or_(*search_conditions))
        else:
            stmt = select(
                QuantizationMethodModel,
            ).filter_by(**filters)
            count_stmt = select(func.count()).select_from(QuantizationMethodModel).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(QuantizationMethodModel, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)
        logger.info(f"result: {result}")
        return result, count

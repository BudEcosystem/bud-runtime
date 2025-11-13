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

"""The crud package, containing essential business logic, services, and routing configurations for the project ops."""

from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from fastapi import status
from fastapi.exceptions import HTTPException
from sqlalchemy import Row, Sequence, and_, case, cast, distinct, func, inspect, or_, select, text
from sqlalchemy import String as SqlAlchemyString
from sqlalchemy.orm import aliased
from sqlalchemy.sql import literal_column

from budapp.commons import logging
from budapp.commons.db_utils import DataManagerUtils

from ..commons.constants import EndpointStatusEnum, ProjectStatusEnum, UserStatusEnum
from ..commons.exceptions import ClientException
from ..credential_ops.models import Credential
from ..endpoint_ops.models import Endpoint
from ..permissions.models import Permission, ProjectPermission
from ..user_ops.models import User
from .models import Project, project_user_association


logger = logging.get_logger(__name__)


class ProjectDataManager(DataManagerUtils):
    """Data manager for the Project model."""

    async def create_project(self, project: Project) -> Project:
        """Create a new project in the database."""
        return await self.insert_one(project)

    def get_unique_user_count_in_all_projects(self) -> int:
        """Get the count of unique users across all active projects.

        Returns:
            int: Count of unique users in all active projects.
        """
        unique_users_stmt = (
            select(func.count(distinct(project_user_association.c.user_id)))
            .join(Project, project_user_association.c.project_id == Project.id)
            .join(User, project_user_association.c.user_id == User.id)
            .where(
                Project.status == ProjectStatusEnum.ACTIVE,
                User.status != UserStatusEnum.DELETED,
            )
        )
        return self.scalar_one_or_none(unique_users_stmt) or 0

    async def get_all_active_project_ids(self) -> List[UUID]:
        """Get all active project ids.

        Returns:
            List[UUID]: List of active project ids.
        """
        stmt = select(Project.id).where(Project.status == ProjectStatusEnum.ACTIVE)
        return self.scalars_all(stmt)

    async def retrieve_project_by_fields(
        self,
        fields: Dict,
        missing_ok: bool = False,
        case_sensitive: bool = True,
    ) -> Optional[Project]:
        """Retrieve project by fields."""
        await self.validate_fields(Project, fields)

        if case_sensitive:
            stmt = select(Project).filter_by(**fields)
        else:
            conditions = []
            for field_name, value in fields.items():
                field = getattr(Project, field_name)
                if isinstance(field.type, SqlAlchemyString):
                    conditions.append(func.lower(cast(field, SqlAlchemyString)) == func.lower(value))
                else:
                    conditions.append(field == value)
            stmt = select(Project).filter(*conditions)

        db_project = self.scalar_one_or_none(stmt)

        if not missing_ok and db_project is None:
            logger.info("Project not found in database")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        return db_project if db_project else None

    async def get_active_user_ids_in_project(self, project_id: UUID) -> List[User]:
        """Get all active users in a project."""
        stmt = (
            select(User.id)
            .select_from(Project)
            .filter_by(id=project_id)
            .outerjoin(
                project_user_association,
                Project.id == project_user_association.c.project_id,
            )
            .outerjoin(User, project_user_association.c.user_id == User.id)
            .filter_by(status=UserStatusEnum.ACTIVE)
        )

        return self.scalars_all(stmt)

    async def search_tags_by_name(self, search_value: str, offset: int, limit: int) -> Tuple[List[dict], int]:
        """Search tags in the database filtered by the tag name with pagination."""
        # Subquery to extract individual tags
        subquery = (
            select(func.jsonb_array_elements(Project.tags).label("tag"))
            .where(Project.status == ProjectStatusEnum.ACTIVE)
            .where(Project.tags.isnot(None))
        ).subquery()

        # Group by 'name' to ensure only one instance of each tag (e.g., first occurrence)
        final_query = (
            select(
                func.jsonb_extract_path_text(subquery.c.tag, "name").label("name"),
                func.min(func.jsonb_extract_path_text(subquery.c.tag, "color")).label("color"),
            )
            .where(func.jsonb_extract_path_text(subquery.c.tag, "name").ilike(f"{search_value}%"))
            .group_by("name")
            .order_by("name")
            .offset(offset)  # Apply offset for pagination
            .limit(limit)  # Apply limit for pagination
        )

        # Execute the query
        results = self.execute_all(final_query)

        # Format the results into a list of unique tags
        tags = [{"name": res.name, "color": res.color} for res in results] if results else []

        # Count of the total number of filtered results (without pagination)
        total_query = select(func.count(func.distinct(func.jsonb_extract_path_text(subquery.c.tag, "name")))).where(
            func.jsonb_extract_path_text(subquery.c.tag, "name").ilike(f"{search_value}%")
        )
        total_count = self.execute_scalar(total_query)

        return tags, total_count

    async def get_all_tags(self) -> Tuple[List, int]:
        """Get all tags in the database."""
        distinct_tags_stmt = (
            select(distinct(func.jsonb_array_elements(Project.tags)))
            .filter(Project.status == ProjectStatusEnum.ACTIVE)
            .filter(Project.tags.isnot(None))
            .alias("distinct_tags")
        )
        count_stmt = select(func.count()).select_from(distinct_tags_stmt)
        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        subquery = (
            select(distinct(func.jsonb_array_elements(Project.tags)).label("tag"))
            .where(Project.status == ProjectStatusEnum.ACTIVE)
            .where(Project.tags.isnot(None))
        ).subquery()

        # Final query to select from the subquery and order by the 'name' key in the JSONB
        final_query = select(subquery).order_by(literal_column("tag->>'name'"))

        results = self.execute_all(final_query)
        tags = [res[0] for res in results] if results else []
        return tags, count

    async def get_all_active_projects(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Project], int]:
        """List all projects in the database."""
        await self.validate_fields(Project, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await ProjectDataManager._generate_global_search_stmt(Project, filters)
            u = aliased(User)
            # Subquery to calculate endpoint count
            endpoint_count_subquery = (
                select(
                    Endpoint.project_id,
                    func.count(Endpoint.id.distinct()).label("endpoint_count"),
                )
                .where(Endpoint.status != EndpointStatusEnum.DELETED)
                .group_by(Endpoint.project_id)
                .alias("ecount")
            )
            # Subquery to calculate credential count
            credential_count_subquery = (
                select(
                    Credential.project_id,
                    func.count(Credential.id.distinct()).label("credential_count"),
                )
                .group_by(Credential.project_id)
                .alias("ccount")
            )
            stmt = (
                select(
                    Project,
                    func.count(u.id).label("user_count"),
                    func.aggregate_strings(u.color, ",").label("profile_colors"),
                    endpoint_count_subquery.c.endpoint_count.label("endpoint_count"),
                    credential_count_subquery.c.credential_count.label("credential_count"),
                )
                .filter(and_(*search_conditions))
                .select_from(Project)
                .outerjoin(
                    project_user_association,
                    Project.id == project_user_association.c.project_id,
                )
                .outerjoin(u, project_user_association.c.user_id == u.id)
                .filter(u.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .outerjoin(
                    endpoint_count_subquery,
                    Project.id == endpoint_count_subquery.c.project_id,
                )
                .outerjoin(
                    credential_count_subquery,
                    Project.id == credential_count_subquery.c.project_id,
                )
                .group_by(
                    Project.id, endpoint_count_subquery.c.endpoint_count, credential_count_subquery.c.credential_count
                )
            )
            count_stmt = select(func.count()).select_from(Project).filter(and_(*search_conditions))
        else:
            u = aliased(User)
            # Subquery to calculate endpoint count
            endpoint_count_subquery = (
                select(
                    Endpoint.project_id,
                    func.count(Endpoint.id.distinct()).label("endpoint_count"),
                )
                .where(Endpoint.status != EndpointStatusEnum.DELETED)
                .group_by(Endpoint.project_id)
                .alias("ecount")
            )
            # Subquery to calculate credential count
            credential_count_subquery = (
                select(
                    Credential.project_id,
                    func.count(Credential.id.distinct()).label("credential_count"),
                )
                .group_by(Credential.project_id)
                .alias("ccount")
            )
            stmt = (
                select(
                    Project,
                    func.count(u.id).label("user_count"),
                    func.aggregate_strings(u.color, ",").label("profile_colors"),
                    endpoint_count_subquery.c.endpoint_count.label("endpoint_count"),
                    credential_count_subquery.c.credential_count.label("credential_count"),
                )
                .filter_by(**filters)
                .select_from(Project)
                .outerjoin(
                    project_user_association,
                    Project.id == project_user_association.c.project_id,
                )
                .outerjoin(u, project_user_association.c.user_id == u.id)
                .filter(u.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .outerjoin(
                    endpoint_count_subquery,
                    Project.id == endpoint_count_subquery.c.project_id,
                )
                .outerjoin(
                    credential_count_subquery,
                    Project.id == credential_count_subquery.c.project_id,
                )
                .group_by(
                    Project.id, endpoint_count_subquery.c.endpoint_count, credential_count_subquery.c.credential_count
                )
            )
            count_stmt = select(func.count()).select_from(Project).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Project, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def get_all_participated_projects(
        self,
        user_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Sequence[Row[Tuple[Project, int, Any]]]:
        """List all projects in the database."""
        await self.validate_fields(Project, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await ProjectDataManager._generate_global_search_stmt(Project, filters)
            u = aliased(User)
            # Subquery to calculate endpoint count
            endpoint_count_subquery = (
                select(
                    Endpoint.project_id,
                    func.count(Endpoint.id.distinct()).label("endpoint_count"),
                )
                .where(Endpoint.status != EndpointStatusEnum.DELETED)
                .group_by(Endpoint.project_id)
                .alias("ecount")
            )
            # Subquery to calculate credential count
            credential_count_subquery = (
                select(
                    Credential.project_id,
                    func.count(Credential.id.distinct()).label("credential_count"),
                )
                .group_by(Credential.project_id)
                .alias("ccount")
            )
            stmt = (
                select(
                    Project,
                    func.count(User.id).label("user_count"),
                    func.aggregate_strings(u.color, ",").label("profile_colors"),
                    endpoint_count_subquery.c.endpoint_count.label("endpoint_count"),
                    credential_count_subquery.c.credential_count.label("credential_count"),
                )
                .filter(and_(*search_conditions))
                .select_from(Project)
                .outerjoin(
                    project_user_association,
                    Project.id == project_user_association.c.project_id,
                )
                .outerjoin(u, project_user_association.c.user_id == u.id)
                .filter(u.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .outerjoin(
                    endpoint_count_subquery,
                    Project.id == endpoint_count_subquery.c.project_id,
                )
                .outerjoin(
                    credential_count_subquery,
                    Project.id == credential_count_subquery.c.project_id,
                )
                .join(Project.users)
                .filter_by(id=user_id)
                .group_by(
                    Project.id, endpoint_count_subquery.c.endpoint_count, credential_count_subquery.c.credential_count
                )
            )
            count_stmt = (
                select(func.count())
                .select_from(Project)
                .filter(and_(*search_conditions))
                .join(Project.users)
                .filter_by(id=user_id)
            )
        else:
            u = aliased(User)
            # Subquery to calculate endpoint count
            endpoint_count_subquery = (
                select(
                    Endpoint.project_id,
                    func.count(Endpoint.id.distinct()).label("endpoint_count"),
                )
                .where(Endpoint.status != EndpointStatusEnum.DELETED)
                .group_by(Endpoint.project_id)
                .alias("ecount")
            )
            # Subquery to calculate credential count
            credential_count_subquery = (
                select(
                    Credential.project_id,
                    func.count(Credential.id.distinct()).label("credential_count"),
                )
                .group_by(Credential.project_id)
                .alias("ccount")
            )
            stmt = (
                select(
                    Project,
                    func.count(User.id).label("user_count"),
                    func.aggregate_strings(u.color, ",").label("profile_colors"),
                    endpoint_count_subquery.c.endpoint_count.label("endpoint_count"),
                    credential_count_subquery.c.credential_count.label("credential_count"),
                )
                .filter_by(**filters)
                .select_from(Project)
                .outerjoin(
                    project_user_association,
                    Project.id == project_user_association.c.project_id,
                )
                .outerjoin(u, project_user_association.c.user_id == u.id)
                .filter(u.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .outerjoin(
                    endpoint_count_subquery,
                    Project.id == endpoint_count_subquery.c.project_id,
                )
                .outerjoin(
                    credential_count_subquery,
                    Project.id == credential_count_subquery.c.project_id,
                )
                .join(Project.users)
                .filter_by(id=user_id)
                .group_by(
                    Project.id, endpoint_count_subquery.c.endpoint_count, credential_count_subquery.c.credential_count
                )
            )
            count_stmt = (
                select(func.count())
                .select_from(Project)
                .filter_by(**filters)
                .join(Project.users)
                .filter_by(id=user_id)
            )
            """ RAW SQL
            SELECT
                p.id AS project_id,
                p.name AS project_name,
                COUNT(u.id) AS user_count,
                (SELECT COUNT(DISTINCT e.id) FROM endpoint e WHERE e.project_id = p.id AND e.is_active = 1) AS endpoint_count
            FROM
                project p
            LEFT JOIN
                project_user_association ON p.id = project_user_association.project_id
            LEFT JOIN
                user u ON project_user_association.user_id = u.id AND u.is_active = 1
            WHERE
                u.is_active = 1
            GROUP BY
                p.id;
            """

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Project, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    @staticmethod
    async def _generate_global_search_stmt(model: Project, fields: Dict):
        # Inspect model columns
        inspect(model).columns

        # Initialize list to store search conditions
        search_conditions = []

        # Extract common filters
        status = fields.get("status", ProjectStatusEnum.ACTIVE)
        benchmark = fields.get("benchmark", False)
        search_value = fields.get("name")

        # Add active and benchmark conditions
        search_conditions.append(model.status == status)
        search_conditions.append(model.benchmark == benchmark)

        # Create conditions for name, description, and tags
        if search_value:
            name_condition = model.name.ilike(f"%{search_value}%")
            description_condition = model.description.ilike(f"%{search_value}%")

            # JSON condition for tags, accessing the "name" key in the JSON structure
            tags_condition = text(
                "EXISTS ("
                "SELECT 1 FROM jsonb_array_elements(CAST(project.tags AS JSONB)) AS tag "
                "WHERE lower(tag->>'name') LIKE :search_value"
                ")"
            ).bindparams(search_value=f"%{search_value.lower()}%")

            # Combine conditions using OR to match name, description, or tags
            search_conditions.append(or_(name_condition, description_condition, tags_condition))

        return search_conditions

    async def retrieve_project_details(self, project_id: UUID) -> Union[Tuple[Project, int], None]:
        """Retrieve project details with endpoint count for detail page."""
        # Subquery to count endpoints per project
        endpoint_count_subquery = (
            select(
                Endpoint.project_id,
                func.count(Endpoint.id.distinct()).label("endpoint_count"),
            )
            .where(Endpoint.status != EndpointStatusEnum.DELETED)
            .group_by(Endpoint.project_id)
            .alias("ecount")
        )

        # Main query with endpoint count, defaulting to 0 if no endpoints found
        stmt = (
            select(
                Project,
                func.coalesce(endpoint_count_subquery.c.endpoint_count, 0).label("endpoint_count"),  # Use coalesce
            )
            .outerjoin(
                endpoint_count_subquery,
                Project.id == endpoint_count_subquery.c.project_id,
            )
            .filter(
                Project.id == project_id,
                Project.status == ProjectStatusEnum.ACTIVE,  # Filter for active projects
            )
        )

        # Retrieve project details
        result = self.execute_all(stmt)
        row = result[0] if result else None

        if row is None:
            logger.info("Project not found in database")
            raise ClientException(status_code=status.HTTP_404_NOT_FOUND, message="Project not found")
        db_project, endpoint_count = row
        return db_project, endpoint_count

    async def get_all_project_users_without_permissions(
        self,
        project_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Tuple[User, str]], int]:
        """Get all users in a project without permission tables."""
        await self.validate_fields(User, filters)

        # define project_role
        project_role = case(
            (Project.created_by == User.id, "owner"),
            else_="participant",
        ).label("project_role")

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(User, filters)
            stmt = (
                select(
                    User,
                    project_role,
                )
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter(and_(*search_conditions))
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
            )

            count_stmt = (
                select(func.count())
                .select_from(User)
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter(and_(*search_conditions))
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .where(project_user_association.c.project_id == project_id)
            )
        else:
            stmt = (
                select(
                    User,
                    project_role,
                )
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter_by(**filters)
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
            )

            count_stmt = (
                select(func.count())
                .select_from(User)
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter_by(**filters)
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .where(project_user_association.c.project_id == project_id)
            )

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = []
            # Handle project_role custom field
            for order_tuple in order_by[:]:  # Create a copy to iterate over
                order_field = order_tuple[0]
                direction = order_tuple[1]
                if order_field == "project_role":
                    if direction == "asc":
                        sort_conditions.append(project_role.asc())
                    else:
                        sort_conditions.append(project_role.desc())
                    order_by.remove(order_tuple)
                    break

            # Add remaining sort conditions for User model fields
            sort_conditions.extend(await self.generate_sorting_stmt(User, order_by))
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        return result, count

    async def get_all_users(
        self,
        project_id: UUID,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List, int]:
        """Get all users in a project."""
        await self.validate_fields(User, filters)

        # define project_role
        project_role = case(
            (Project.created_by == User.id, "owner"),
            else_="participant",
        ).label("project_role")

        # Generate statements according to search or filters
        # Collect user ids from project user association table
        if search:
            search_conditions = await self.generate_search_stmt(User, filters)
            stmt = (
                select(
                    User,
                    project_role,
                    ProjectPermission,
                    Permission,
                )
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter(and_(*search_conditions))
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
                .join(
                    ProjectPermission,
                    and_(
                        ProjectPermission.project_id == Project.id,
                        ProjectPermission.user_id == User.id,
                    ),
                )
                .join(Permission, Permission.user_id == User.id)
            )

            count_stmt = (
                select(func.count())
                .select_from(User)
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter(and_(*search_conditions))
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
                .join(
                    ProjectPermission,
                    and_(
                        ProjectPermission.project_id == Project.id,
                        ProjectPermission.user_id == User.id,
                    ),
                )
            )
        else:
            stmt = (
                select(
                    User,
                    project_role,
                    ProjectPermission,
                    Permission,
                )
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter_by(**filters)
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
                .join(
                    ProjectPermission,
                    and_(
                        ProjectPermission.project_id == Project.id,
                        ProjectPermission.user_id == User.id,
                    ),
                )
                .join(Permission, Permission.user_id == User.id)
            )

            count_stmt = (
                select(func.count())
                .select_from(User)
                .filter(User.status.in_([UserStatusEnum.INVITED, UserStatusEnum.ACTIVE]))
                .filter_by(**filters)
                .join(
                    project_user_association,
                    User.id == project_user_association.c.user_id,
                )
                .join(
                    Project,
                    project_user_association.c.project_id == Project.id,
                )
                .where(project_user_association.c.project_id == project_id)
                .join(
                    ProjectPermission,
                    and_(
                        ProjectPermission.project_id == Project.id,
                        ProjectPermission.user_id == User.id,
                    ),
                )
            )

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = []
            # if project_role is in order_by, list then remove it from the order_by
            for order_tuple in order_by:
                order_field = order_tuple[0]
                direction = order_tuple[1]
                if order_field == "project_role":
                    if direction == "asc":
                        sort_conditions.append(project_role.asc())
                    else:
                        sort_conditions.append(project_role.desc())
                    order_by.remove(order_tuple)
                    break

            sort_conditions.extend(await self.generate_sorting_stmt(User, order_by))
            stmt = stmt.order_by(*sort_conditions)

        result = self.execute_all(stmt)

        count = self.execute_scalar(count_stmt)

        return result, count

    async def get_active_projects_by_ids(self, project_ids: List[UUID]) -> List[Project]:
        """Get active projects by ids.

        Args:
            project_ids: List of project ids

        Returns:
            List of active projects
        """
        stmt = select(Project).filter(Project.id.in_(project_ids)).filter_by(status=ProjectStatusEnum.ACTIVE)

        return self.scalars_all(stmt)

    async def is_user_in_project(self, user_id: UUID, project_id: UUID) -> bool:
        """Check if a user is a member of a project.

        Args:
            user_id: The user ID
            project_id: The project ID

        Returns:
            True if user is a member, False otherwise
        """
        stmt = (
            select(func.count())
            .select_from(project_user_association)
            .where(project_user_association.c.user_id == user_id, project_user_association.c.project_id == project_id)
        )
        count = self.scalar_one_or_none(stmt)
        return count > 0 if count is not None else False

    async def get_user_project_ids(self, user_id: UUID) -> List[UUID]:
        """Get all project IDs that a user is associated with.

        Args:
            user_id: The user ID

        Returns:
            List of project IDs the user has access to
        """
        stmt = (
            select(project_user_association.c.project_id)
            .select_from(project_user_association)
            .join(Project, project_user_association.c.project_id == Project.id)
            .where(
                project_user_association.c.user_id == user_id,
                Project.status == ProjectStatusEnum.ACTIVE,
            )
        )
        result = self.scalars_all(stmt)
        return result if result else []

    async def check_duplicate_name_for_user_projects(
        self, project_name: str, user_id: UUID, project_type: str, exclude_project_id: Optional[UUID] = None
    ) -> bool:
        """Check if a project with the same name and type exists for the user's associated projects.

        Args:
            project_name: The project name to check
            user_id: The user ID
            project_type: The project type to check
            exclude_project_id: Optional project ID to exclude from the check (useful for updates)

        Returns:
            True if a duplicate project name exists, False otherwise
        """
        conditions = [
            project_user_association.c.user_id == user_id,
            func.lower(Project.name) == func.lower(project_name),
            Project.project_type == project_type,
            Project.status == ProjectStatusEnum.ACTIVE,
        ]

        # Add exclude condition if provided
        if exclude_project_id is not None:
            conditions.append(Project.id != exclude_project_id)

        stmt = (
            select(func.count())
            .select_from(Project)
            .join(
                project_user_association,
                Project.id == project_user_association.c.project_id,
            )
            .where(and_(*conditions))
        )
        count = self.scalar_one_or_none(stmt)
        return count > 0 if count is not None else False

    async def get_all_projects(
        self,
        offset: int,
        limit: int,
        filters: Dict = {},
        order_by: List = [],
        search: bool = False,
    ) -> Tuple[List[Project], int]:
        """List all projects in the database."""
        await self.validate_fields(Project, filters)

        # Generate statements according to search or filters
        if search:
            search_conditions = await self.generate_search_stmt(Project, filters)
            stmt = select(Project).filter(or_(*search_conditions))
            count_stmt = select(func.count()).select_from(Project).filter(and_(*search_conditions))
        else:
            stmt = select(Project).filter_by(**filters)
            count_stmt = select(func.count()).select_from(Project).filter_by(**filters)

        # Calculate count before applying limit and offset
        count = self.execute_scalar(count_stmt)

        # Apply limit and offset
        stmt = stmt.limit(limit).offset(offset)

        # Apply sorting
        if order_by:
            sort_conditions = await self.generate_sorting_stmt(Project, order_by)
            stmt = stmt.order_by(*sort_conditions)

        result = self.scalars_all(stmt)

        return result, count

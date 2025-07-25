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

"""Contains dependency injection functions and utilities for the microservices, enabling modular and reusable components across the application."""

from collections.abc import AsyncGenerator
from typing import Annotated, List

from budmicroframe.shared.psql_service import Database
from fastapi import Query
from sqlalchemy.orm import Session


async def get_session() -> AsyncGenerator[Session, None]:
    """Get database session."""
    db = Database()
    session = db.get_session()
    try:
        yield session
    finally:
        db.close_session(session)


async def parse_ordering_fields(
    order_by: Annotated[
        str | None,
        Query(
            alias="order_by",
            description="Comma-separated list of fields. Example: field1,-field2,field3:asc,field4:desc",
        ),
    ] = None,
) -> List:
    """Parse a comma-separated list of fields with optional sorting directions.

    Args:
        order_by (str | None): A comma-separated list of fields for ordering.
            Each field can include an optional sorting direction.
            Format: field1,-field2,field3:asc,field4:desc

    Returns:
        List[Tuple[str, str]]: A list of tuples, each containing a field name
        and its sorting direction ('asc' or 'desc').

    Examples:
        >>> parse_ordering_fields("name,-age,created_at:desc")
        [('name', 'asc'), ('age', 'desc'), ('created_at', 'desc')]
    """
    order_by_list = []

    if order_by is not None and order_by != "null":
        # Split the order_by string into individual fields
        fields = order_by.split(",")

        for field in fields:
            # Skip empty fields
            if not field.strip():
                continue

            # Split field into field name and sorting direction
            parts = field.split(":")
            field_name = parts[0].strip()

            if len(parts) == 1:
                # No sorting direction specified, default to ascending
                if field_name.startswith("-"):
                    order_by_list.append((field_name[1:], "desc"))
                else:
                    order_by_list.append((field_name, "asc"))
            else:
                # Sorting direction specified
                sort_direction = parts[1].lower().strip()
                if sort_direction == "asc" or sort_direction == "desc":
                    order_by_list.append((field_name, sort_direction))

    return order_by_list

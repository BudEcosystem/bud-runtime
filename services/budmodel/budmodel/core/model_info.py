from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

# Import Models, Sources, and get_db_uri from your models definition
from .models import Models, Sources


# TODO: Use the PSQL service for db management and keep the models in the target modules
# Database setup
# DATABASE_URL = get_db_uri()
# async_engine = create_async_engine(DATABASE_URL, echo=True)
# AsyncSessionLocal = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


def serialize_value(value):
    """Helper function to handle datetime serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def fetch_merged_models(session: AsyncSession, page: int = 1, page_size: int = 10):
    # Calculate offset for pagination
    offset = (page - 1) * page_size

    # Query all models with their source names, sorted by updated_at
    result = await session.execute(
        select(Models, Sources.name)
        .join(Sources, Models.source_id == Sources.id)
        .order_by(desc(Models.updated_at))
        .offset(offset)
        .limit(page_size)
    )
    models_data = result.fetchall()

    # List to store merged results
    merged_models = []

    # Loop through each model row to populate merged_models
    for model, source_name in models_data:
        model_data = {"name": model.name, "fields": {}, "source_urls": []}

        # Populate the fields for this model, including empty ones
        for column in Models.__table__.columns:
            col_name = column.name
            value = getattr(model, col_name)
            model_data["fields"][col_name] = serialize_value(value) if value is not None else None

        # Append unique URLs with source name
        model_data["source_urls"].append({"url": model.url, "source_name": source_name})

        # Add the model data to the list
        merged_models.append(model_data)

    return merged_models


async def get_models(page: int = 1, page_size: int = 10):
    async with AsyncSessionLocal() as session:
        models = await fetch_merged_models(session, page, page_size)
        return models

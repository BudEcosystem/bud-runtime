# from budmodel.models import get_db_uri
from budmodel.commons import logging


# from budmodel.metrics_collector.fetch_data import extract_data


logger = logging.get_logger(__name__)


# TODO: Use the PSQL service for db management and keep the models in the target modules
# DATABASE_URL = get_db_uri()
# async_engine = create_async_engine(DATABASE_URL, echo=True)
# AsyncSessionLocal = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def insert_or_update_models_from_sources():
    """Insert or update models from active sources in the database."""
    # TODO: This function needs proper database configuration
    # The required imports (AsyncSessionLocal, async_engine) are commented out
    raise NotImplementedError("Function requires proper database setup")


if __name__ == "__main__":
    import asyncio

    asyncio.run(insert_or_update_models_from_sources())

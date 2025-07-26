import importlib
import json

from sqlalchemy.future import select

# from budmodel.models import get_db_uri
from budmodel.commons import logging
from budmodel.metrics_collector.fetch_data import extract_data


logger = logging.get_logger(__name__)


# TODO: Use the PSQL service for db management and keep the models in the target modules
# DATABASE_URL = get_db_uri()
# async_engine = create_async_engine(DATABASE_URL, echo=True)
# AsyncSessionLocal = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


async def insert_or_update_models_from_sources():
    try:
        logger.info("Starting model data collection process")
        # Dynamically import Sources and Models from models.py
        models_module = importlib.import_module("budmodel.models")
        Sources = getattr(models_module, "Sources")
        Models = getattr(models_module, "Models")

        async with AsyncSessionLocal() as session:
            # Fetch only active entries from Sources asynchronously
            result = await session.execute(select(Sources).where(Sources.is_active == True))
            sources = result.scalars().all()
            logger.info(f"Found {len(sources)} active sources")

            # Reflect the current columns in the Models table
            async with async_engine.begin() as conn:
                inspector = await conn.run_sync(
                    lambda connection: connection.dialect.get_columns(connection, Models.__tablename__)
                )
                current_columns = {col["name"] for col in inspector}

            for source in sources:
                logger.debug(f"Processing source: {source.name}")
                # Parse schema and other fields needed for data extraction
                logger.info(f"Extracting data from source: {source.name}")
                schema = json.loads(source.schema)
                wait_for = source.wait_for or ""
                js_code = source.js_code or ""
                css_base_selector = source.css_base_selector or ""

                try:
                    # Call `extract_data` asynchronously with the source parameters
                    extracted_data = await extract_data(
                        url=source.url,
                        schema=schema,
                        wait_for=wait_for,
                        js_code=js_code,
                        css_base_selector=css_base_selector,
                    )

                    # Insert or update each document from extracted_data in the Models table
                    for data in extracted_data:
                        # Add source_id to the data dictionary
                        data_with_source = {"source_id": source.id, **data}

                        # Dynamically add missing columns
                        for key in data_with_source:
                            if key not in current_columns:
                                logger.info(f"Adding missing column '{key}' to Models table.")
                                async with async_engine.begin() as conn:
                                    await conn.execute(f"ALTER TABLE {Models.__tablename__} ADD COLUMN {key} TEXT")
                                current_columns.add(key)

                        # Check if model with the same name exists
                        existing_model = await session.execute(
                            select(Models).where(Models.name == data.get("name"), Models.source_id == source.id)
                        )
                        existing_model = existing_model.scalars().first()

                        if existing_model:
                            # Update the existing model fields
                            for key, value in data_with_source.items():
                                setattr(existing_model, key, value)
                            logger.info(f"Updated model: {existing_model.name}")
                        else:
                            # Create a new model instance and add to session
                            model = Models(**data_with_source)
                            session.add(model)
                            logger.info(f"Inserted new model: {model.name}")

                except Exception as e:
                    logger.error(f"Error extracting data for source {source.name}: {str(e)}")
                    continue

            # Commit all changes to the database
            await session.commit()
            logger.info("Data successfully inserted or updated in Models from active Sources.")
        logger.info("Model data collection completed successfully")
    except Exception as e:
        logger.error(f"Error during model data collection: {str(e)}")
        raise

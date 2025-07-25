import json
import os
from typing import Any, Dict

from datasets import load_dataset_builder

from budapp.commons import logging
from budapp.commons.config import secrets_settings
from budapp.commons.constants import DatasetStatusEnum
from budapp.dataset_ops.models import DatasetCRUD
from budapp.dataset_ops.schemas import DatasetCreate, DatasetUpdate

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# current file path
CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))

# seeder file path
DATASET_SEEDER_FILE_PATH = os.path.join(CURRENT_FILE_PATH, "data", "dataset_info.json")


class DatasetSeeder(BaseSeeder):
    """Seeder for benchmarking datasets.

    Ref: https://github.com/hiyouga/LLaMA-Factory
    """

    async def seed(self) -> None:
        """Seed benchmarking dataset to the database."""
        try:
            await self._seed_datasets()
        except Exception as e:
            logger.exception(f"Failed to seed datasets: {e}")

    @staticmethod
    async def _seed_datasets() -> None:
        existing_datasets = []
        offset = 0
        limit = 100
        while True:
            with DatasetCRUD() as crud:
                db_datasets, count = await crud.fetch_many_with_search(offset=offset, limit=limit, search=False)

            if not db_datasets:
                break

            existing_datasets.extend(db_datasets)
            offset += limit

            logger.info(f"Fetched {count} datasets. Total datasets found: {len(existing_datasets)}")

            if count < limit:
                break

            logger.info(f"Finished fetching datasets. Total datasets found: {len(existing_datasets)}")

        datasets_data = await DatasetSeeder._get_datasets_data()

        for existing_dataset in existing_datasets:
            if existing_dataset.name in datasets_data:
                # update existing dataset
                if datasets_data[existing_dataset.name].get("hf_hub_url"):
                    # commenting calling load_dataset_builder for update step because it takes time
                    # hf_info = await DatasetSeeder.get_huggingface_info(datasets_data[existing_dataset.name]["hf_hub_url"])
                    # datasets_data[existing_dataset["name"]]["description"] = hf_info["description"]
                    datasets_data[existing_dataset.name]["status"] = DatasetStatusEnum.ACTIVE
                    if not datasets_data[existing_dataset.name].get("split"):
                        datasets_data[existing_dataset.name]["split"] = "train"
                if not datasets_data[existing_dataset.name].get("formatting"):
                    datasets_data[existing_dataset.name]["formatting"] = "alpaca"
                update_dataset_object = DatasetUpdate(**datasets_data[existing_dataset.name])
                with DatasetCRUD() as crud:
                    crud.update(
                        data=update_dataset_object.model_dump(mode="json", exclude_none=True),
                        conditions={"id": existing_dataset.id},
                    )
                # delete from datasets_data
                del datasets_data[existing_dataset.name]
            elif existing_dataset.status == DatasetStatusEnum.ACTIVE:
                # update status to inactive
                with DatasetCRUD() as crud:
                    crud.update(data={"status": DatasetStatusEnum.INACTIVE}, conditions={"id": existing_dataset.id})

        # remaining are new entries
        # insert in dataset table
        data_to_be_inserted = []
        for name, dataset_info in datasets_data.items():
            # create insert schema
            dataset_info["name"] = name
            if dataset_info.get("hf_hub_url"):
                hf_info = await DatasetSeeder.get_huggingface_info(dataset_info["hf_hub_url"])
                print(hf_info)
                dataset_info["description"] = hf_info["description"]
                dataset_info["status"] = DatasetStatusEnum.ACTIVE
                if not dataset_info.get("split"):
                    dataset_info["split"] = "train"
                if hf_info["splits"] and hf_info["splits"].get(dataset_info["split"]):  # noqa: SIM102
                    if hasattr(hf_info["splits"][dataset_info["split"]], "num_examples"):
                        dataset_info["num_samples"] = hf_info["splits"][dataset_info["split"]].num_examples
            if not dataset_info.get("formatting"):
                dataset_info["formatting"] = "alpaca"
            create_dataset_object = DatasetCreate(**dataset_info)
            data_to_be_inserted.append(create_dataset_object.model_dump(mode="json"))

        if data_to_be_inserted:
            # bulk insert
            with DatasetCRUD() as crud:
                crud.bulk_insert(data_to_be_inserted)

    @staticmethod
    async def _get_datasets_data() -> Dict[str, Any]:
        """Get benchmark datasets data from the seeder file."""
        try:
            with open(DATASET_SEEDER_FILE_PATH, "r") as file:
                return json.load(file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {DATASET_SEEDER_FILE_PATH}") from e

    @staticmethod
    async def get_huggingface_info(hf_hub_url):
        """Get dataset info from huggingface."""
        description = ""
        splits = None
        try:
            ds_builder = load_dataset_builder(hf_hub_url, token=secrets_settings.hf_token)
            description = ds_builder.info.description
            splits = ds_builder.info.splits
        except Exception as e:
            logger.error(f"Failed to get data from huggingface: {e}")
        return {"description": description, "splits": splits}

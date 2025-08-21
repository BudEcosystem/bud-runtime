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

"""Repository interface for evaluation dataset metadata access."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .manifest_schemas import Dataset, TraitDefinition


class EvalDatasetRepository(ABC):
    """Abstract repository interface for evaluation dataset metadata."""

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get a dataset by ID."""
        pass

    @abstractmethod
    async def list_datasets(self, traits: list[str] | None = None, source: str | None = None) -> list[Dataset]:
        """List all datasets, optionally filtered by traits or source."""
        pass

    @abstractmethod
    async def get_trait(self, trait_name: str) -> TraitDefinition | None:
        """Get a trait definition by name."""
        pass

    @abstractmethod
    async def list_traits(self) -> list[TraitDefinition]:
        """List all trait definitions."""
        pass

    @abstractmethod
    async def get_datasets_by_trait(self, trait_name: str) -> list[Dataset]:
        """Get all datasets that evaluate a specific trait."""
        pass

    @abstractmethod
    async def search_datasets(self, query: str) -> list[Dataset]:
        """Search datasets by name or description."""
        pass

    @abstractmethod
    async def get_dataset_sources(self) -> list[str]:
        """Get all available dataset sources."""
        pass

    @abstractmethod
    async def get_datasets_by_source(self, source: str) -> list[Dataset]:
        """Get all datasets from a specific source."""
        pass


class DatabaseManifestRepository(EvalDatasetRepository):
    """Database implementation of the repository using persisted dataset metadata."""

    def __init__(self) -> None:
        """Initialize the database repository and connect to the database."""
        from budmicroframe.shared.psql_service import Database

        self.db = Database()
        self.db.connect()

    async def get_dataset(self, dataset_id: str) -> Dataset | None:
        """Get a dataset by ID."""
        from sqlalchemy.orm import joinedload

        from .models import ExpDataset

        with self.db.get_session() as session:
            # Find dataset by manifest_id in meta_links
            dataset = (
                session.query(ExpDataset)
                .filter(ExpDataset.meta_links["manifest_id"].astext == dataset_id)
                .options(joinedload(ExpDataset.versions), joinedload(ExpDataset.traits))
                .first()
            )

            if not dataset:
                return None

            return self._convert_to_dataset_schema(dataset)

    async def list_datasets(self, traits: list[str] | None = None, source: str | None = None) -> list[Dataset]:
        """List all datasets, optionally filtered by traits or source."""
        from sqlalchemy.orm import joinedload

        from .models import ExpDataset, ExpTrait, ExpTraitsDatasetPivot

        with self.db.get_session() as session:
            query = session.query(ExpDataset).options(joinedload(ExpDataset.versions), joinedload(ExpDataset.traits))

            # Filter by traits if specified
            if traits:
                query = query.join(ExpTraitsDatasetPivot).join(ExpTrait).filter(ExpTrait.name.in_(traits))

            # Note: source filtering would require storing source in metadata
            # For now, we'll return all datasets and let caller handle source filtering

            datasets = query.all()
            return [self._convert_to_dataset_schema(dataset) for dataset in datasets]

    async def get_trait(self, trait_name: str) -> TraitDefinition | None:
        """Get a trait definition by name."""
        from .models import ExpTrait

        with self.db.get_session() as session:
            trait = session.query(ExpTrait).filter_by(name=trait_name).first()
            if not trait:
                return None

            return TraitDefinition(
                name=trait.name,
                description=trait.description or f"Evaluation trait: {trait.name}",
                icon=trait.icon or f"icons/traits/{trait.name.lower().replace(' ', '_')}.png",
            )

    async def list_traits(self) -> list[TraitDefinition]:
        """List all trait definitions."""
        from .models import ExpTrait

        with self.db.get_session() as session:
            traits = session.query(ExpTrait).all()
            return [
                TraitDefinition(
                    name=trait.name,
                    description=trait.description or f"Evaluation trait: {trait.name}",
                    icon=trait.icon or f"icons/traits/{trait.name.lower().replace(' ', '_')}.png",
                )
                for trait in traits
            ]

    async def get_datasets_by_trait(self, trait_name: str) -> list[Dataset]:
        """Get all datasets that evaluate a specific trait."""
        from sqlalchemy.orm import joinedload

        from .models import ExpDataset, ExpTrait, ExpTraitsDatasetPivot

        with self.db.get_session() as session:
            datasets = (
                session.query(ExpDataset)
                .join(ExpTraitsDatasetPivot)
                .join(ExpTrait)
                .filter(ExpTrait.name == trait_name)
                .options(joinedload(ExpDataset.versions), joinedload(ExpDataset.traits))
                .all()
            )

            return [self._convert_to_dataset_schema(dataset) for dataset in datasets]

    async def search_datasets(self, query: str) -> list[Dataset]:
        """Search datasets by name or description."""
        from sqlalchemy import or_
        from sqlalchemy.orm import joinedload

        from .models import ExpDataset

        with self.db.get_session() as session:
            query_lower = f"%{query.lower()}%"
            datasets = (
                session.query(ExpDataset)
                .filter(or_(ExpDataset.name.ilike(query_lower), ExpDataset.description.ilike(query_lower)))
                .options(joinedload(ExpDataset.versions), joinedload(ExpDataset.traits))
                .all()
            )

            return [self._convert_to_dataset_schema(dataset) for dataset in datasets]

    async def get_dataset_sources(self) -> list[str]:
        """Get all available dataset sources."""
        # Since we don't store source separately, return a default list
        # This could be enhanced to parse source from metadata or store separately
        return ["opencompass", "custom"]

    async def get_datasets_by_source(self, source: str) -> list[Dataset]:
        """Get all datasets from a specific source."""
        # For now, return all datasets since we don't store source separately
        # This could be enhanced based on how source is determined
        return await self.list_datasets()

    def _convert_to_dataset_schema(self, db_dataset) -> Dataset:
        """Convert database model to Dataset schema."""
        from .manifest_schemas import Dataset, DatasetMetadata

        # Get the latest version
        latest_version = None
        if db_dataset.versions:
            latest_version = max(db_dataset.versions, key=lambda v: v.created_at)

        # Extract metadata from the version
        version_meta = latest_version.meta if latest_version else {}

        # Create metadata object
        metadata = DatasetMetadata(
            format=version_meta.get("metadata", {}).get("format", "jsonl"),
            language=db_dataset.language[0] if db_dataset.language else "en",
            domain=db_dataset.domains[0] if db_dataset.domains else "general",
            difficulty="medium",  # Default since we don't store this separately
            estimated_input_tokens=db_dataset.estimated_input_tokens or 0,
            estimated_output_tokens=db_dataset.estimated_output_tokens or 0,
        )

        return Dataset(
            id=db_dataset.meta_links.get("manifest_id", str(db_dataset.id)),
            name=db_dataset.name,
            version=latest_version.version if latest_version else "1.0",
            description=db_dataset.description or "",
            url=version_meta.get("url", ""),
            size_mb=version_meta.get("size_mb", 0.0),
            checksum=version_meta.get("checksum", ""),
            sample_count=version_meta.get("sample_count", 0),
            traits=[trait.name for trait in db_dataset.traits],
            metadata=metadata,
            original_data=db_dataset.meta_links,
        )


# Global repository instance
_repository: EvalDatasetRepository | None = None


def get_eval_dataset_repository() -> EvalDatasetRepository:
    """Get the global repository instance."""
    global _repository
    if _repository is None:
        _repository = DatabaseManifestRepository()
    return _repository

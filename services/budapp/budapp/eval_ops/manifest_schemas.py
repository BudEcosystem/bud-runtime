"""Schema definitions for evaluation dataset manifest."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VersionInfo(BaseModel):
    """Previous version information."""

    version: str
    deprecated: bool
    migration_required: Optional[bool] = False
    end_of_life: Optional[str] = None


class RepositoryInfo(BaseModel):
    """Repository metadata."""

    name: str
    description: str
    maintainer: str
    base_url: str
    bundle_url: Optional[str] = None  # URL to download all datasets as a single zip
    bundle_checksum: Optional[str] = None  # Checksum for the complete bundle
    bundle_size_mb: Optional[float] = None  # Size of the complete bundle


class ManifestVersion(BaseModel):
    """Version information for the manifest."""

    current_version: str
    previous_versions: List[VersionInfo] = []


class TraitCategory(BaseModel):
    """Trait category grouping."""

    name: str
    traits: List[str]


class TraitDefinition(BaseModel):
    """Individual trait definition."""

    name: str
    description: str
    icon: str


class TraitsInfo(BaseModel):
    """Traits definition information."""

    version: str
    checksum: str
    url: str
    count: int
    categories: Optional[List[TraitCategory]] = None  # Old format support
    definitions: Optional[List[TraitDefinition]] = None  # New format


class DatasetMetadata(BaseModel):
    """Dataset-specific metadata."""

    # Common fields
    format: str
    language: Optional[str] = None
    languages: Optional[List[str]] = None

    # Domain-specific fields
    domain: Optional[str] = None
    subjects: Optional[int] = None
    questions_per_subject: Optional[str] = None
    difficulty: Optional[str] = None
    programming_language: Optional[str] = None
    samples_per_language: Optional[int] = None

    # Access control
    requires_auth: Optional[bool] = False
    privacy_level: Optional[str] = None

    # Token estimates
    estimated_input_tokens: Optional[int] = None
    estimated_output_tokens: Optional[int] = None

    # Enriched evaluation fields
    why_run_this_eval: Optional[List[str]] = None
    what_to_expect: Optional[List[str]] = None
    evaluation_description: Optional[str] = None
    top_5_task_types: Optional[List[str]] = None
    top_5_domains: Optional[List[str]] = None
    top_5_skills: Optional[List[str]] = None
    top_5_concepts: Optional[List[str]] = None
    top_5_qualifications: Optional[List[str]] = None
    top_5_languages: Optional[List[str]] = None
    age_distribution: Optional[Dict[str, Any]] = None


class Dataset(BaseModel):
    """Individual dataset information."""

    id: str
    name: str
    version: str
    description: str
    url: str
    size_mb: float
    checksum: str
    sample_count: Optional[int] = None
    traits: List[str]
    metadata: DatasetMetadata
    eval_type: Optional[Dict[str, str]] = None  # Evaluation type configurations
    original_data: Optional[Dict[str, Any]] = None  # Original metadata from source


class DatasetCollection(BaseModel):
    """Collection of datasets from a source."""

    version: str
    license: str
    source: Optional[str] = None
    bundle_url: Optional[str] = None  # URL to download this collection as a zip
    bundle_checksum: Optional[str] = None  # Checksum for this collection bundle
    bundle_size_mb: Optional[float] = None  # Size of this collection bundle
    datasets: List[Dataset]


class UpdatePolicy(BaseModel):
    """Update policy configuration."""

    check_interval_hours: int = 24
    auto_update: bool = False
    notify_on_update: bool = True
    backup_before_update: bool = True
    rollback_on_failure: bool = True


class Authentication(BaseModel):
    """Authentication configuration."""

    required_for: List[str]
    method: str
    token_endpoint: str


class MigrationScript(BaseModel):
    """Migration script information."""

    order: int
    description: str
    url: str


class Migration(BaseModel):
    """Migration information between versions."""

    from_version: str
    to_version: str
    type: str  # "incremental" or "full"
    scripts: List[MigrationScript]


class EvalDataManifest(BaseModel):
    """Complete evaluation dataset manifest."""

    manifest_version: str
    last_updated: datetime
    schema_version: str
    repository: RepositoryInfo
    version_info: ManifestVersion
    traits: TraitsInfo
    datasets: Dict[str, DatasetCollection] = Field(
        description="Dataset collections by source (opencompass, bud_custom, etc.)"
    )
    update_policy: UpdatePolicy
    authentication: Optional[Authentication] = None
    migration: Optional[Migration] = None
    changelog: Dict[str, List[str]] = Field(default_factory=dict)

    def get_all_datasets(self) -> List[Dataset]:
        """Get all datasets from all sources."""
        all_datasets = []
        for collection in self.datasets.values():
            all_datasets.extend(collection.datasets)
        return all_datasets

    def get_datasets_by_trait(self, trait: str) -> List[Dataset]:
        """Get all datasets that evaluate a specific trait."""
        return [dataset for dataset in self.get_all_datasets() if trait in dataset.traits]

    def get_dataset_by_id(self, dataset_id: str) -> Optional[Dataset]:
        """Get a specific dataset by ID."""
        for dataset in self.get_all_datasets():
            if dataset.id == dataset_id:
                return dataset
        return None

    def requires_migration(self, current_version: str | None) -> bool:
        """Check if migration is required from current version."""
        if current_version == "none":
            return True

        if not self.migration:
            return False
        return self.migration.from_version == current_version

    def get_total_size_mb(self) -> float:
        """Calculate total size of all datasets."""
        return sum(dataset.size_mb for dataset in self.get_all_datasets())

    def get_authenticated_datasets(self) -> List[Dataset]:
        """Get all datasets that require authentication."""
        return [dataset for dataset in self.get_all_datasets() if dataset.metadata.requires_auth]

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

"""Pydantic schemas for evaluation dataset manifest based on actual structure."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Repository(BaseModel):
    """Repository information."""

    name: str = Field(..., description="Repository name")
    description: str = Field(..., description="Repository description")
    maintainer: str = Field(..., description="Repository maintainer")
    base_url: str = Field(..., description="Base URL for datasets")
    bundle_url: str | None = Field(None, description="Bundle download URL")
    bundle_checksum: str | None = Field(None, description="Bundle checksum")
    bundle_size_mb: float | None = Field(None, description="Bundle size in MB")


class PreviousVersion(BaseModel):
    """Previous version information."""

    version: str = Field(..., description="Version string")
    deprecated: bool = Field(False, description="Whether version is deprecated")
    migration_required: bool = Field(False, description="Whether migration is required")


class VersionInfo(BaseModel):
    """Version information for the manifest."""

    current_version: str = Field(..., description="Current version of the manifest")
    previous_versions: list[PreviousVersion] = Field(default_factory=list, description="Previous versions")


class TraitDefinition(BaseModel):
    """Definition of an evaluation trait."""

    name: str = Field(..., description="Name of the trait")
    description: str = Field(..., description="Description of the trait")
    icon: str = Field(..., description="Icon path for the trait")


class TraitsInfo(BaseModel):
    """Information about evaluation traits."""

    version: str = Field(..., description="Version of traits definitions")
    checksum: str = Field(..., description="Checksum of traits data")
    url: str = Field(..., description="URL to traits definition file")
    count: int = Field(..., description="Number of traits")
    definitions: list[TraitDefinition] = Field(..., description="List of trait definitions")


class DatasetMetadata(BaseModel):
    """Dataset metadata information."""

    format: str = Field(..., description="Dataset format (e.g., 'jsonl')")
    language: str = Field(..., description="Primary language")
    domain: str = Field(..., description="Domain or category")
    difficulty: str = Field(..., description="Difficulty level")
    requires_auth: bool = Field(False, description="Whether authentication is required")
    estimated_input_tokens: int = Field(..., description="Estimated input tokens")
    estimated_output_tokens: int = Field(..., description="Estimated output tokens")


class CreatorInfo(BaseModel):
    """Creator information."""

    uid: str = Field(..., description="User ID")
    name: str | None = Field(None, description="Creator name")
    avatar: str | None = Field(None, description="Avatar URL")
    nickname: str = Field(..., description="Display nickname")


class Dimension(BaseModel):
    """Dimension information."""

    cn: str = Field(..., description="Chinese name")
    en: str = Field(..., description="English name")


class Tag(BaseModel):
    """Tag information."""

    cn: str = Field(..., description="Chinese tag")
    en: str = Field(..., description="English tag")


class Description(BaseModel):
    """Bilingual description."""

    cn: str = Field(..., description="Chinese description")
    en: str = Field(..., description="English description")


class QuestionExample(BaseModel):
    """Example question and answer."""

    question: str = Field(..., description="Question text")
    options: list[str] = Field(..., description="Answer options")
    correct_answer: str = Field(..., description="Correct answer")
    explanation: str = Field(..., description="Explanation of the answer")


class SampleQuestionsAnswers(BaseModel):
    """Sample questions and answers structure."""

    examples: list[QuestionExample] = Field(default_factory=list, description="Example questions")
    total_questions: int = Field(0, description="Total number of questions")
    question_format: str = Field("", description="Format of questions")
    difficulty_levels: list[str] = Field(default_factory=list, description="Difficulty levels")


class AdvantagesDisadvantages(BaseModel):
    """Advantages and disadvantages."""

    advantages: list[str] = Field(default_factory=list, description="Advantages")
    disadvantages: list[str] = Field(default_factory=list, description="Disadvantages")


class OriginalData(BaseModel):
    """Original dataset metadata from source."""

    id: str = Field(..., description="Original dataset ID")
    language: list[str] = Field(default_factory=list, description="Supported languages")
    domains: list[str] = Field(default_factory=list, description="Domains")
    concepts: list[str] = Field(default_factory=list, description="Concepts")
    humans_vs_llm_qualifications: list[str] = Field(default_factory=list, description="Human vs LLM qualifications")
    task_type: list[str] = Field(default_factory=list, description="Task types")
    modalities: list[str] = Field(default_factory=list, description="Modalities")
    sample_questions_answers: SampleQuestionsAnswers = Field(
        default_factory=SampleQuestionsAnswers, description="Sample Q&A"
    )
    advantages_disadvantages: AdvantagesDisadvantages = Field(
        default_factory=AdvantagesDisadvantages, description="Pros and cons"
    )
    emoji: str = Field("", description="Emoji representation")
    dimensions: list[Dimension] = Field(default_factory=list, description="Dimensions")
    sub_dimensions: list[Dimension] = Field(default_factory=list, description="Sub-dimensions", alias="subDimensions")
    tags: list[Tag] = Field(default_factory=list, description="Tags")
    topic_tags: list[Tag] = Field(default_factory=list, description="Topic tags", alias="topicTags")
    bench_certificate_level: int = Field(0, description="Benchmark certificate level", alias="benchCertificateLevel")
    github_link: str = Field("", description="GitHub link", alias="githubLink")
    paper_link: str = Field("", description="Paper link", alias="paperLink")
    official_website_link: str = Field("", description="Official website link", alias="officialWebsiteLink")
    leaderboard_link: bool = Field(False, description="Leaderboard link", alias="leaderboardLink")
    creator_info: CreatorInfo = Field(..., description="Creator information", alias="creatorInfo")
    look_num: str = Field("", description="Look number", alias="lookNum")
    top: bool = Field(False, description="Top dataset")
    state: int = Field(0, description="State")
    public_flag: int = Field(0, description="Public flag", alias="publicFlag")
    review_block_error: str | None = Field(None, description="Review block error", alias="reviewBlockError")
    review_success_date: str | None = Field(None, description="Review success date", alias="reviewSuccessDate")
    support_online_eval: bool = Field(False, description="Support online evaluation", alias="supportOnlineEval")
    update_date: str = Field("", description="Update date", alias="updateDate")
    create_date: str = Field("", description="Create date", alias="createDate")
    desc: Description = Field(..., description="Bilingual description")


class Dataset(BaseModel):
    """Dataset metadata."""

    id: str = Field(..., description="Unique dataset identifier")
    name: str = Field(..., description="Human-readable dataset name")
    version: str = Field(..., description="Dataset version")
    description: str = Field(..., description="Dataset description")
    url: str = Field(..., description="URL to download dataset")
    size_mb: float = Field(..., description="Dataset size in MB")
    checksum: str = Field(..., description="Dataset checksum")
    sample_count: int = Field(..., description="Number of samples in dataset")
    traits: list[str] = Field(..., description="List of traits this dataset evaluates")
    metadata: DatasetMetadata = Field(..., description="Dataset metadata")
    original_data: OriginalData = Field(..., description="Original dataset metadata")


class DatasetCollection(BaseModel):
    """Collection of datasets from a specific source."""

    version: str = Field(..., description="Collection version")
    license: str = Field(..., description="License information")
    source: str = Field(..., description="Source name")
    checksum: str = Field(..., description="Collection checksum")
    count: int = Field(..., description="Number of datasets in collection")
    datasets: list[Dataset] = Field(..., description="List of datasets from this source")


class Authentication(BaseModel):
    """Authentication configuration."""

    required_for: list[str] = Field(default_factory=list, description="Sources requiring authentication")
    method: str = Field("", description="Authentication method")
    token_endpoint: str = Field("", description="Token endpoint URL")


class EvalDataManifest(BaseModel):
    """Root manifest structure for evaluation data."""

    manifest_version: str = Field(..., description="Manifest version")
    last_updated: datetime = Field(..., description="Last update timestamp")
    schema_version: str = Field(..., description="Schema version")
    repository: Repository = Field(..., description="Repository information")
    version_info: VersionInfo = Field(..., description="Version information")
    traits: TraitsInfo = Field(..., description="Traits definitions")
    datasets: dict[str, DatasetCollection] = Field(..., description="Datasets grouped by source")
    authentication: Authentication = Field(..., description="Authentication configuration")
    migration: Any | None = Field(None, description="Migration information")
    changelog: dict[str, list[str]] = Field(default_factory=dict, description="Changelog")

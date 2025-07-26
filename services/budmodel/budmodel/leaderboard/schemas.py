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

"""The leaderboard schemas, containing essential data structures for the leaderboard microservice."""

from datetime import datetime
from typing import Any, List

from budmicroframe.commons.schemas import SuccessResponse
from pydantic import UUID4, BaseModel, ConfigDict, model_validator

from ..commons.constants import LeaderboardDataOrigin


class SourceCreate(BaseModel):
    """Source create schema."""

    name: str
    url: str
    wait_for: str | None = None
    js_code: str | None = None
    schema: str | None = None
    css_base_selector: str | None = None
    is_active: bool = True


class SourceUpdate(SourceCreate):
    """Source update schema."""

    pass


class Source(SourceCreate):
    """Source schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime
    updated_at: datetime


# Leaderboard schema


class LeaderboardBase(BaseModel):
    """Leaderboard base schema."""

    # APAC Eval Leaderboard fields
    lc_win_rate: float | None = None
    win_rate: float | None = None

    # Berkeley Leaderboard fields
    bcfl: float | None = None

    # LiveCodeBench Leaderboard fields
    live_code_bench: float | None = None

    # MTEB Leaderboard fields
    classification: float | None = None
    clustering: float | None = None
    pair_classification: float | None = None
    reranking: float | None = None
    retrieval: float | None = None
    semantic: float | None = None
    summarization: float | None = None

    # UGI Leaderboard fields (with _score suffixes)
    ugi_score: float | None = None
    w_10_score: float | None = None
    # i_10_score: str | None = None  # TODO: Uncomment this column when scraper bug is fixed
    unruly_score: float | None = None
    internet_score: float | None = None
    # stats_score: str | None = None  # TODO: Uncomment this column when scraper bug is fixed
    # writing_score: str | None = None  # TODO: Uncomment this column when scraper bug is fixed
    polcontro_score: float | None = None

    # VLLM Leaderboard fields
    mmbench: float | None = None
    mmstar: float | None = None
    mmmu: float | None = None
    math_vista: float | None = None
    ocr_bench: float | None = None
    ai2d: int | None = None
    hallucination_bench: float | None = None
    mmvet: float | None = None

    # Chatbot Arena Leaderboard fields
    lmsys_areana: int | None = None

    # LLM Stats Leaderboard fields
    gpqa: float | None = None
    mmlu: float | None = None
    mmlu_pro: float | None = None
    drop: float | None = None
    humaneval: float | None = None


class LeaderboardCreate(BaseModel):
    """Leaderboard create schema."""

    eval_name: str
    normalised_eval_name: str
    eval_score: float
    source_id: UUID4 | None = None
    model_info_id: UUID4
    data_origin: LeaderboardDataOrigin


class LeaderboardUpdate(LeaderboardBase):
    """Leaderboard update schema."""

    pass


class Leaderboard(LeaderboardCreate):
    """Leaderboard schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    created_at: datetime
    updated_at: datetime


# Crawler schemas


class BaseCrawlerConfig(BaseModel):
    """Base crawler config schema."""

    pass


class Crawl4aiConfig(BaseCrawlerConfig):
    """Crawl4ai config schema."""

    schema: dict
    wait_for: str | None = None
    js_code: list[str] | str | None = None
    css_selector: str | None = None
    browser_type: str = "chromium"
    page_timeout: int = 120000
    delay_before_return_html: int = 100
    headless: bool = False
    bypass_cache: bool = True

    @model_validator(mode="before")
    @classmethod
    def convert_js_code_to_list(cls, data: Any) -> Any:
        """Convert js_code to list[str]."""
        if isinstance(data, dict):
            js_code = data.get("js_code")
            if js_code and isinstance(js_code, str):
                data["js_code"] = [js_code]
        return data


# Leaderboard parser routes


class ModelParamsResponse(BaseModel):
    """Model params schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    uri: str
    num_params: int | None = None  # NOTE: optional to handle nullable num_params in architecture field


class LeaderboardResponse(BaseModel):
    """Leaderboard response schema."""

    # APAC Eval Leaderboard fields
    lc_win_rate: float | None = None

    # Berkeley Leaderboard fields
    bcfl: float | None = None

    # LiveCodeBench Leaderboard fields
    live_code_bench: float | None = None

    # MTEB Leaderboard fields
    classification: float | None = None
    clustering: float | None = None
    pair_classification: float | None = None
    reranking: float | None = None
    retrieval: float | None = None
    semantic: float | None = None
    summarization: float | None = None

    # UGI Leaderboard fields (with _score suffixes)
    ugi_score: float | None = None

    # VLLM Leaderboard fields
    mmbench: float | None = None
    mmstar: float | None = None
    mmmu: float | None = None
    math_vista: float | None = None
    ocr_bench: float | None = None
    ai2d: int | None = None
    hallucination_bench: float | None = None
    mmvet: float | None = None

    # Chatbot Arena Leaderboard fields
    lmsys_areana: int | None = None

    model_info: ModelParamsResponse


class LeaderboardListResponse(SuccessResponse):
    """Leaderboard list response schema."""

    leaderboards: list[dict] = []


class ModelInfoResponse(BaseModel):
    """Model info response schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    uri: str


class LeaderboardModelResponse(LeaderboardResponse):
    """Leaderboard model response schema."""

    model_info: ModelInfoResponse


class LeaderboardModelCompareResponse(SuccessResponse):
    """Leaderboard model compare response schema."""

    leaderboards: list[dict] = []


class LeaderboardResponse(BaseModel):
    """Leaderboard response schema."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    eval_name: str
    eval_label: str
    eval_score: float


class LeaderboardModelUrisResponse(BaseModel):
    """Leaderboard model compare response schema."""

    uri: str
    benchmarks: List[LeaderboardResponse]


class LeaderboardModelUrisListResponse(SuccessResponse):
    """Leaderboard model compare response schema."""

    leaderboards: List[LeaderboardModelUrisResponse]

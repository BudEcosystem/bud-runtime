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

"""The leaderboard CRUD operations."""

import uuid
from typing import Dict, List, Optional, Tuple

from budmicroframe.shared.psql_service import CRUDMixin
from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session
from sqlalchemy.types import BigInteger

from ..commons.constants import LeaderboardDataOrigin
from ..model_info.models import Leaderboard as LeaderboardModel
from ..model_info.models import ModelInfoSchema
from ..model_info.models import Source as SourceModel
from .schemas import LeaderboardCreate


class SourceCRUD(CRUDMixin[SourceModel, None, None]):
    """Source table CRUD operations."""

    __model__ = SourceModel

    def __init__(self) -> None:
        """Initialize the SourceCRUD class."""
        super().__init__(model=self.__model__)


class LeaderboardCRUD(CRUDMixin[LeaderboardModel, None, None]):
    """Leaderboard table CRUD operations."""

    __model__ = LeaderboardModel

    def __init__(self) -> None:
        """Initialize the LeaderboardCRUD class."""
        super().__init__(model=self.__model__)

    # def get_leaderboard_table_between_params(
    #     self,
    #     min_params: int,
    #     max_params: int,
    #     limit: int,
    #     session: Optional[Session] = None,
    # ) -> List[LeaderboardModel]:
    #     """Get the leaderboard table.

    #     Args:
    #         min_params: The minimum number of parameters.
    #         max_params: The maximum number of parameters.
    #         limit: The limit of the number of models to return.
    #         session: The session to use.

    #     Returns:
    #         The leaderboard table.

    #     NOTE: This function is DEPRECATED.
    #     """
    #     session: Session = session or self.get_session()

    #     # Create average calculation for all numeric fields
    #     avg_fields = [
    #         # APAC Eval Leaderboard fields
    #         LeaderboardModel.lc_win_rate,
    #         # Berkeley Leaderboard
    #         LeaderboardModel.bcfl,
    #         # LiveCodeBench
    #         LeaderboardModel.live_code_bench,
    #         # MTEB fields
    #         LeaderboardModel.classification,
    #         LeaderboardModel.clustering,
    #         LeaderboardModel.pair_classification,
    #         LeaderboardModel.reranking,
    #         LeaderboardModel.retrieval,
    #         LeaderboardModel.semantic,
    #         LeaderboardModel.summarization,
    #         # UGI Leaderboard fields (with _score suffixes)
    #         LeaderboardModel.ugi_score,
    #         # VLLM fields
    #         LeaderboardModel.mmbench,
    #         LeaderboardModel.mmstar,
    #         LeaderboardModel.mmmu,
    #         LeaderboardModel.math_vista,
    #         LeaderboardModel.ocr_bench,
    #         LeaderboardModel.ai2d,
    #         LeaderboardModel.hallucination_bench,
    #         LeaderboardModel.mmvet,
    #         # Arena
    #         LeaderboardModel.lmsys_areana,
    #     ]

    #     # Calculate sum of all fields cast to float
    #     sum_expr = sum(func.coalesce(field.cast(Float), 0) for field in avg_fields)

    #     # Count non-null fields
    #     count_expr = sum(case((field.isnot(None), 1), else_=0) for field in avg_fields)

    #     # Calculate average score
    #     avg_score = (sum_expr / func.nullif(count_expr, 0)).label("average_score")

    #     query = (
    #         session.query(
    #             ModelInfoSchema.uri.label("model_uri"),
    #             ModelInfoSchema.architecture["num_params"].astext.cast(BigInteger).label("num_params"),
    #             LeaderboardModel,
    #             avg_score,
    #         )
    #         .select_from(LeaderboardModel)
    #         .join(ModelInfoSchema, LeaderboardModel.model_info_id == ModelInfoSchema.id)
    #         .filter(ModelInfoSchema.architecture["num_params"].astext.cast(BigInteger).between(min_params, max_params))
    #         .group_by(ModelInfoSchema.uri, ModelInfoSchema.architecture, LeaderboardModel.id)
    #         .order_by(avg_score.desc())
    #         .limit(limit)
    #     )
    #     return query.all()

    def get_all_eval_names(self, session: Optional[Session] = None) -> List[str]:
        """Fetch all unique eval names in the LeaderboardModel table."""
        session: Session = session or self.get_session()
        query = session.query(LeaderboardModel.eval_name.distinct())
        return [row[0] for row in query.all()]

    # Helper to fetch full leaderboard (eval_name -> score) for model
    def get_leaderboard_by_model_info_id(
        self, model_info_id: uuid.UUID, session: Optional[Session] = None
    ) -> Dict[str, float]:
        """Get leaderboard data by model info ID."""
        session: Session = session or self.get_session()
        rows = (
            session.query(LeaderboardModel.eval_name, LeaderboardModel.eval_score)
            .filter(LeaderboardModel.model_info_id == model_info_id)
            .all()
        )
        return {row.eval_name: row.eval_score for row in rows if row.eval_score is not None}

    def get_leaderboard_with_current_model(
        self,
        current_model_info_id: uuid.UUID,
        min_params: int,
        max_params: int,
        limit: int,
        session: Optional[Session] = None,
    ) -> Tuple[List, List[str], List]:
        """Return raw leaderboard data needed to build the leaderboard table.

        The method returns the benchmark rows for the current model and the top
        models, the evaluation names associated with the current model and the
        ordered list of top models.  Any response formatting should be handled
        by the service layer.
        """
        session: Session = session or self.get_session()

        # Fetch eval names from the current model to ensure consistent
        # comparison across models.
        current_eval_names = [
            row[0]
            for row in session.query(LeaderboardModel.normalised_eval_name)
            .filter(
                LeaderboardModel.model_info_id == current_model_info_id,
                LeaderboardModel.eval_score is not None,
            )
            .distinct()
            .all()
        ]

        if not current_eval_names:
            return [], [], []

        # Subquery to compute the average score for other models using only the
        # evals present in the current model. This is used purely for ordering
        # the results.
        avg_score_subq = (
            session.query(
                LeaderboardModel.model_info_id,
                func.avg(LeaderboardModel.eval_score).label("average_score"),
            )
            .join(ModelInfoSchema, LeaderboardModel.model_info_id == ModelInfoSchema.id)
            .filter(
                ModelInfoSchema.architecture["num_params"].astext.cast(BigInteger).between(min_params, max_params),
                LeaderboardModel.model_info_id != current_model_info_id,
                LeaderboardModel.eval_score is not None,
                LeaderboardModel.normalised_eval_name.in_(current_eval_names),
            )
            .group_by(LeaderboardModel.model_info_id)
            .subquery()
        )

        # Query top models ordered by the computed average
        top_models = (
            session.query(
                LeaderboardModel.model_info_id,
                ModelInfoSchema.uri,
                ModelInfoSchema.architecture["num_params"].astext.cast(BigInteger).label("num_params"),
                avg_score_subq.c.average_score,
            )
            .join(ModelInfoSchema, LeaderboardModel.model_info_id == ModelInfoSchema.id)
            .join(avg_score_subq, LeaderboardModel.model_info_id == avg_score_subq.c.model_info_id)
            .group_by(
                LeaderboardModel.model_info_id,
                ModelInfoSchema.uri,
                ModelInfoSchema.architecture,
                avg_score_subq.c.average_score,
            )
            .order_by(desc(avg_score_subq.c.average_score))
            .limit(limit)
            .all()
        )

        top_model_ids = [row.model_info_id for row in top_models]

        # Fetch the current model information using the same eval name filter so
        # that the average is computed over the same set of benchmarks that will
        # be returned.
        current_model = (
            session.query(
                LeaderboardModel.model_info_id,
                ModelInfoSchema.uri,
                ModelInfoSchema.architecture["num_params"].astext.cast(BigInteger).label("num_params"),
                func.avg(LeaderboardModel.eval_score).label("average_score"),
            )
            .join(ModelInfoSchema, LeaderboardModel.model_info_id == ModelInfoSchema.id)
            .filter(
                LeaderboardModel.model_info_id == current_model_info_id,
                LeaderboardModel.eval_score is not None,
                LeaderboardModel.normalised_eval_name.in_(current_eval_names),
            )
            .group_by(
                LeaderboardModel.model_info_id,
                ModelInfoSchema.uri,
                ModelInfoSchema.architecture,
            )
            .first()
        )

        # Collect all model ids we need benchmark rows for
        all_model_ids = top_model_ids.copy()
        if current_model and current_model.model_info_id not in all_model_ids:
            all_model_ids = [current_model.model_info_id] + all_model_ids

        benchmarks = (
            session.query(
                LeaderboardModel.model_info_id,
                LeaderboardModel.normalised_eval_name,
                LeaderboardModel.eval_name,
                LeaderboardModel.eval_score,
            )
            .filter(
                LeaderboardModel.model_info_id.in_(all_model_ids),
                LeaderboardModel.eval_score is not None,
                LeaderboardModel.normalised_eval_name.in_(current_eval_names),
            )
            .all()
        )

        return list(benchmarks), current_eval_names, list(top_models)

    def get_leaderboards_by_models(
        self,
        model_uris: List[str],
        fields: Optional[List[str]] = None,
        limit: int = 10,
        session: Optional[Session] = None,
    ) -> List[dict]:
        """Get leaderboards by model URIs."""
        session: Session = session or self.get_session()

        # Step 1: Fetch unique eval_names only once if fields not given
        if not fields:
            fields = [row[0] for row in session.query(LeaderboardModel.normalised_eval_name.distinct()).all()]

        if not fields:
            return []

        # Step 2a: Build per-field max(score) expressions
        field_exprs = [
            func.max(
                case((LeaderboardModel.normalised_eval_name == field, LeaderboardModel.eval_score), else_=None)
            ).label(field)
            for field in fields
        ]
        # Step 2b: Build corresponding eval_name expressions
        eval_label_exprs = [
            func.max(
                case((LeaderboardModel.normalised_eval_name == field, LeaderboardModel.eval_name), else_=None)
            ).label(f"{field}_eval_label")
            for field in fields
        ]

        # Step 3: Compute average for sorting (not returned)
        avg_score = (
            sum(func.coalesce(column, 0.0) for column in field_exprs)
            / func.nullif(sum(case((column is not None, 1), else_=0) for column in field_exprs), 0)
        ).label("avg_score")

        # Step 4: Final query
        query = (
            session.query(ModelInfoSchema.uri.label("uri"), *field_exprs, *eval_label_exprs, avg_score)
            .join(ModelInfoSchema, ModelInfoSchema.id == LeaderboardModel.model_info_id)
            .filter(ModelInfoSchema.uri.in_(model_uris))
            .having(avg_score.isnot(None))
            .group_by(ModelInfoSchema.uri)
            .order_by(avg_score.desc())
            .limit(limit)
        )

        # Step 5: Parse and structure result
        results = []
        for row in query.all():
            row_dict = dict(row._mapping)
            parsed = {"uri": row_dict["uri"]}
            benchmarks = []
            for field in fields:
                score = row_dict.get(field)
                eval_label = row_dict.get(f"{field}_eval_label")
                if score is not None:
                    benchmarks.append({"eval_name": field, "eval_score": score, "eval_label": eval_label})
            if benchmarks:
                parsed["benchmarks"] = benchmarks
                results.append(parsed)

        return results

    def get_model_evals_by_uris(
        self,
        model_uris: List[str],
        session: Optional[Session] = None,
    ):
        """Get model evaluations by URIs."""
        session: Session = session or self.get_session()
        # Fetch all models with given URIs
        results = (
            session.query(
                ModelInfoSchema.uri,
                LeaderboardModel.eval_name,
                LeaderboardModel.normalised_eval_name,
                LeaderboardModel.eval_score,
            )
            .join(LeaderboardModel, ModelInfoSchema.id == LeaderboardModel.model_info_id)
            .filter(ModelInfoSchema.uri.in_(model_uris))
            .all()
        )

        return results

    def update_or_insert_leaderboards(
        self, model_info_id: uuid.UUID, entries: List[LeaderboardCreate], session: Optional[Session] = None
    ) -> None:
        """Update or insert leaderboard entries."""
        session: Session = session or self.get_session()

        # Fetch existing records with primary key (id) included
        existing = (
            session.query(
                LeaderboardModel.id,
                LeaderboardModel.normalised_eval_name,
                LeaderboardModel.eval_score,
                LeaderboardModel.data_origin,
            )
            .filter(LeaderboardModel.model_info_id == model_info_id)
            .all()
        )

        existing_map = {row.normalised_eval_name: row for row in existing}

        updates = []
        inserts = []

        for entry in entries:
            existing_entry = existing_map.get(entry.normalised_eval_name)

            if existing_entry:
                if entry.data_origin == LeaderboardDataOrigin.SCRAPED:
                    if (
                        existing_entry.data_origin == LeaderboardDataOrigin.SCRAPED
                        and entry.eval_score != existing_entry.eval_score
                    ):
                        updates.append(
                            {
                                "id": existing_entry.id,
                                "eval_score": entry.eval_score,
                            }
                        )
                    elif existing_entry.data_origin == LeaderboardDataOrigin.README_LLM:
                        updates.append(
                            {
                                "id": existing_entry.id,
                                "eval_score": entry.eval_score,
                                "data_origin": entry.data_origin,
                                "source_id": entry.source_id,
                            }
                        )
                elif entry.data_origin == LeaderboardDataOrigin.README_LLM and (
                    existing_entry.data_origin == LeaderboardDataOrigin.README_LLM
                    and entry.eval_score != existing_entry.eval_score
                ):
                    updates.append(
                        {
                            "id": existing_entry.id,
                            "eval_score": entry.eval_score,
                        }
                    )

            else:
                # Insert new row
                inserts.append(
                    LeaderboardModel(
                        model_info_id=model_info_id,
                        eval_name=entry.eval_name,
                        normalised_eval_name=entry.normalised_eval_name,
                        eval_score=entry.eval_score,
                        data_origin=entry.data_origin,
                        source_id=entry.source_id,
                    )
                )

        # Bulk update and insert
        if updates:
            session.bulk_update_mappings(LeaderboardModel, updates)
        if inserts:
            session.bulk_save_objects(inserts)

        session.commit()

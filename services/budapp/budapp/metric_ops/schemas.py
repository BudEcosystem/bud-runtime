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


"""Contains core Pydantic schemas used for data validation and serialization within the metric ops services."""

from ..commons.schemas import SuccessResponse


class DashboardStatsResponse(SuccessResponse):
    """Dashboard stats response schema."""

    total_model_count: int
    cloud_model_count: int
    local_model_count: int
    total_projects: int
    total_project_users: int
    total_endpoints_count: int
    running_endpoints_count: int
    total_clusters: int
    inactive_clusters: int

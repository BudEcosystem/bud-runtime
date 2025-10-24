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

"""The main entry point for the application, initializing the FastAPI app and setting up the application's lifespan management, including configuration and secret syncs."""

from budmicroframe.main import configure_app

from .commons.config import app_settings, secrets_settings


app = configure_app(app_settings, secrets_settings)

from .benchmark_ops.routes import benchmark_router  # noqa: E402
from .cluster_ops.routes import cluster_router  # noqa: E402
from .cluster_ops.workflows import *  # noqa: F403, E402
from .deployment.routes import deployment_router  # noqa: E402
from .deployment.workflows import *  # noqa: F403, E402
from .jobs.routes import job_router  # noqa: E402
from .metrics_collector.routes import metrics_router  # noqa: E402


app.include_router(deployment_router)
app.include_router(cluster_router)
app.include_router(benchmark_router)
app.include_router(job_router)
app.include_router(metrics_router)

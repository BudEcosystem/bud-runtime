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

from contextlib import asynccontextmanager

from budmicroframe.main import configure_app, dapr_lifespan
from fastapi import FastAPI
from starlette_compress import CompressMiddleware

from .cluster_metrics.routes import router as cluster_metrics_router
from .commons.config import app_settings, secrets_settings
from .commons.profiling_utils import performance_logger
from .observability.routes import observability_router
from .observability.usage_routes import usage_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    # Startup
    async with dapr_lifespan(app):
        if app_settings.debug:
            await performance_logger.start()
        yield
        # Shutdown
        if app_settings.debug:
            await performance_logger.stop()


app = configure_app(app_settings, secrets_settings, lifespan=lifespan)

# Add GZip middleware for compressing large responses
# minimum_size: Only compress responses larger than this number of bytes (1KB)
# compresslevel: 1-9, where 1 is fastest/least compression, 9 is slowest/most compression
# 6 is a good balance between speed and compression ratio for API responses
app.add_middleware(CompressMiddleware, minimum_size=1000, zstd_level=4, brotli_quality=4, gzip_level=4)

app.include_router(observability_router)
app.include_router(usage_router, prefix="/observability")
app.include_router(cluster_metrics_router)

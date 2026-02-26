#!/usr/bin/env bash

#
#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------
#

DAPR_COMPONENTS="../.dapr/components/"
DAPR_APP_CONFIG="../.dapr/appconfig-dev.yaml"

DOCKER_COMPOSE_FILE="./deploy/docker-compose-dev.yaml"
BUILD_FLAG=""
DETACH_FLAG=""

function display_help() {
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  --dapr-components        Set the dapr components folder path, this should be relative to the deploy directory (default: $DAPR_COMPONENTS)"
    echo "  --dapr-app-config        Set the dapr app config path, this should be relative to the deploy directory (default: $DAPR_APP_CONFIG)"
    echo "  -f FILE                  Specify the Docker Compose file to use, this should be relative to your current directory (default: $DOCKER_COMPOSE_FILE)"
    echo "  --build                  Include this flag to force a rebuild of the Docker containers"
    echo "  --skip-app               Include this flag to skip the app container"
    echo "  -d                       Include this flag to detach and run the containers in background"
    echo "  --help                   Display this help message and exit"
    echo
    echo "Example:"
    echo "  $0 -f docker-compose-local.yaml --build"
    echo "  This will use 'docker-compose-local.yaml' and force a rebuild of the containers."
    echo
    exit 0
}

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dapr-components) DAPR_COMPONENTS="$2"; shift ;;
        --dapr-app-config) DAPR_APP_CONFIG="$2"; shift ;;
        -f) DOCKER_COMPOSE_FILE="$2"; shift ;;
        --build) BUILD_FLAG="--build" ;;
        --skip-app) SKIP_APP_FLAG="true" ;;
        -d) DETACH_FLAG="-d" ;;
        --help) display_help ;;
        *) echo "Unknown parameter passed: $1"; show_help; exit 1 ;;
    esac
    shift
done

set -a
source ./.env
set +a

export REDIS_PORT=$(echo "${SECRETS_REDIS_URI:-redis:6379}" | cut -d':' -f2)

: ${APP_NAME:?Application name is required, use --app-name flag to specify the name.}

# Print the environment variables
echo "****************************************************"
echo "*                                                  *"
echo "*         Starting BudUseCases Service             *"
echo "*                                                  *"
echo "****************************************************"
echo ""
echo "🛠 App Name            : $APP_NAME"
echo "🌐 App Port             : $APP_PORT"
echo "🔑 Redis Uri           : $SECRETS_REDIS_URI"
echo "🌍 Dapr HTTP Port      : $DAPR_HTTP_PORT"
echo "🌍 Dapr gRPC Port      : $DAPR_GRPC_PORT"
echo "🛠 Namespace            : $NAMESPACE"
echo "📊 Log Level           : $LOG_LEVEL"
echo "🗂 Config Store Name    : $CONFIGSTORE_NAME"
echo "🔐 Secret Store Name   : $SECRETSTORE_NAME"
echo "🛠 Dapr Components     : $DAPR_COMPONENTS"
echo "🛠 Dapr App Config     : $DAPR_APP_CONFIG"
echo "🛠 Docker Compose File : $DOCKER_COMPOSE_FILE"
echo "🚀 Build flag          : $BUILD_FLAG"
echo ""
echo "****************************************************"

# Bring up Docker Compose
echo "Bringing up Docker Compose with file: $DOCKER_COMPOSE_FILE"
if [ -z "$SKIP_APP_FLAG" ]; then
    docker compose --profile app -f "$DOCKER_COMPOSE_FILE" up $BUILD_FLAG $DETACH_FLAG
else
    docker compose -f "$DOCKER_COMPOSE_FILE" up $BUILD_FLAG $DETACH_FLAG
fi

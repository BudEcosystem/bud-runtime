#!/bin/bash

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

# Default value for Docker Compose file
DOCKER_COMPOSE_FILE="./deploy/docker-compose-dev.yaml"

# Function to display help message
function display_help() {
    echo "Usage: $0 [options]"
    echo
    echo "Options:"
    echo "  -f FILE   Specify the Docker Compose file to use (default: deploy/docker-compose-dev.yaml)"
    echo "  --help                Display this help message and exit"
    echo
    echo "Example:"
    echo "  $0 -f docker-compose-local.yaml"
    echo "  This will stop the services using 'docker-compose-local.yaml'."
    echo
    exit 0
}

# Parse optional arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -f) DOCKER_COMPOSE_FILE="$2"; shift ;;
        --help) display_help ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

set -a
source ./.env
set +a

export REDIS_PORT=$(echo "${SECRETS_REDIS_URI:-redis:6379}" | cut -d':' -f2)

# Stop Docker Compose services
echo "Stopping services defined in: $DOCKER_COMPOSE_FILE"
docker compose -f "$DOCKER_COMPOSE_FILE" stop

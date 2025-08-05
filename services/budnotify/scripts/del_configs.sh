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

# Initialize variables
container=""
password=""
keys=()

function display_help() {
    echo "Usage: del_configs.sh --container <container_name> [--password <password>] [--key <key>]..."
    echo
    echo "Options:"
    echo "  --container   Name of the container where Redis is running (required)"
    echo "  --password    Redis password (optional)"
    echo "  --<key>         Configuration key to delete from the store (multiple keys can be deleted)"
    echo "  --help        Display this help message and exit"
    echo
    echo "Examples:"
    echo "  ./scripts/del_configs.sh --container my_redis_container --setting1 --setting2"
    echo "  ./scripts/del_configs.sh --container my_redis_container --password mypassword --setting1"
    exit 0
}

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --container) container="$2"; shift ;;
        --password) password="$2"; shift ;;
        --help) display_help ;;
        --*) key="${1:2}"; keys+=("$key") ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Check if container name is provided
if [ -z "$container" ]; then
    echo "Error: --container is required"
    exit 1
fi

# Check if at least one key is provided
if [ ${#keys[@]} -eq 0 ]; then
    echo "Error: At least one key is required"
    exit 1
fi

# Construct the redis-cli DEL command
del_command="DEL ${keys[@]}"

# Check if password is provided and modify the command accordingly
if [ -n "$password" ]; then
    auth_command="-a $password $del_command"
else
    auth_command="$del_command"
fi

# Execute the command in the specified container
docker exec "$container" redis-cli $auth_command

# Print a message indicating success
echo "Executed command: docker exec $container redis-cli $auth_command"

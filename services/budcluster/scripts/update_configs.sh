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
keys_values=()

function display_help() {
    echo "Usage: ./update_configs.sh --container <container_name> [--password <password>] --<key> <value> [--<key2> <value2> ...]"
    echo
    echo "This script is used to add key-value pairs to a Redis config store running inside a Docker container."
    echo
    echo "Options:"
    echo "  --container   The name of the Docker container running Redis (Required)"
    echo "  --password    The password for Redis, if required (Optional)"
    echo "  --<key>       The key for the config value (At least one key-value pair is required)"
    echo "  <value>       The value associated with the key"
    echo "  --help        Display this help message and exit"
    echo
    echo "Example:"
    echo "  ./scripts/update_configs.sh --container my_redis_container --password mypassword --setting1 value1 --setting2 value2"
    exit 0
}

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --container) container="$2"; shift ;;
        --password) password="$2"; shift ;;
        --help) display_help ;;
        --*) key="${1:2}"; value="$2"; keys_values+=("$key" "$value"); shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Check if container name is provided
if [ -z "$container" ]; then
    echo "Error: --container is required"
    exit 1
fi

# Check if at least one key-value pair is provided
if [ ${#keys_values[@]} -eq 0 ]; then
    echo "Error: At least one key-value pair is required"
    exit 1
fi

# Construct the redis-cli MSET command
mset_command="MSET ${keys_values[@]}"

# Check if password is provided and modify the command accordingly
if [ -n "$password" ]; then
    cli_command="-a $password $mset_command"
else
    cli_command="$mset_command"
fi

# Execute the command in the specified container
docker exec "$container" redis-cli $cli_command

# Print a message indicating success
echo "Executed command: docker exec $container redis-cli $cli_command"

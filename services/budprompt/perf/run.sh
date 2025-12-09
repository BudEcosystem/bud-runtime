#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"

echo 'POST http://localhost:9088/v1/responses' \
| vegeta attack \
    -header="Content-Type: application/json" \
    -header="Authorization: Bearer bud_admin_1qvc0eSofAdihRSp37hi34FjZMgpb_Re5JIkbhUkqG0" \
    -body=$SCRIPT_DIR/body.json \
    -duration=10s \
    -rate=100 \
    -timeout=30s \
| vegeta report

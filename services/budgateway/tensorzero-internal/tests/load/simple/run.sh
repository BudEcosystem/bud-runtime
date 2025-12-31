#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"

echo 'POST http://gateway.intuixai.local/v1/embeddings' \
| vegeta attack \
    -header="Content-Type: application/json" \
    -header="Authorization: Bearer bud_admin_PNYOVkPFgIeZbC4X9ABPcRrFzpbp-0yKKIxVlCRj29o" \
    -body=$SCRIPT_DIR/body.json \
    -duration=60s \
    -rate=30 \
    -timeout=300s \
| vegeta report

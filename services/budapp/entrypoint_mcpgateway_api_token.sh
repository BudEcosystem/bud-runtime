#!/usr/bin/env bash

set -o errexit -o pipefail

note() {
	printf "\033[32;1mentrypoint_mcpgateway_api_token_sh: %b\033[0m\n" "$*"
}

curl_wrapped() {
	curl --retry 5 \
		--connect-timeout 600 \
		--max-time 600 \
		--header 'accept: application/json' \
		--header 'Content-Type: application/json' "$@"
}

access_token_get() {
	resp="$(
		curl_wrapped \
			--location "$ENTRYPOINT_MCPGATEWAY_SERVICE/auth/login" \
			--data-binary @- <<-EOF
				{
					  "email": "$ENTRYPOINT_MCPGATEWAY_EMAIL",
					  "password": "$ENTRYPOINT_MCPGATEWAY_PASSWORD"
				}
			EOF
	)"

	echo "$resp" | jq --exit-status --raw-output '.access_token'
}

api_token_get() {
	access_token="$1"

	resp="$(
		curl_wrapped \
			--location "$ENTRYPOINT_MCPGATEWAY_SERVICE/tokens" \
			--header "Authorization: Bearer $access_token" \
			--data-binary @- <<-EOF
				{
				  "name": "entrypoint-mcpgateway-api-token-sh-$(date +%s%N)",
				  "description": "Autocreated by budprompt entrypoint_mcpgateway_api_token.sh",
				  "scope": {
				    "permissions": [],
				    "ip_restrictions": [],
				    "time_restrictions": {},
				    "usage_limits": {}
				  },
				  "tags": [],
				  "team_id": null
				}
			EOF
	)"

	echo "$resp" | jq --exit-status --raw-output '.access_token'
}

while [ -z "$MCP_FOUNDRY_API_KEY" ] &&
	[ -n "$ENTRYPOINT_MCPGATEWAY_SERVICE" ] &&
	[ -n "$ENTRYPOINT_MCPGATEWAY_PASSWORD" ] &&
	[ -n "$ENTRYPOINT_MCPGATEWAY_EMAIL" ]; do
	note fetching mcp gateway api token from "$ENTRYPOINT_MCPGATEWAY_SERVICE"

	access_token="$(access_token_get)"
	note access_token="$access_token"
	api_token="$(api_token_get "$access_token")"
	note api_token="$api_token"
	export MCP_FOUNDRY_API_KEY="$api_token"
done

exec "$@"

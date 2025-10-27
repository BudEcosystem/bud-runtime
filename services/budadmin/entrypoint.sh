#!/bin/sh
set -e

# Debugging: Print environment variables to make sure they exist
echo "Environment variables: "
printenv | grep NEXT_PUBLIC_

# Fetch dynamic environment variable
NEXT_PUBLIC_NOVU_APP_ID=$(curl -s --retry 5 --connect-timeout 600 --max-time 600 --location "http://$ENTRYPOINT_BUDNOTIFY_SERVICE/settings/credentials" \
  --header 'accept: application/json' | jq -r '.prod_app_id')

# Export it so it's available in printenv
export NEXT_PUBLIC_NOVU_APP_ID

# Replace env variable placeholders with real values
# Store environment variables to avoid pipe input stream conflict
ENV_VARS=$(printenv | grep NEXT_PUBLIC_)

# Process each environment variable
echo "$ENV_VARS" | while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue

  key=$(echo "$line" | cut -d "=" -f1)
  value=$(echo "$line" | cut -d "=" -f2-)

  # Debugging: Print the key and value being processed
  echo "Processing: Key = $key, Value = $value"

  # Replace in all .js files using find -exec to avoid nested pipes
  find /usr/bin/src/.next/ -type f -name "*.js" -exec sed -i "s|$key|$value|g" {} \;

  echo "Replaced $key with $value in .js files"
done

# Debugging: Check if the next start process is hanging
echo "Starting Next.js..."
exec "$@"

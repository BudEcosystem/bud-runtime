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

# Ensure all branding variables are present (set to placeholder if not provided)
# This ensures they get processed even if not set at runtime
export NEXT_PUBLIC_LOGO_URL="${NEXT_PUBLIC_LOGO_URL:-NEXT_PUBLIC_LOGO_URL}"
export NEXT_PUBLIC_LOGO_AUTH_URL="${NEXT_PUBLIC_LOGO_AUTH_URL:-NEXT_PUBLIC_LOGO_AUTH_URL}"
export NEXT_PUBLIC_FAVICON_URL="${NEXT_PUBLIC_FAVICON_URL:-NEXT_PUBLIC_FAVICON_URL}"

# Replace env variable placeholders with real values
# Store environment variables to avoid pipe input stream conflict
ENV_VARS=$(printenv | grep NEXT_PUBLIC_)

# Process each environment variable
echo "$ENV_VARS" | while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue

  key=$(echo "$line" | cut -d "=" -f1)
  value=$(echo "$line" | cut -d "=" -f2-)

  # If value equals the key name (placeholder not replaced), use default path
  # This ensures both server-rendered HTML and client-side JS use correct defaults
  if [ "$value" = "$key" ]; then
    case "$key" in
      "NEXT_PUBLIC_LOGO_URL") value="/images/logo.svg" ;;
      "NEXT_PUBLIC_LOGO_AUTH_URL") value="/images/BudLogo.png" ;;
      "NEXT_PUBLIC_FAVICON_URL") value="/favicon.ico" ;;
      *) value="" ;;
    esac
  fi

  # Debugging: Print the key and value being processed
  echo "Processing: Key = $key, Value = $value"

  # Replace in all .js and .html files using find -exec to avoid nested pipes
  find /usr/bin/src/.next/ -type f \( -name "*.js" -o -name "*.html" \) -exec sed -i "s|$key|$value|g" {} \;

  echo "Replaced $key with $value in .js and .html files"
done

# Debugging: Check if the next start process is hanging
echo "Starting Next.js..."
exec "$@"

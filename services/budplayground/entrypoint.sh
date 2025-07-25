#!/bin/sh
set -e

# Debugging: Print environment variables to make sure they exist
echo "Environment variables: "
printenv | grep NEXT_PUBLIC_

# Replace env variable placeholders with real values
printenv | grep NEXT_PUBLIC_ | while read -r line; do
  key=$(echo "$line" | cut -d "=" -f1)
  value=$(echo "$line" | cut -d "=" -f2-)

  # Debugging: Print the key and value being processed
  echo "Processing: Key = $key, Value = $value"

  # Recursively process all .js files only
  find /usr/bin/src/.next/ -type f -name "*.js" | while read -r file; do
    echo "Processing file: $file"
    sed -i "s|$key|$value|g" "$file"
  done

  echo "Replaced $key with $value in .js files"
done

# Debugging: Check if the next start process is hanging
echo "Starting Next.js..."
exec "$@"

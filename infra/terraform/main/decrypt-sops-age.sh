#!/usr/bin/env bash

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
sops_key_path="var/secrets/devbox.sops"

mkdir -p "$(dirname "$sops_key_path")"
umask 0177
sops --extract '["devbox_sops"]' --decrypt "$script_dir/secrets.yaml" > "$sops_key_path"
umask 0022

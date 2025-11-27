{
  writeShellApplication,
  yq,
  coreutils,
}:
writeShellApplication {
  name = "no_new_global_env";

  runtimeInputs = [
    coreutils
    yq
  ];

  text = ''
    set -o errexit

    max_global_env_count="93"
    value_path="$(git rev-parse --show-toplevel)/infra/helm/bud/values.yaml"
    global_env_count="$(yq -r '.microservices.global.env | keys | length' "$value_path")"

    echo "max_global_env_count : $max_global_env_count"
    echo "global_env_count     : $global_env_count"
    if [ "$global_env_count" -gt "$max_global_env_count" ]; then
      echo "Failure"
      echo ""
      echo "Please avoiding adding new global envs(.microservices.global.env)"
      echo "to the helm chart use .microservices.<service_name>.env instead"
      exit 1
    else
      echo "Success"
    fi
  '';
}

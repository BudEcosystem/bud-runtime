{
  budcustomer,
  lib,
  dockerTools,
  curl,
  writeShellApplication,
  jq,
  coreutils,
  gnused,
  gnugrep,
  findutils,
}:
let
  port = 3000;

  novu_id_env_setter = writeShellApplication {
    name = "novu_id_env_setter";
    runtimeInputs = [
      curl
      jq
      coreutils
      gnused
      gnugrep
      findutils
    ];

    text = ''
      note() {
        echo "entrypoint: $*"
      }

      # fetch novu app id
      note "fetching api key from $ENTRYPOINT_BUDNOTIFY_SERVICE"
      set +o errexit
      novu_app_id="$(curl --retry 5 \
        --connect-timeout 600 \
        --max-time 600 \
        --location "http://$ENTRYPOINT_BUDNOTIFY_SERVICE/settings/credentials" \
        --header 'accept: application/json' | jq -r '.prod_app_id')"
      set -o errexit
      export NEXT_PUBLIC_NOVU_APP_ID="$novu_app_id"

      # runtime env injection hack
      printenv | grep NEXT_PUBLIC_ | while read -r line; do
        key=$(echo "$line" | cut -d "=" -f1)
        value=$(echo "$line" | cut -d "=" -f2-)
        echo "Processing: Key = $key, Value = $value"
        find "$2/share/budcustomer" -type f -name "*.js" | while read -r file; do
          echo "Processing file: $file"
          sed -i "s|$key|$value|g" "$file"
        done
        echo "Replaced $key with $value in .js files"
      done

      exec "$1"
    '';
  };
in
dockerTools.buildLayeredImage {
  name = "budstudio/budcustomer";
  tag = "git";

  contents = [
    budcustomer
    novu_id_env_setter
    dockerTools.binSh # npm error enoent spawn sh ENOENT
  ];

  config = {
    Cmd = [
      (lib.getExe novu_id_env_setter)
      (lib.getExe budcustomer)
      (toString budcustomer)
    ];
    Env = [
      "PORT=${builtins.toString port}"
    ];
    ExposedPorts = {
      "${builtins.toString port}/tcp" = { };
    };
  };
}

{
  budcustomer,
  lib,
  dockerTools,
  curl,
  writeShellApplication,
  jq,
}:
let
  port = 3000;

  novu_id_env_setter = writeShellApplication {
    name = "novu_id_env_setter";
    runtimeInputs = [
      curl
      jq
    ];

    text = ''
      note() {
        echo "novu_id_env_setter: $*"
      }

      note "fetching api key from $ENTRYPOINT_BUDNOTIFY_SERVICE"

      set +o errexit
      novu_app_id="$(curl --retry 5 \
        --connect-timeout 600 \
        --max-time 600 \
        --location "http://$ENTRYPOINT_BUDNOTIFY_SERVICE/settings/credentials" \
        --header 'accept: application/json' | jq -r '.prod_app_id')"
      set -o errexit

      note "execing into $1 with NEXT_PUBLIC_NOVU_APP_ID=$novu_app_id"
      NEXT_PUBLIC_NOVU_APP_ID="$novu_app_id" exec "$1"
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
    ];
    Env = [
      "PORT=${builtins.toString port}"
    ];
    ExposedPorts = {
      "${builtins.toString port}/tcp" = { };
    };
  };
}

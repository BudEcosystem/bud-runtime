{
  budcustomer,
  lib,
  dockerTools,
}:
let
  port = 3000;
in
dockerTools.buildLayeredImage {
  name = "budstudio/budcustomer";
  tag = "nightly";

  contents = [
    budcustomer
    dockerTools.binSh # npm error enoent spawn sh ENOENT
  ];

  config = {
    Cmd = [
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

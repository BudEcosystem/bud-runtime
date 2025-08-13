{
  caddy,
  lib,
  dockerTools,
}:
let
  port = 80;
in
dockerTools.buildLayeredImage {
  name = "budstudio/status";
  tag = "latest";
  contents = [ caddy ];

  config = {
    Cmd = [
      (lib.getExe caddy)
      "file-server"
      "--root"
      ./web
      "--listen"
      "0.0.0.0:${toString port}"
    ];

    Env = [
      "PORT=${builtins.toString port}"
    ];
    ExposedPorts = {
      "${builtins.toString port}/tcp" = { };
    };
  };
}

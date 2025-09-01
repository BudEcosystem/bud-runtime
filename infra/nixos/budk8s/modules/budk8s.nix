{ lib, ... }:
{
  options.global.budk8s = {
    primaryIp = lib.mkOption {
      type = lib.types.str;
      example = "10.177.2.69";
      default = "10.177.2.69";
    };
  };
}

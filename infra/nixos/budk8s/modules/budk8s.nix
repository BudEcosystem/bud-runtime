{
  lib,
  primaryIp ? "10.177.2.69",
  ...
}:
{
  options.global.budk8s = {
    primaryIp = lib.mkOption {
      type = lib.types.str;
      example = "192.168.29.69";
      default = primaryIp;
    };
  };
}

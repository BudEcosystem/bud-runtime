{
  config,
  lib,
  ...
}:
let
  wheelUsers = builtins.attrNames (
    lib.attrsets.filterAttrs (key: val: builtins.elem "wheel" val.extraGroups) config.users.users
  );
in
{
  virtualisation.docker = {
    enable = true;
    autoPrune.enable = true;
  };

  users.extraGroups.docker.members = [ wheelUsers ];
}

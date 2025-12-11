{ lib, ... }:
let
  userName = "bud";
in
{
  services.getty = {
    greetingLine = ''
      BUD NIXOS IMAGE
    '';
    helpLine = lib.mkForce ''
      Default Username: ${userName}
      Default Password: ${userName}

      Run `bud-settings` to modify bud configuration";
      Run `passwd` to change the default password
    '';
  };

  users.users.${userName} = {
    uid = 6767;
    isNormalUser = true;
    initialPassword = userName;
    description = "Bud Maintenance User";
    extraGroups = [ "wheel" ];
  };
}

{ ... }:
let
  userName = "bud";
in
{
  services.getty = {
    greetingLine = ''
      ______ _   _______   ________  ___  ___  _____  _____ 
      | ___ \ | | |  _  \ |_   _|  \/  | / _ \|  __ \|  ___|
      | |_/ / | | | | | |   | | | .  . |/ /_\ \ |  \/| |__  
      | ___ \ | | | | | |   | | | |\/| ||  _  | | __ |  __| 
      | |_/ / |_| | |/ /   _| |_| |  | || | | | |_\ \| |___ 
      \____/ \___/|___/    \___/\_|  |_/\_| |_/\____/\____/
    '';
    helpLine = ''
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

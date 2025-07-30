{ ... }:
{
  users.users = {
    "athul" = {
      isNormalUser = true;
      extraGroups = [ "wheel" ];

      openssh.authorizedKeys.keys = [
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzvzpqulvlwby+7PQUKD6JOPJvyjAi70M+TlsenDIxn athul@accubits.com"
      ];
    };
  };
}

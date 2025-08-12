{ pkgs, lib, ... }:
let
  script = pkgs.callPackage ./package.nix { };
  sops_key_path = "/var/secrets/master.sops";
in
{
  systemd =
    let
      name = "helm-nixos-cd";
      meta.description = "NixOS Helm CD For Bud (github:BudEcosystem/bud-runtime:infra/helm)";
    in
    {
      timers.${name} = meta // {
        wantedBy = [ "timers.target" ];

        timerConfig = {
          OnCalendar = "*:0/1";
          Persistent = true;
        };
      };

      services.${name} = meta // {
        serviceConfig = {
          StateDirectory = name;
          WorkingDirectory = "%S/${name}";
          ExecStart = lib.getExe script;
          Environment = [ "SOPS_AGE_KEY_FILE=${sops_key_path}" ];
        };
      };
    };
}

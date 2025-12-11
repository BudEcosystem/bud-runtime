{
  config,
  pkgs,
  lib,
  ...
}:
let
  wgInterface = "wg";
  wanInterface = "eth0";
  port = 51820;

  wgConf = pkgs.writeText "wg.conf" ''
    [interface]
    Address = 10.54.132.1/24
    MTU = 1420
    ListenPort = ${toString port}
    PostUp = ${
      lib.getExe (
        pkgs.writeShellApplication {
          name = "wg_set_key";
          runtimeInputs = with pkgs; [ wireguard-tools ];
          text = ''
            wg set ${wgInterface} private-key <(cat ${config.sops.secrets."misc/wireguard".path})
          '';
        }
      )
    }

    [Peer]
    # friendly_name = sinan_cez
    PublicKey = IcMpAs/D0u8O/AcDBPC7pFUYSeFQXQpTqHpGOeVpjS8=
    AllowedIPs = 10.54.132.2/32

    [Peer]
    # friendly_name = sinan_exy
    PublicKey = bJ9aqGYD2Jh4MtWIL7q3XxVHFuUdwGJwO8p7H3nNPj8=
    AllowedIPs = 10.54.132.3/32

    [Peer]
    # friendly_name = ditto
    PublicKey = moSdO8FsGvJGnS3X09lqv0Fx3Pm+haHcBivuWylUk1k=
    AllowedIPs = 10.54.132.4/32

    [Peer]
    # friendly_name = varun
    PublicKey = 0p3WlvhxK6HKq2tFapQvjCogeABgPcUjwW3veN3qGyw=
    AllowedIPs = 10.54.132.5/32

    [Peer]
    # friendly_name = adarsh
    PublicKey = H8awlBbJtoNKiEZruBVzqk0KzSc6u2VbCc8iPwwaQUc=
    AllowedIPs = 10.54.132.6/32

    [Peer]
    # friendly_name = karthik
    PublicKey = MS4oL6uihxlozA61FYgBHl5fz7ck5d5gOdW1DXCkSSk=
    AllowedIPs = 10.54.132.7/32
  '';
in
{
  sops.secrets."misc/wireguard".sopsFile = ./secrets.yaml;
  services.k3s.extraFlags = [ "--tls-san 10.54.132.1" ];

  networking = {
    nat = {
      enable = true;
      externalInterface = wanInterface;
      internalInterfaces = [ wgInterface ];
    };

    firewall = {
      allowedUDPPorts = [ port ];
      interfaces.${wgInterface} = {
        allowedTCPPortRanges = [
          {
            from = 1;
            to = 65535;
          }
        ];
        allowedUDPPortRanges = [
          {
            from = 1;
            to = 65535;
          }
        ];
      };
    };

    wg-quick.interfaces.${wgInterface}.configFile = builtins.toString wgConf;
  };
}

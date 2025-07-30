{
  config,
  pkgs,
  lib,
  ...
}:
let
  nameServer = [
    "1.1.1.1"
    "8.8.8.8"
  ];

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
  '';
in
{
  sops.secrets."misc/wireguard" = { };
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
        allowedTCPPortRanges = [{
          from = 1;
          to = 65535;
        }];
        allowedUDPPortRanges = [{
          from = 1;
          to = 65535;
        }];
      };
    };

    wg-quick.interfaces.${wgInterface}.configFile = builtins.toString wgConf;
  };

  services.dnsmasq = {
    enable = true;
    settings = {
      bind-interfaces = true;
      server = nameServer;
      interface = [ wgInterface ];
      no-dhcp-interface = wgInterface;
    };
  };
}

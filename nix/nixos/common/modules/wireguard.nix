{
  config,
  pkgs,
  lib,
  ...
}:
let
  wgInterface = "wg";
  wanInterface = "ppp0";
  port = 51820;

  wgConf = pkgs.writeText "wg.conf" ''
    [interface]
    Address = 10.0.1.1/24
    MTU = 1412
    ListenPort = 51820
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
    # friendly_name = cez
    PublicKey = IcMpAs/D0u8O/AcDBPC7pFUYSeFQXQpTqHpGOeVpjS8=
    AllowedIPs = 10.0.1.2/32

    [Peer]
    # friendly_name = exy
    PublicKey = bJ9aqGYD2Jh4MtWIL7q3XxVHFuUdwGJwO8p7H3nNPj8=
    AllowedIPs = 10.0.1.3/32

    [Peer]
    # friendly_name = dad
    PublicKey = q70IyOS2IpubIRWqo5sL3SeEjtUy2V/PT8yqVExiHTQ=
    AllowedIPs = 10.0.1.4/32
  '';
in
{
  sops.secrets."misc/wireguard" = { };

  networking = {
    nat = {
      enable = true;
      externalInterface = wanInterface;
      internalInterfaces = [ wgInterface ];
    };

    firewall.allowedUDPPorts = [ port ];
    wg-quick.interfaces.${wgInterface}.configFile = builtins.toString wgConf;
  };

  services.dnsmasq.settings = {
    no-dhcp-interface = wgInterface;
    interface = [ wgInterface ];
  };

  services.prometheus.exporters.wireguard = {
    enable = true;
    withRemoteIp = true;
    wireguardConfig = builtins.toString wgConf;
    singleSubnetPerField = true;
    listenAddress = "127.0.0.1";
  };
}

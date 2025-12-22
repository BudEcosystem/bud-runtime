nixosModules:
{
  system,
  nixos-generators,
  lib,
  disko,
}:
let
  imageForFormat =
    format:
    nixos-generators.nixosGenerate {
      inherit system format;

      modules = [
        # nixosModules.common
        (
          { modulesPath, ... }:
          {
            imports = [
              "${toString modulesPath}/installer/tools/tools.nix"
            ];
            environment.systemPackages = [
              disko.packages.${system}.disko
            ];
            services.cloud-init = {
              enable = true;
              network.enable = true;
            };
            networking.useNetworkd = true;
          }
        )
      ];
    };

  supportedFormats = [
    "qcow"
    "kexec"
    "kexec-bundle"
  ];

  attrPrefixImage = name: value: lib.attrsets.nameValuePair ("image_installer_" + name) value;
  images = lib.genAttrs supportedFormats imageForFormat;
in
lib.attrsets.mapAttrs' attrPrefixImage images

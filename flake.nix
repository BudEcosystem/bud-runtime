{
  inputs = {
    nixpkgs.url = "github:NixOs/nixpkgs/nixos-unstable";
    nixos-facter-modules.url = "github:nix-community/nixos-facter-modules";

    sinan = {
      url = "github:sinanmohd/nixos/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    disko = {
      url = "github:nix-community/disko/latest";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      sinan,
      disko,
      nixos-facter-modules,
    }:
    let
      lib = nixpkgs.lib;

      forSystem =
        f: system:
        f {
          inherit system;
          pkgs = import nixpkgs { inherit system; };
        };
      supportedSystems = lib.platforms.unix;
      forAllSystems = f: lib.genAttrs supportedSystems (forSystem f);
      forLinuxSystems = f: lib.genAttrs lib.platforms.linux (forSystem f);
      pkgs = import nixpkgs { system = "x86_64-linux"; };

      makeNixos =
        host: system:
        lib.nixosSystem {
          inherit system;

          modules = [
            {
              networking.hostName = host;
            }

            disko.nixosModules.disko
            sinan.nixosModules.server
            nixos-facter-modules.nixosModules.facter

            ./nix/nixos/${host}/configuration.nix
          ];
        };
    in
    {
      devShells = forAllSystems (
        { system, pkgs }:
        {
          bud = pkgs.callPackage ./nix/shell.nix {
            self = self;
          };

          default = self.devShells.${system}.bud;
        }
      );

      packages =
        lib.recursiveUpdate
          (forAllSystems (
            { system, pkgs }:
            {
              workflow_devbox_tofu_apply = pkgs.callPackage ./nix/workflows/devbox_tofu_apply { };
              budcustomer = pkgs.callPackage ./nix/packages/budcustomer.nix { };
            }
          ))
          (
            forLinuxSystems (
              { system, pkgs }:
              {
                container_devbox = pkgs.callPackage ./nix/container/devbox { };
                container_budcustomer = pkgs.callPackage ./nix/container/budcustomer.nix {
                  budcustomer = self.packages.${system}.budcustomer;
                };
              }
            )
          );

      nixosConfigurations = lib.genAttrs [
        "common"
        "devbox"
      ] (host: makeNixos host "x86_64-linux");
    };
}

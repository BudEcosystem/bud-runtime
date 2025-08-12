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
          bud = pkgs.callPackage ./nix/shell {
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
              workflow_tofu_apply = pkgs.callPackage ./nix/workflows/tofu_apply { };
              workflow_dockerhub_budcustomer = pkgs.callPackage ./nix/workflows/dockerhub_budcustomer { };

              budcustomer = pkgs.callPackage ./nix/packages/budcustomer.nix { };
            }
          ))
          (
            forLinuxSystems (
              { system, pkgs }:
              {
                container_status = pkgs.callPackage ./nix/container/status { };
                container_budcustomer = pkgs.callPackage ./nix/container/budcustomer.nix {
                  budcustomer = self.packages.${system}.budcustomer;
                };
              }
            )
          );

      nixosConfigurations = lib.genAttrs [
        "common"
        "master"
      ] (host: makeNixos host "x86_64-linux");
    };
}

{
  inputs = {
    nixpkgs.url = "github:NixOs/nixpkgs/nixos-unstable";
    nixos-facter-modules.url = "github:nix-community/nixos-facter-modules";
    pre-commit-hooks.url = "github:cachix/git-hooks.nix";

    sinan = {
      url = "github:sinanmohd/nixos/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    scid = {
      url = "github:sinanmohd/scid/master";
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
      pre-commit-hooks,
      scid,
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
            scid.nixosModules.scid
            nixos-facter-modules.nixosModules.facter

            ./infra/nixos/${host}/configuration.nix
          ];
        };
    in
    {
      checks = forAllSystems (
        { system, pkgs }:
        {
          pre-commit-check = pre-commit-hooks.lib.${system}.run {
            src = ./.;
            # https://devenv.sh/reference/options/#git-hooks
            hooks = {
              actionlint.enable = true;
              nixfmt-rfc-style.enable = true;
              check-added-large-files.enable = true;
              check-case-conflicts.enable = true;
              check-executables-have-shebangs.enable = true;
              check-json.enable = true;
              check-merge-conflicts.enable = true;
              check-symlinks.enable = true;
              check-toml.enable = true;
              check-vcs-permalinks = {
                enable = true;
                excludes = [
                  "services/budadmin/public/login_files/.*"
                  "node_modules/.*"
                ];
              };

              check-xml.enable = true;

              check-yaml = {
                enable = true;
                excludes = [
                  "infra/helm/.*\.yaml"
                  "services/.*/charts/.*/templates/.*\.yaml"
                  "services/.*/examples/.*/templates/.*\.yaml"
                  "services/budnotify/deploy/kubernetes/.*\.yaml"
                  ".*\.minijinja$"
                ];
              };
              detect-private-keys = {
                enable = true;
                excludes = [
                  "services/budcluster/crypto-keys/.*\.pem"
                  "services/budgateway/docs/.*\.md"
                  "services/budgateway/CLAUDE\.md"
                  "services/budgateway/ci/dummy-gcp-credentials\.json"
                  "infra/helm/bud/charts/novu/values\.yaml"
                  "services/budgateway/tensorzero-internal/src/inference/providers/gcp_vertex_gemini\.rs"
                  "\.env\.sample"
                ];
              };

              trim-trailing-whitespace.enable = true;
              end-of-file-fixer.enable = true;

              shellcheck = {
                enable = true;
                excludes = [ "services/.*" ];
              };
            };
          };
        }
      );

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
              workflow_budcustomer_bumper = pkgs.callPackage ./nix/workflows/budcustomer_bumper { };
              workflow_dockerhub_budcustomer = pkgs.callPackage ./nix/workflows/dockerhub_budcustomer { };

              budcustomer = pkgs.callPackage ./nix/packages/budcustomer.nix { };
              no_new_global_env = pkgs.callPackage ./nix/packages/no_new_global_env.nix { };
              k8s_deploy = pkgs.callPackage ./nix/packages/k8s_deploy { };
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
        # generic budk8s iso
        "primary"

        # dev.bud.studio specific, cause of ./infra/nixos/dev
        "primary-dev"
        "ingress"
        "worker"
      ] (host: makeNixos host "x86_64-linux");
    };
}

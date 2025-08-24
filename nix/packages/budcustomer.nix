{
  lib,
  stdenv,
  nodejs,
  pnpm,
  makeWrapper
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "budcustomer";
  version = "git";
  src = ../../services/budCustomer;

  postPatch = ''
    cp .env.hack .env
  '';
  buildPhase = ''
    export npm_config_nodedir=${nodejs}
    pnpm exec next build
  '';

  installPhase = ''
    mkdir -p $out/share
    rm -rf ./src
    cp -r ./.  $out/share/budcustomer
    makeWrapper "${lib.getExe pnpm}" "$out/bin/budcustomer" \
      --run "cd $out/share/budcustomer" \
      --add-flags "start"
  '';

  nativeBuildInputs = [
    pnpm
    pnpm.configHook
    nodejs
    makeWrapper
  ];

  pnpmDeps = pnpm.fetchDeps {
    inherit (finalAttrs) pname version src;
    fetcherVersion = 2;
    hash = builtins.readFile ../../services/budCustomer/nix.hash;
  };

  meta = {
    description = "Bud customer nextjs frontend";
    homepage = "https://bud.studio";
    license = lib.licenses.gpl3;
    mainProgram = "budcustomer";
    maintainers = with lib.maintainers; [ sinanmohd ];
  };
})

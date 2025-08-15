{
  lib,
  buildNpmPackage,
  nodejs,
}:

buildNpmPackage {
  name = "budcustomer";
  src = ../../services/budCustomer;
  npmDepsHash = builtins.readFile ../../services/budCustomer/nix.hash;

  installPhase = ''
    mkdir -p $out/share

    rm -rf ./src
    cp -r ./.  $out/share/budcustomer
    makeWrapper '${nodejs}/bin/npm' "$out/bin/budcustomer" \
      --run "cd $out/share/budcustomer" \
      --add-flags "start"
  '';

  meta = {
    description = "Bud customer nextjs frontend";
    homepage = "https://bud.studio";
    license = lib.licenses.gpl3;
    mainProgram = "budcustomer";
    maintainers = with lib.maintainers; [ sinanmohd ];
  };
}

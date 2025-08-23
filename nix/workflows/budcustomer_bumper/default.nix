{
  writeShellApplication,
  prefetch-npm-deps,
  git,
  nix,
}:
writeShellApplication {
  name = "bumper";

  runtimeInputs = [
    prefetch-npm-deps
    git
    nix
  ];

  text = builtins.readFile ./bumper.sh;
}

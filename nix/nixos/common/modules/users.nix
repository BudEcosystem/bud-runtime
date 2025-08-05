{ ... }:
{
  users.users = {
    "ditto" = {
      isNormalUser = true;
      extraGroups = [ "wheel" ];
      openssh.authorizedKeys.keys = [
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDMvXPoqVJwEN1KulT6kJMD8SUgfx1M9zCSpXQS3DlRFsaFXjLXDXtRzxhJ01hu3XGBkkxBiX+J4wkGfpsPWQnMBPGqIuo2Wr4PTdwYKchnTlAMWxlasCiA9vCCdkWCiUawwmkizJjvSVYbdtSidY7bKBiRX5EmUYhZ1n31WocQh9OWSiqp07kTQB1/pMyLEKrbukmJdqf9yKg7D9ckgbtGyaAJtV9iyjGBSgtW9zIFkzaGj1nDxcWVi9FsM+bbs+3aNRhbszHm5UR6oB3xzyZdg/kMUuRqQkSqeYwdqmSUOMpD+Qi5xVz0E196cUCMSeycEAtxO7P2W55T0pOVJqSiVhUEsbMfPpNHeqBD4VB51OVR8QJWTltkqHNoaoCvFcRuidg80t9935Zm8SA3zlCRmafq0jb8Pn347jf9YgC3MyQcv2OHvazIXGPwdodzuyZUkkrHgRIbprcjSoWVBPB9EdNmDKRtnOfV2xypJ+pHSqViXC5dG0xnEW3U6TnhFG0= dittops@MacBook-Pro-2.local"
      ];
    };
    "athul" = {
      isNormalUser = true;
      extraGroups = [ "wheel" ];
      openssh.authorizedKeys.keys = [
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzvzpqulvlwby+7PQUKD6JOPJvyjAi70M+TlsenDIxn athul@accubits.com"
      ];
    };
    "karthik" = {
      isNormalUser = true;
      extraGroups = [ "wheel" ];
      openssh.authorizedKeys.keys = [
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDuWOGURjVpOcHpQolKCWGYuVYn+03K7mXy+KYzUCsG+Hlgsq0i8FN/OD/rx1A4TY1PbYi9epYjamFDPjMdBrwXPn0sRlWcHse8/49hdjXhhsQbZX8IkYK4YEKVrDyPqeek36RCwU1X9MWcEYFbKxZzU2Ho4Lz3pWb0mb8G5q/R0R1D5Q2Dqzxwkw9/9bGn0V/j76PHenZmxmEKAzNDYLl0rDdqcxYB/xNuzgAi6tt05fs32RcPMIHnDROwOmhl7P2AOPjaVr8SfkNbIc+/YknUkpFXTGmbO9LPhtSGH0z1v+8x9ABDWVXnJ6AM5T5URafxpI48GFh4UMLtdLMMEFZZ karthik@accubits.com"
      ];
    };
  };
}

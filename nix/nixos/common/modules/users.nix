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
  };
}

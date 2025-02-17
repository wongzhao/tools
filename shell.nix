{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  nativeBuildInputs = with pkgs; [
    python312
  ] ++ (with python312Packages; [
    textual
    textual-dev

    google-api-python-client
    google-auth-httplib2
    google-auth-oauthlib
  ]);
}

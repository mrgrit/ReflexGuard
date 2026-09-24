#!/usr/bin/env bash
set -euo pipefail
umask 077
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
destination=${1:-"$root/certs"}
if [[ $# -gt 1 || -e "$destination" || -L "$destination" ]]; then
  printf 'Use one new certificate directory; existing files are never overwritten.\n' >&2
  exit 1
fi
mkdir -p -- "$destination"
destination=$(cd -- "$destination" && pwd)
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -sha256 -days 30 -subj '/CN=ReflexGuard Local Development CA' \
  -addext 'basicConstraints=critical,CA:TRUE,pathlen:0' \
  -addext 'keyUsage=critical,keyCertSign,cRLSign' \
  -keyout "$destination/ca.key" -out "$destination/ca.crt"
for purpose in server client; do
  openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
    -sha256 -subj "/CN=reflexguard-$purpose" \
    -keyout "$destination/$purpose.key" -out "$destination/$purpose.csr"
  {
    printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
    printf 'extendedKeyUsage=%sAuth\n' "$purpose"
    if [[ "$purpose" == server ]]; then
      printf 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1\n'
    fi
  } > "$destination/$purpose.ext"
  serial=$(openssl rand -hex 16)
  openssl x509 -req -sha256 -days 7 -in "$destination/$purpose.csr" \
    -CA "$destination/ca.crt" -CAkey "$destination/ca.key" -set_serial "0x$serial" \
    -extfile "$destination/$purpose.ext" -out "$destination/$purpose.crt"
done
openssl verify -CAfile "$destination/ca.crt" -purpose sslserver "$destination/server.crt"
openssl verify -CAfile "$destination/ca.crt" -purpose sslclient "$destination/client.crt"
printf 'Local development certificates created in %s (private files: 0600).\n' "$destination"

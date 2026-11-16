#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
mkdir -p "$root/certs"
config=$(mktemp)
trap 'rm -f "$config"' EXIT
cat > "$config" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = v3_req
prompt = no
[dn]
CN = localhost
[v3_req]
subjectAltName = DNS:localhost, IP:127.0.0.1
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF
openssl req -x509 -newkey rsa:2048 \
  -keyout "$root/certs/key.pem" \
  -out "$root/certs/cert.pem" \
  -days 30 -nodes \
  -config "$config"
echo "SPKI SHA-256:"
openssl x509 -pubkey -noout -in "$root/certs/cert.pem" \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl base64 -A
echo
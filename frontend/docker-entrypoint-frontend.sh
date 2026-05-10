#!/bin/sh
set -e

echo "Backend URL: $BACKEND_URL"

echo "--- /etc/resolv.conf ---"
cat /etc/resolv.conf || echo "(not found)"
echo "---"

# Extract the first nameserver from /etc/resolv.conf.
# nginx requires IPv6 resolver addresses wrapped in brackets, e.g. [fd12::10].
RAW_NS=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
if [ -z "$RAW_NS" ]; then
  RAW_NS="1.1.1.1"
fi

# Wrap in brackets if it looks like an IPv6 address (contains a colon)
if echo "$RAW_NS" | grep -q ':'; then
  NAMESERVER="[$RAW_NS]"
else
  NAMESERVER="$RAW_NS"
fi

echo "Using DNS resolver: $NAMESERVER"
export NAMESERVER

envsubst '${BACKEND_URL} ${NAMESERVER}' \
  < /etc/nginx-spa.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "--- Generated /etc/nginx/conf.d/default.conf ---"
cat /etc/nginx/conf.d/default.conf
echo "---"

nginx -t
exec nginx -g 'daemon off;'

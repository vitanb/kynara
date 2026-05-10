#!/bin/sh
set -e

echo "Backend URL: $BACKEND_URL"

echo "--- /etc/resolv.conf ---"
cat /etc/resolv.conf || echo "(not found)"
echo "---"

# Extract the first nameserver from /etc/resolv.conf so nginx can re-resolve
# backend.railway.internal on each request (picks up backend redeploys and
# avoids stale IPv6 addresses). Falls back to 1.1.1.1 if unavailable.
NAMESERVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
if [ -z "$NAMESERVER" ]; then
  NAMESERVER="1.1.1.1"
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

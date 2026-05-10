#!/bin/sh
set -e

echo "Backend URL: $BACKEND_URL"

echo "--- /etc/resolv.conf ---"
cat /etc/resolv.conf || echo "(not found)"
echo "---"

envsubst '${BACKEND_URL}' \
  < /etc/nginx-spa.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "--- Generated /etc/nginx/conf.d/default.conf ---"
cat /etc/nginx/conf.d/default.conf
echo "---"

nginx -t
exec nginx -g 'daemon off;'

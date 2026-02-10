#!/bin/sh
# Wrap the original entrypoint with proxychains to tunnel MTProto through proxy
exec proxychains4 -q /docker-entrypoint.sh "$@"

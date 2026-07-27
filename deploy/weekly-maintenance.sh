#!/bin/sh
set -eu

# Solo elimina artefactos Docker recreables; nunca toca volúmenes ni datos.
docker builder prune -af
docker image prune -f

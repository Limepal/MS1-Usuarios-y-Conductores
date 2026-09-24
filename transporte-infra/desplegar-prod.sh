#!/usr/bin/env bash
# Despliegue completo en mv-prod-a / mv-prod-b (correr como ec2-user en su home).
# Clona o actualiza los repos públicos, construye las imágenes y levanta todo
# con docker-compose.prod.yml. Idempotente: se puede correr las veces que sea.
#
# Primera vez:  cp .env.example .env  (y completar las contraseñas)
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Falta .env (cp .env.example .env y completarlo)"; exit 1; }
command -v git >/dev/null || sudo dnf install -y git

REPOS=(
  "https://github.com/Limepal/MS1-Usuarios-y-Conductores.git"
  "https://github.com/S1nk0-0/transporte-ms2-viajes.git"
  "https://github.com/enriquetorres-cell/transporte-ms3-calificaciones.git"
  "https://github.com/enriquetorres-cell/transporte-ms4.git"
  "https://github.com/enriquetorres-cell/transporte-ms5-analitica.git"
)

for url in "${REPOS[@]}"; do
  dir=$(basename "$url" .git)
  if [ -d "$dir/.git" ]; then git -C "$dir" pull -q; else git clone -q "$url"; fi
  echo "$dir: $(git -C "$dir" log --oneline -1)"
done

# Contenedores creados antes a mano (docker run) chocan por nombre con compose.
for c in ms4 ms5; do
  if docker inspect "$c" >/dev/null 2>&1 && \
     [ -z "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c")" ]; then
    docker rm -f "$c" >/dev/null
  fi
done

docker compose -f docker-compose.prod.yml up -d --build
sleep 10
for n in 1 2 3 4 5; do echo "ms$n: $(curl -s localhost:800$n/ms$n/health)"; done

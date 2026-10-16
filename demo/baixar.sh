#!/usr/bin/env bash
# Baixa o bruto da demo: "Pequenas Empresas podem se tornar Grandes Marcas", Multiviascom,
# YouTube, licença Creative Commons Attribution (reuse allowed). O vídeo não fica no repositório.
# Precisa de yt-dlp (brew install yt-dlp | pip install yt-dlp).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bruto
if [ -s bruto/multiviascom-grandes-marcas.mp4 ]; then
  echo "já está em bruto/multiviascom-grandes-marcas.mp4"
  exit 0
fi
yt-dlp -f "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080]" --merge-output-format mp4 \
  -o "bruto/multiviascom-grandes-marcas.mp4" "https://www.youtube.com/watch?v=9jhsU2tmtyc"
echo "pronto. Crédito: Multiviascom (https://www.youtube.com/@Multiviascom), CC BY."

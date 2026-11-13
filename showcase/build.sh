#!/usr/bin/env bash
# Vault → 集計 → 動画（MP4）までを通しで実行する。Vault は読むだけ。
#   ./build.sh                      # Vault を自動検出
#   ./build.sh /path/to/Vault       # 場所を指定
#   CONTENT=sample/content.sample.json ./build.sh   # 既存の content.json で映像だけ作る
# build_content.py への追加オプションは CONTENT_OPTS で渡す（例: CONTENT_OPTS="--show-folders"）
set -euo pipefail
cd "$(dirname "$0")"
OUT=out
NAME=${NAME:-vault-showcase}
mkdir -p "$OUT"

if [ -z "${CONTENT:-}" ]; then
  python3 vault_stats.py ${1:+"$1"} -o "$OUT/stats.json"
  python3 build_content.py "$OUT/stats.json" -o "$OUT/content.json" ${CONTENT_OPTS:-}
  CONTENT="$OUT/content.json"
  if [ "${CONFIRM:-}" != "yes" ]; then
    echo
    echo "↑ 動画に出る内容です。$CONTENT を確認・編集してから、次で続きを実行してください:"
    echo "  CONTENT=$CONTENT ./build.sh"
    exit 0
  fi
fi

python3 music.py "$OUT/music.wav"
rm -rf "$OUT/frames"
node render.js --content "$CONTENT" --out "$OUT/frames" --workers "${WORKERS:-6}"
ffmpeg -y -loglevel error -framerate 30 -i "$OUT/frames/f%05d.png" -i "$OUT/music.wav" \
  -c:v libx264 -preset slow -crf 17 -maxrate 4200k -bufsize 8400k -pix_fmt yuv420p \
  -c:a aac -b:a 192k -shortest -movflags +faststart "$NAME.mp4"
ffmpeg -y -loglevel error -i "$NAME.mp4" -vf "select='not(mod(n\,75))',scale=480:-1,tile=4x4" -frames:v 1 "$OUT/contact.png"
ls -la "$NAME.mp4"
ffmpeg -hide_banner -i "$NAME.mp4" -af volumedetect -vn -f null - 2>&1 | grep -E "Duration|Stream|mean_volume|max_volume"

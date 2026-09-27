#!/bin/bash
# gappei: 実データ版の元データ取得（すべて公開GET・PII/送信なし）
# 実行後: python3 src/build_real.py && python3 src/build_x.py
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$HERE/data/raw"
mkdir -p "$RAW"

echo "[1/3] 国土数値情報 N03（行政区域, 2023年）全国 約427MB"
curl -L -o "$RAW/N03_all.zip" \
  "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2023/N03-20230101_GML.zip"
python3 - "$RAW/N03_all.zip" "$RAW" <<'PYEOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
for n in ["N03-23_230101.shp", "N03-23_230101.dbf", "N03-23_230101.shx", "N03-23_230101.prj"]:
    z.extract(n, sys.argv[2])
PYEOF
rm -f "$RAW/N03_all.zip"

echo "[2/3] IPSS 令和5年推計（市区町村別将来推計人口）"
curl -L -o "$RAW/ipss_suikei_kekka.xlsx" \
  "https://www.ipss.go.jp/pp-shicyoson/j/shicyoson23/3kekka/suikei_kekka.xlsx"

echo "[3/3] 総務省 市町村税課税状況等の調（市区町村別・第11表）"
curl -L -o "$RAW/J51-25-b.xlsx" \
  "https://www.soumu.go.jp/main_sosiki/jichi_zeisei/czaisei/czaisei_seido/xls/J51-25-b.xlsx"

echo "取得完了 -> $RAW"

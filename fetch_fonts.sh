#!/bin/sh
# Fetch Noto Sans KR (SIL OFL 1.1) subset OTFs used to build the pack.
set -e
mkdir -p fonts
BASE=https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/KR
curl -L -o fonts/NotoSansKR-Regular.otf "$BASE/NotoSansKR-Regular.otf"
curl -L -o fonts/NotoSansKR-Bold.otf "$BASE/NotoSansKR-Bold.otf"
echo "done"

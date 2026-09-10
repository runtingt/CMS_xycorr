#!/usr/bin/env bash
set -euo pipefail

VERSION="$1"

BASE="./results/corrections/${VERSION}"
TARGET="/eos/cms/store/group/phys_higgs/cmshgg/ingredients"

declare -A SCHEMAS=(
    ["schemaV2_2022_Summer22.json"]="2022/metXY/met_xyCorrections_2022_2022.json.gz"
    ["schemaV2_2022_Summer22EE.json"]="2022/metXY/met_xyCorrections_2022_2022EE.json.gz"
    ["schemaV2_2023_Summer23.json"]="2023/metXY/met_xyCorrections_2023_2023.json.gz"
    ["schemaV2_2023_Summer23BPix.json"]="2023/metXY/met_xyCorrections_2023_2023BPix.json.gz"
    ["schemaV2_2024_Summer24.json"]="2024/metXY/met_xyCorrections_2024_2024.json.gz"
)

for src_name in "${!SCHEMAS[@]}"; do
    src="${BASE}/${src_name}"
    dst="${TARGET}/${SCHEMAS[$src_name]}"

    if [[ ! -f "$src" ]]; then
        echo "Missing: $src" >&2
        continue
    fi

    mkdir -p "$(dirname "$dst")"

    echo "$src"
    echo "  -> $dst"

    gzip -c "$src" > "$dst"
    chmod 777 "$dst"
done

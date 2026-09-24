#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
cyclonedx-py environment .venv/bin/python --pyproject pyproject.toml --mc-type application   --sv 1.6 --of JSON --output-reproducible --validate -o docs/sbom.json
.venv/bin/python scripts/sbom_provenance.py

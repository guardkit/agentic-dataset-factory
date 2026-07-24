#!/bin/sh
# sha256-pinned first-start fetch — the no-manual-step way to populate the model volume.
#
# Pattern (documented; NOT yet wired into docker-compose.yml because no off-box host holds the GGUF
# — see packaging/gguf-manifest.json "backup_gap"). Once the GGUF is published to a URL your host
# can reach, add an init service to the compose that runs this script against the shared volume:
#
#   services:
#     model-init:
#       image: alpine@sha256:<pin alpine>          # busybox has wget + sha256sum, no apk needed
#       environment:
#         MODEL_URL: "https://your-host/recruiter-qwen3-4b-Q4_K_M.gguf"
#       volumes:
#         - recruiter-model:/models
#         - ./fetch-model.sh:/fetch-model.sh:ro
#       entrypoint: ["/bin/sh", "/fetch-model.sh"]
#     seat:
#       depends_on:
#         model-init:
#           condition: service_completed_successfully
#       ...
#
# On first start it downloads + verifies; on every later start the file already exists and it is a
# fast no-op. A checksum mismatch is a HARD failure — the seat never starts on a bad/partial model.
set -eu

DEST="/models/recruiter-qwen3-4b-Q4_K_M.gguf"
# The one load-bearing constant — the GGUF's sha256 (packaging/gguf-manifest.json). Byte-for-byte.
SHA256="c13c3f2e3bce98d2115990786cd3c11dc73abad3b3b23ed37fe92e95879e234d"
URL="${MODEL_URL:?set MODEL_URL to the GGUF download URL}"

verify() { echo "${SHA256}  ${DEST}" | sha256sum -c - >/dev/null 2>&1; }

if [ -f "$DEST" ] && verify; then
  echo "[fetch-model] model present and sha256 OK — nothing to do."
  exit 0
fi

echo "[fetch-model] downloading model from \$MODEL_URL ..."
tmp="${DEST}.partial"
rm -f "$tmp"
wget -q -O "$tmp" "$URL"

echo "[fetch-model] verifying sha256 ..."
if ! echo "${SHA256}  ${tmp}" | sha256sum -c - >/dev/null 2>&1; then
  echo "[fetch-model] FATAL: sha256 mismatch — refusing to install. Got:"
  sha256sum "$tmp" || true
  echo "[fetch-model] expected: ${SHA256}"
  rm -f "$tmp"
  exit 1
fi

mv "$tmp" "$DEST"
echo "[fetch-model] model installed + verified at ${DEST}."

#!/usr/bin/env bash
set -euo pipefail

# Build a statically linked Qdrant binary using MUSL
TARGET="x86_64-unknown-linux-musl"

if ! command -v cargo >/dev/null; then
    echo "Cargo is required" >&2
    exit 1
fi

rustup target add "$TARGET"

git clone --depth 1 https://github.com/qdrant/qdrant.git qdrant-src
pushd qdrant-src >/dev/null
cargo build --release --target "$TARGET"
popd >/dev/null

mkdir -p ../devstral_cli/bin
cp qdrant-src/target/$TARGET/release/qdrant ../devstral_cli/bin/qdrant-linux-x86_64

echo "Qdrant built at devstral_cli/bin/qdrant-linux-x86_64"

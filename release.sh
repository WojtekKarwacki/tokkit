#!/usr/bin/env bash
set -euo pipefail

# Usage: ./release.sh <version>
#        ./release.sh -b major|minor|patch
# Example: ./release.sh 0.2.0
#          ./release.sh -b patch    # 0.1.8 -> 0.1.9
#          ./release.sh -b minor    # 0.1.8 -> 0.2.0
#          ./release.sh -b major    # 0.1.8 -> 1.0.0

bump_version() {
    local current="$1" part="$2"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$current"
    case "$part" in
        major) echo "$((major + 1)).0.0" ;;
        minor) echo "$major.$((minor + 1)).0" ;;
        patch) echo "$major.$minor.$((patch + 1))" ;;
    esac
}

VERSION=""
BUMP=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -b)
            if [[ $# -lt 2 ]] || ! [[ "$2" =~ ^(major|minor|patch)$ ]]; then
                echo "Error: -b requires major, minor, or patch"
                exit 1
            fi
            BUMP="$2"; shift 2 ;;
        *)
            VERSION="$1"; shift ;;
    esac
done

if [[ -n "$BUMP" && -n "$VERSION" ]]; then
    echo "Error: use either -b or an explicit version, not both"
    exit 1
fi

if [[ -n "$BUMP" ]]; then
    CURRENT=$(grep -m1 '^version = "' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    VERSION=$(bump_version "$CURRENT" "$BUMP")
    echo "Bumping $BUMP: $CURRENT -> $VERSION"
elif [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "       $0 -b major|minor|patch"
    exit 1
fi

# Validate semver format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version must be semver (e.g., 0.2.0)"
    exit 1
fi

echo "=== Releasing tokkit-ai $VERSION ==="

# 1. Update version in all files
echo "Bumping version to $VERSION..."

sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i "s/^version = \".*\"/version = \"$VERSION\"/" Cargo.toml
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" py/tokkit_server/__init__.py
sed -i "s/\"version\": \".*\"/\"version\": \"$VERSION\"/" py/tokkit_server/protocol.py

# 2. Verify changes
echo "Version references after bump:"
grep -n "version.*$VERSION" pyproject.toml Cargo.toml py/tokkit_server/__init__.py py/tokkit_server/protocol.py

# 3. Run tests
echo ""
echo "Running Rust tests..."
cargo test --workspace --quiet

echo "Running Python tests..."
maturin develop --quiet 2>/dev/null
python -m pytest tests/ -q --ignore=tests/e2e/benchmark

# 4. Commit and tag
echo ""
echo "Committing and tagging..."
git add pyproject.toml Cargo.toml Cargo.lock py/tokkit_server/__init__.py py/tokkit_server/protocol.py
git commit -m "release: v$VERSION"
git tag "v$VERSION"

# 5. Publish to PyPI (build inside manylinux container for broad compatibility)
echo ""
echo "Publishing to PyPI..."
docker run --rm -v "$(pwd)":/io \
    -e MATURIN_USERNAME -e MATURIN_PASSWORD \
    ghcr.io/pyo3/maturin publish -i python3.11 python3.12 python3.13 --skip-existing

echo ""
echo "=== Released tokkit-ai $VERSION ==="
echo "Run 'git push && git push --tags' to push to GitHub."

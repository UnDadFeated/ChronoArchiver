#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${ROOT_DIR}/flatpak/io.github.UnDadFeated.ChronoArchiver.yml"
BUILD_DIR="${ROOT_DIR}/.flatpak-builder/build"
REPO_DIR="${ROOT_DIR}/.flatpak-builder/repo"
APP_ID="io.github.UnDadFeated.ChronoArchiver"
BRANCH="stable"

flatpak-builder \
  --force-clean \
  --user \
  --install-deps-from=flathub \
  --repo="${REPO_DIR}" \
  "${BUILD_DIR}" \
  "${MANIFEST}"

flatpak build-update-repo "${REPO_DIR}"

flatpak build-bundle "${REPO_DIR}" "${ROOT_DIR}/${APP_ID}.flatpak" "${APP_ID}" "${BRANCH}"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
archive=content/digital-twin/GJU_DigitalTwin_LMS_Media.tar.gz
printf '%s  %s\n' '4f52a339bd1ec777cf886ab3e91750d9f41279acedcc054dca044517fca9a231' "$archive" | sha256sum -c -
mkdir -p media/digital-twin
tar -xzf "$archive" -C media/digital-twin --no-same-owner
chmod 755 media/digital-twin
chmod 644 media/digital-twin/*.mp4 media/digital-twin/*.html
printf 'DIGITAL_TWIN_MEDIA_READY\n'

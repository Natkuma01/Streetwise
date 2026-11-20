#!/usr/bin/env bash
# Put new backend code live. Run on the server as the normal login user:
#   bash /opt/streetwise/app/deploy/update.sh            # deploys release/v1.0
#   bash /opt/streetwise/app/deploy/update.sh some-branch
set -euo pipefail

APP=/opt/streetwise/app
VENV=/opt/streetwise/venv
BRANCH="${1:-release/v1.0}"
RUN="sudo -u streetwise"

$RUN git -C "$APP" fetch origin
$RUN git -C "$APP" checkout "$BRANCH"
$RUN git -C "$APP" pull --ff-only origin "$BRANCH"
$RUN "$VENV/bin/pip" install --quiet -r "$APP/requirements.txt"
$RUN "$VENV/bin/python" "$APP/manage.py" migrate --noinput
$RUN "$VENV/bin/python" "$APP/manage.py" collectstatic --noinput
sudo systemctl restart streetwise
echo "Deployed $BRANCH."

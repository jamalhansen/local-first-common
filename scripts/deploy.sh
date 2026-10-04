#!/usr/bin/env bash
#
# deploy.sh <repo> -- make a fleet repo's committed code the code that runs.
#
# A commit is not live until the installed uv tool is rebuilt: `uv tool install`
# is a snapshot, not a link. Twice on 2026-10-03/04 a fix sat committed but
# undeployed (the dashboard's publish step, the gateway's logging fix). And a
# KeepAlive service keeps running the old process until it's restarted.
#
#   1. reinstall the uv tool, if the repo is installed as one
#   2. restart com.localfirst.<repo>, if that LaunchAgent is a KeepAlive service
#   3. smoke-test: import every [project.scripts] entry point's module with the
#      installed tool's own Python (not `--help`: a service's entry point starts
#      the server), and check a restarted service is running again
#
# Usage: make deploy REPO=<repo>      (or scripts/deploy.sh <repo>)

set -euo pipefail

REPO="${1:?usage: deploy.sh <repo>}"
WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIR="${WORKSPACE}/${REPO%/}"
TOOLS="${HOME}/.local/share/uv/tools"
PLIST="${HOME}/Library/LaunchAgents/com.localfirst.${REPO%/}.plist"
fail=0

[ -f "$DIR/pyproject.toml" ] || { echo "No pyproject.toml in $DIR" >&2; exit 1; }

if [ -n "$(git -C "$DIR" status --porcelain)" ]; then
    echo "warning: $REPO has uncommitted changes; deploying the working tree, not a commit." >&2
fi

tool_name=$(python3 -c "import tomllib,sys;print(tomllib.load(open(sys.argv[1],'rb'))['project']['name'])" "$DIR/pyproject.toml")

# 1. reinstall
if [ -f "$TOOLS/$tool_name/uv-receipt.toml" ]; then
    uv tool install --reinstall -q "$DIR"
    echo "reinstalled uv tool: $tool_name"
else
    echo "not installed as a uv tool: nothing to reinstall ($tool_name)"
fi

# 2. restart a KeepAlive service
if [ -f "$PLIST" ] && [ "$(plutil -extract KeepAlive raw -o - "$PLIST" 2>/dev/null)" = "true" ]; then
    launchctl kickstart -k "gui/$(id -u)/com.localfirst.${REPO%/}"
    sleep 3
    pid=$(launchctl list | awk -v l="com.localfirst.${REPO%/}" '$3==l {print $1}')
    if [ -n "$pid" ] && [ "$pid" != "-" ]; then
        echo "restarted service com.localfirst.${REPO%/} (pid $pid)"
    else
        echo "FAILED: com.localfirst.${REPO%/} is not running after restart" >&2
        fail=1
    fi
fi

# 3. smoke-test entry points
if [ -x "$TOOLS/$tool_name/bin/python" ]; then
    modules=$(python3 -c "
import tomllib,sys
s=tomllib.load(open(sys.argv[1],'rb')).get('project',{}).get('scripts',{})
print(' '.join(sorted({v.split(':')[0] for v in s.values()})))" "$DIR/pyproject.toml")
    for m in $modules; do
        if "$TOOLS/$tool_name/bin/python" -c "import $m" 2>/dev/null; then
            echo "smoke ok: import $m"
        else
            echo "FAILED smoke: import $m" >&2
            fail=1
        fi
    done
fi

exit $fail

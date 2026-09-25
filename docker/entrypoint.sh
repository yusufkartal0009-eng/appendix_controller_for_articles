#!/usr/bin/env bash
# ==============================================================================
# Repro Radar: Sandbox Entrypoint Wrapper
# Handles execution timeouts, output redirection, and exit code capture.
# ==============================================================================

set -eo pipefail

TIMEOUT_SECONDS="${SANDBOX_TIMEOUT:-600}"
OUTPUT_DIR="/workspace/output"
STDOUT_LOG="${OUTPUT_DIR}/stdout.log"
STDERR_LOG="${OUTPUT_DIR}/stderr.log"
META_JSON="${OUTPUT_DIR}/execution_meta.json"

mkdir -p "${OUTPUT_DIR}"

cd /workspace/repo || true

# 1. Offline Package Installation Bootstrap
# If pre-downloaded wheels exist in /workspace/packages, install into user space.
# A failed install does not abort the run, but it is recorded in execution_meta.json.
DEPENDENCY_STATUS="SKIPPED"
if [ -d "/workspace/packages" ] && [ -n "$(ls -A /workspace/packages 2>/dev/null)" ]; then
  echo "=================================================="
  echo "Repro Radar: Installing Offline Bundled Packages"
  echo "=================================================="
  mkdir -p /workspace/home/.local
  if [ -f "/workspace/repo/requirements.txt" ]; then
    PIP_TARGETS=(-r /workspace/repo/requirements.txt)
  else
    PIP_TARGETS=(/workspace/packages/*)
  fi
  if pip install --no-index --find-links=/workspace/packages --no-cache-dir --user "${PIP_TARGETS[@]}"; then
    DEPENDENCY_STATUS="INSTALLED"
  else
    DEPENDENCY_STATUS="FAILED"
    echo "Repro Radar: WARNING offline dependency installation failed; continuing" >&2
  fi
fi

echo "=================================================="
echo "Repro Radar: Isolated Sandbox Runtime Initiated"
echo "Working Dir   : $(pwd)"
echo "Timeout Limit : ${TIMEOUT_SECONDS}s"
echo "Security Mode : Unprivileged (UID: $(id -u))"
echo "Network State : Isolated (--network none)"
echo "Command       : $@"
echo "=================================================="

START_TIME=$(date +%s.%N)

# Execute command under timeout guard with split output capture
set +e
timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" "$@" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" >&2)
EXIT_CODE=$?
set -e

# Flush buffers
sync 2>/dev/null || true
sleep 0.1

END_TIME=$(date +%s.%N)

# Calculate duration using Python for precision and zero external tool dependency
DURATION=$(python3 -c "print(round(${END_TIME} - ${START_TIME}, 3))" 2>/dev/null || echo "0.0")

# Classify exit status
STATUS="COMPLETED"
if [ ${EXIT_CODE} -eq 137 ] || [ ${EXIT_CODE} -eq 124 ]; then
  STATUS="TIMEOUT"
elif [ ${EXIT_CODE} -ne 0 ]; then
  STATUS="FAILED"
fi

# Write structured execution metadata
cat <<EOF > "${META_JSON}"
{
  "status": "${STATUS}",
  "exit_code": ${EXIT_CODE},
  "duration_seconds": ${DURATION},
  "timeout_limit_seconds": ${TIMEOUT_SECONDS},
  "dependency_install_status": "${DEPENDENCY_STATUS}",
  "user_id": $(id -u),
  "group_id": $(id -g)
}
EOF

echo "=================================================="
echo "Repro Radar: Execution Concluded"
echo "Status        : ${STATUS} (Exit Code: ${EXIT_CODE})"
echo "Dependencies  : ${DEPENDENCY_STATUS}"
echo "Duration      : ${DURATION}s"
echo "=================================================="

exit ${EXIT_CODE}

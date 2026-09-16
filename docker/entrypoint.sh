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

echo "=================================================="
echo "Repro Radar: Isolated Sandbox Runtime Initiated"
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

END_TIME=$(date +%s.%N)
DURATION=$(echo "${END_TIME} - ${START_TIME}" | bc -l 2>/dev/null || echo "0.0")

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
  "user_id": $(id -u),
  "group_id": $(id -g)
}
EOF

echo "=================================================="
echo "Repro Radar: Execution Concluded"
echo "Status        : ${STATUS} (Exit Code: ${EXIT_CODE})"
echo "Duration      : ${DURATION}s"
echo "=================================================="

exit ${EXIT_CODE}

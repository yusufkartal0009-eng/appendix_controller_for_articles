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

# Peak memory of this container's cgroup in bytes (v2: memory.peak; v1: memory.max_usage_in_bytes), or null
# when the kernel does not expose it. Recorded for the pilot's resource measurements (docs/PILOT_WEEK2.md section 6).
peak_memory_bytes() {
  local value=""
  if [ -r /sys/fs/cgroup/memory.peak ]; then
    value=$(cat /sys/fs/cgroup/memory.peak)
  elif [ -r /sys/fs/cgroup/memory/memory.max_usage_in_bytes ]; then
    value=$(cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes)
  fi
  case "${value}" in
    ''|*[!0-9]*) echo "null" ;;
    *) echo "${value}" ;;
  esac
}

# 1. Install phase (SANDBOX_PHASE=install): a separate container, run before the paper code.
# Installs pre-downloaded wheels from /workspace/packages into /workspace/deps (the only writable
# mount besides the output directory), binary-only so that no package code runs during install.
# The run phase mounts /workspace/deps read-only: compiled extensions can load there, but the
# paper code can neither modify them nor add executables (/workspace/home and /tmp stay noexec).
if [ "${SANDBOX_PHASE:-run}" = "install" ]; then
  INSTALL_LOG="${OUTPUT_DIR}/install.log"
  INSTALL_META="${OUTPUT_DIR}/install_meta.json"
  # Same files as the host-side bundling (RepoStager.analyze_dependencies): every *requirements*.txt
  # in the repository root; without any, install every bundled wheel.
  PIP_TARGETS=()
  for req in /workspace/repo/*requirements*.txt; do
    if [ -f "${req}" ]; then
      PIP_TARGETS+=(-r "${req}")
    fi
  done
  if [ ${#PIP_TARGETS[@]} -eq 0 ]; then
    PIP_TARGETS=(/workspace/packages/*)
  fi
  echo "=================================================="
  echo "Repro Radar: Install Phase (offline, binary wheels only)"
  echo "Requirements  : ${PIP_TARGETS[*]}"
  echo "=================================================="
  # pip stages --target installs in TMPDIR; /tmp is a 64 MB tmpfs, too small for large wheels.
  export TMPDIR=/workspace/deps/.pip-tmp
  mkdir -p "${TMPDIR}"
  INSTALL_START=$(date +%s.%N)
  set +e
  timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" python -m pip install --no-index \
    --find-links=/workspace/packages --only-binary=:all: --no-cache-dir \
    --target /workspace/deps "${PIP_TARGETS[@]}" > "${INSTALL_LOG}" 2>&1
  INSTALL_CODE=$?
  set -e
  INSTALL_DURATION=$(python3 -c "print(round($(date +%s.%N) - ${INSTALL_START}, 3))" 2>/dev/null || echo "0.0")
  rm -rf "${TMPDIR}"
  cat "${INSTALL_LOG}"
  INSTALL_STATUS="INSTALLED"
  if [ ${INSTALL_CODE} -ne 0 ]; then
    INSTALL_STATUS="FAILED"
  fi
  printf '{"phase": "install", "status": "%s", "exit_code": %d, "duration_seconds": %s, "peak_memory_bytes": %s}\n' \
    "${INSTALL_STATUS}" "${INSTALL_CODE}" "${INSTALL_DURATION}" "$(peak_memory_bytes)" > "${INSTALL_META}"
  echo "Install Status: ${INSTALL_STATUS} (Exit Code: ${INSTALL_CODE})"
  exit ${INSTALL_CODE}
fi

# 2. Run phase: dependencies were installed by the install phase (if any); the runner passes the
# result in SANDBOX_DEPENDENCY_STATUS. A failed install does not abort the run, it is recorded.
DEPENDENCY_STATUS="${SANDBOX_DEPENDENCY_STATUS:-SKIPPED}"

echo "=================================================="
echo "Repro Radar: Isolated Sandbox Runtime Initiated"
echo "Working Dir   : $(pwd)"
echo "Timeout Limit : ${TIMEOUT_SECONDS}s"
echo "Security Mode : Unprivileged (UID: $(id -u))"
echo "Network State : Isolated (--network none)"
echo "Command       : $@"
echo "=================================================="

# Kernel OOM kills recorded for this container's cgroup (v2: memory.events; v1: memory.oom_control).
# Both the timeout watchdog and the OOM killer end the process with SIGKILL (exit 137), so the
# counter is what tells an out-of-memory kill apart from a timeout.
oom_kill_count() {
  local count=""
  if [ -r /sys/fs/cgroup/memory.events ]; then
    count=$(sed -n 's/^oom_kill //p' /sys/fs/cgroup/memory.events)
  elif [ -r /sys/fs/cgroup/memory/memory.oom_control ]; then
    count=$(sed -n 's/^oom_kill //p' /sys/fs/cgroup/memory/memory.oom_control)
  fi
  echo "${count:-0}"
}
OOM_KILLS_BEFORE=$(oom_kill_count)

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
OOM_KILLS_AFTER=$(oom_kill_count)
STATUS="COMPLETED"
if [ ${EXIT_CODE} -ne 0 ] && [ "${OOM_KILLS_AFTER}" -gt "${OOM_KILLS_BEFORE}" ]; then
  STATUS="OOM_KILLED"
elif [ ${EXIT_CODE} -eq 137 ] || [ ${EXIT_CODE} -eq 124 ]; then
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
  "peak_memory_bytes": $(peak_memory_bytes),
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

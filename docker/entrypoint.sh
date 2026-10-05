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

# Working directory of the paper's run setup (#166), set by the runner; the repository root by default.
cd "${SANDBOX_WORKDIR:-/workspace/repo}" || true

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

# 0. Build phase (SANDBOX_PHASE=build, #193): a separate container of the build image (C/C++ compiler), run on
# the host's request before bundling. Turns sdists from /workspace/packages, and /workspace/repo when asked (a
# writable per-run copy), into wheels in /workspace/output/built_wheels. Build code runs here under the same
# isolation as paper code (network off, uid 1000, read-only root); the install phase below stays binary-only.
if [ "${SANDBOX_PHASE:-run}" = "build" ]; then
  BUILD_LOG="${OUTPUT_DIR}/build.log"
  BUILD_META="${OUTPUT_DIR}/build_meta.json"
  BUILT_DIR="${OUTPUT_DIR}/built_wheels"
  BUILD_DEPS="${OUTPUT_DIR}/.build-deps"
  mkdir -p "${BUILT_DIR}" "${BUILD_DEPS}" "${OUTPUT_DIR}/.build-tmp"
  # Compilers write temporary files to TMPDIR; /tmp is a small noexec tmpfs.
  export TMPDIR="${OUTPUT_DIR}/.build-tmp"
  echo "=================================================="
  echo "Repro Radar: Build Phase (offline, isolated)"
  echo "Targets            : ${SANDBOX_BUILD_TARGETS:-<none>}"
  echo "Build requirements : ${SANDBOX_BUILD_REQUIREMENTS:-<none>}"
  echo "=================================================="
  BUILD_START=$(date +%s.%N)
  set +e
  BUILD_CODE=0
  : > "${BUILD_LOG}"
  if [ -n "${SANDBOX_BUILD_REQUIREMENTS:-}" ]; then
    # Build requirements are binary wheels only (no package code runs to install them).
    # shellcheck disable=SC2086
    timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" python -m pip install --no-index \
      --find-links=/workspace/packages --only-binary=:all: --no-cache-dir --target "${BUILD_DEPS}" \
      ${SANDBOX_BUILD_REQUIREMENTS} >> "${BUILD_LOG}" 2>&1
    BUILD_CODE=$?
  fi
  if [ ${BUILD_CODE} -eq 0 ]; then
    # shellcheck disable=SC2086
    PYTHONPATH="${BUILD_DEPS}:${PYTHONPATH:-}" timeout --signal=SIGKILL "${TIMEOUT_SECONDS}" python -m pip wheel \
      --no-index --find-links=/workspace/packages --no-build-isolation --no-deps --no-cache-dir \
      -w "${BUILT_DIR}" ${SANDBOX_BUILD_TARGETS} >> "${BUILD_LOG}" 2>&1
    BUILD_CODE=$?
  fi
  set -e
  BUILD_DURATION=$(python3 -c "print(round($(date +%s.%N) - ${BUILD_START}, 3))" 2>/dev/null || echo "0.0")
  rm -rf "${OUTPUT_DIR}/.build-tmp" "${BUILD_DEPS}"
  cat "${BUILD_LOG}"
  BUILD_STATUS="BUILT"
  if [ ${BUILD_CODE} -ne 0 ]; then
    BUILD_STATUS="FAILED"
  fi
  WHEEL_COUNT=$(find "${BUILT_DIR}" -name '*.whl' | wc -l)
  printf '{"phase": "build", "status": "%s", "exit_code": %d, "duration_seconds": %s, "wheel_count": %d}\n' \
    "${BUILD_STATUS}" "${BUILD_CODE}" "${BUILD_DURATION}" "${WHEEL_COUNT}" > "${BUILD_META}"
  echo "Build Status: ${BUILD_STATUS} (Exit Code: ${BUILD_CODE}, wheels: ${WHEEL_COUNT})"
  exit ${BUILD_CODE}
fi

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
  elif [ -n "${SANDBOX_EXTRA_REQUIREMENTS:-}" ]; then
    # Requirements of the paper's run setup that its requirement files do not name (#193); without requirement
    # files every bundled wheel is installed, extras included.
    # shellcheck disable=SC2206
    PIP_TARGETS+=(${SANDBOX_EXTRA_REQUIREMENTS})
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
  # Record what was actually installed, to compare with what the repository asks for (#161).
  python -m pip list --path /workspace/deps --format=json > "${OUTPUT_DIR}/installed_packages.json" 2>/dev/null \
    || echo "[]" > "${OUTPUT_DIR}/installed_packages.json"
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

# GPU (#169): with `docker run --gpus`, the NVIDIA runtime adds nvidia-smi to the container. Record the GPUs the run
# could see, and sample the GPU memory in use once per second during the run, so the report can say whether a GPU
# was used (peak memory above the value before the run). Without a GPU nothing is sampled.
GPU_DIR="${OUTPUT_DIR}/.gpu"
GPU_SAMPLER_PID=""
GPU_DEVICES_JSON="[]"
if [ -n "${SANDBOX_GPUS_REQUESTED:-}" ] && command -v nvidia-smi >/dev/null 2>&1; then
  mkdir -p "${GPU_DIR}"
  nvidia-smi --query-gpu=index,name,driver_version,memory.total,memory.used --format=csv,noheader,nounits \
    > "${GPU_DIR}/devices.csv" 2>/dev/null || true
  GPU_DEVICES_JSON=$(python3 -c "
import csv, json, sys
rows = [r for r in csv.reader(open(sys.argv[1])) if len(r) == 5]
print(json.dumps([{'index': int(r[0]), 'name': r[1].strip(), 'driver': r[2].strip(),
                   'memory_total_mib': int(r[3]), 'memory_used_before_mib': int(r[4])} for r in rows]))
" "${GPU_DIR}/devices.csv" 2>/dev/null || echo "[]")
  ( while true; do
      nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits >> "${GPU_DIR}/samples.txt" 2>/dev/null
      sleep 1
    done ) &
  GPU_SAMPLER_PID=$!
fi

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

if [ -n "${GPU_SAMPLER_PID}" ]; then
  kill "${GPU_SAMPLER_PID}" 2>/dev/null || true
fi
GPU_PEAK_MIB="null"
if [ -s "${GPU_DIR}/samples.txt" ]; then
  GPU_PEAK_MIB=$(sort -n "${GPU_DIR}/samples.txt" | tail -1 | tr -dc '0-9')
  GPU_PEAK_MIB="${GPU_PEAK_MIB:-null}"
fi

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
  "gpu_requested": $([ -n "${SANDBOX_GPUS_REQUESTED:-}" ] && echo true || echo false),
  "gpu_devices": ${GPU_DEVICES_JSON},
  "gpu_peak_memory_used_mib": ${GPU_PEAK_MIB},
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

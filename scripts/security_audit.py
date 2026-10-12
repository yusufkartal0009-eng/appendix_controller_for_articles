#!/usr/bin/env python3
"""Security audit of the container execution boundaries, run against the real Docker sandbox (#46).

Every probe runs through `DockerSandboxRunner`, so it gets exactly the `docker run` flags a paper run gets. The
probes try to break out of or exhaust the container; a control "holds" when the attempt fails. Results go to
`data/security_audit/results.json`, and the table between the markers in `docs/SECURITY_AUDIT.md` is rendered from
that file.

    python scripts/security_audit.py            # run every scenario (needs Docker and the sandbox image)
    python scripts/security_audit.py --render   # rewrite the table in docs/SECURITY_AUDIT.md from results.json
    python scripts/security_audit.py --check    # fail if the table in docs/SECURITY_AUDIT.md is out of date

Verdicts: PASS = the control holds; FAIL = the control is missing or broken (a finding); INFO = behavior that is
recorded but is not a control (for example the output directory is writable on purpose).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import SANDBOX_RUNS_DIR
from src.sandbox.runner import DockerSandboxRunner, SandboxConfig, image_for

RESULTS_PATH = project_root / "data" / "security_audit" / "results.json"
DOC_PATH = project_root / "docs" / "SECURITY_AUDIT.md"
MARKER_START = "<!-- audit:table:start -->"
MARKER_END = "<!-- audit:table:end -->"
# The runner polls the output directory every 0.5 s and then kills the container, so a fast writer gets a little past
# the limit. In 9 measured runs (#261) it was 18 to 122 MiB; the audit allows 512 MiB before it reports a failure.
OUTPUT_OVERSHOOT_ALLOWANCE_MIB = 512

# Probes that run inside the container (Python standard library only). Each prints one line "PROBE <json>".
PROBES_MAIN = r'''
import ctypes, errno, json, os, socket, stat, subprocess, threading, time

CAP_NAMES = ["chown", "dac_override", "dac_read_search", "fowner", "fsetid", "kill", "setgid", "setuid", "setpcap",
             "linux_immutable", "net_bind_service", "net_broadcast", "net_admin", "net_raw", "ipc_lock", "ipc_owner",
             "sys_module", "sys_rawio", "sys_chroot", "sys_ptrace", "sys_pacct", "sys_admin", "sys_boot", "sys_nice",
             "sys_resource", "sys_time", "sys_tty_config", "mknod", "lease", "audit_write", "audit_control",
             "setfcap", "mac_override", "mac_admin", "syslog", "wake_alarm", "block_suspend", "audit_read", "perfmon",
             "bpf", "checkpoint_restore"]
libc = ctypes.CDLL(None, use_errno=True)


def emit(pid, area, title, expect, held, detail):
    print("PROBE " + json.dumps({"id": pid, "area": area, "title": title, "expect": expect, "held": held,
                                 "detail": str(detail)[:400]}), flush=True)


def status_field(name):
    for line in open("/proc/self/status"):
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def caps(mask):
    value = int(mask, 16)
    return [CAP_NAMES[i] if i < len(CAP_NAMES) else "cap%d" % i for i in range(64) if value >> i & 1]


def fails(fn):
    """True when fn raised; the detail is the error."""
    try:
        r = fn()
        return False, "succeeded (%s)" % (r,)
    except Exception as exc:
        return True, "%s: %s" % (type(exc).__name__, exc)


# identity and privilege
emit("user", "privilege", "Process runs as a non-root user", "uid and gid are not 0", os.getuid() != 0 and os.getgid() != 0,
     "uid=%d gid=%d" % (os.getuid(), os.getgid()))
emit("cap_eff", "privilege", "No effective capabilities", "CapEff is 0", int(status_field("CapEff"), 16) == 0,
     "CapEff=%s %s" % (status_field("CapEff"), caps(status_field("CapEff"))))
emit("cap_bnd", "privilege", "Capability bounding set is empty (drop all)", "CapBnd is 0",
     int(status_field("CapBnd"), 16) == 0, "CapBnd=%s %s" % (status_field("CapBnd"), caps(status_field("CapBnd"))))
emit("no_new_privs", "privilege", "no-new-privileges is set", "NoNewPrivs is 1", status_field("NoNewPrivs") == "1",
     "NoNewPrivs=" + status_field("NoNewPrivs"))
emit("seccomp", "privilege", "A seccomp filter is active", "Seccomp is 2 (filter)", status_field("Seccomp") == "2",
     "Seccomp=" + status_field("Seccomp"))
held, detail = fails(lambda: os.setuid(0))
emit("setuid0", "privilege", "setuid(0) is refused", "PermissionError", held, detail)
held, detail = fails(lambda: subprocess.run(["su", "-c", "id", "root"], capture_output=True, timeout=5, check=True))
emit("su_root", "privilege", "su to root does not work", "command fails", held, detail)

# network
def tcp():
    s = socket.socket(); s.settimeout(3); s.connect(("1.1.1.1", 443)); return "connected"
held, detail = fails(tcp)
emit("net_tcp", "network", "TCP to the internet (1.1.1.1:443)", "connection fails", held, detail)
held, detail = fails(lambda: socket.getaddrinfo("example.com", 443))
emit("net_dns", "network", "DNS resolution", "resolution fails", held, detail)
def gateway():
    s = socket.socket(); s.settimeout(3); s.connect(("172.17.0.1", 80)); return "connected"
held, detail = fails(gateway)
emit("net_gateway", "network", "TCP to the Docker bridge gateway (172.17.0.1:80)", "connection fails", held, detail)
ifaces = sorted(os.listdir("/sys/class/net"))
emit("net_ifaces", "network", "Only the loopback interface exists", "interfaces == ['lo']", ifaces == ["lo"], ifaces)
held, detail = fails(lambda: socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP))
emit("net_raw", "network", "Raw (ICMP) socket", "PermissionError", held, detail)
emit("docker_sock", "escape", "Docker socket is not mounted", "no /var/run/docker.sock",
     not os.path.exists("/var/run/docker.sock"), os.path.exists("/var/run/docker.sock"))

# filesystem
for pid, path, mode in (("fs_root", "/probe_file", "w"), ("fs_etc", "/etc/passwd", "a"),
                        ("fs_usr", "/usr/local/probe_file", "w"), ("fs_repo", "/workspace/repo/probe_file", "w")):
    held, detail = fails(lambda path=path, mode=mode: open(path, mode).write("x"))
    emit(pid, "filesystem", "Write to " + path, "read-only file system", held, detail)
try:
    open("/workspace/output/probe_file", "w").write("x"); wrote = True; err = "written"
except Exception as exc:
    wrote = False; err = str(exc)
emit("fs_output", "filesystem", "Write to /workspace/output (intended)", "allowed", wrote, err)
for pid, folder in (("exec_tmp", "/tmp"), ("exec_home", "/workspace/home")):
    target = folder + "/true_copy"
    try:
        with open("/bin/true", "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
        os.chmod(target, 0o755)
        held, detail = fails(lambda: subprocess.run([target], check=True, capture_output=True))
    except Exception as exc:
        held, detail = True, "could not create the copy: %s" % exc
    emit(pid, "filesystem", "Execute a binary written to " + folder, "noexec: PermissionError", held, detail)
def fill(path, megabytes):
    written = 0
    with open(path, "wb") as f:
        for _ in range(megabytes):
            f.write(b"x" * 1048576); f.flush(); os.fsync(f.fileno()); written += 1
    return "wrote %d MiB" % written
held, detail = fails(lambda: fill("/tmp/fill", 100))
emit("tmp_size", "resource", "Fill /tmp beyond its 64 MiB tmpfs limit", "ENOSPC", held, detail)
held, detail = fails(lambda: fill("/dev/shm/fill", 100))
emit("shm_size", "resource", "Fill /dev/shm beyond its 64 MiB limit", "ENOSPC", held, detail)
mounts = []
for line in open("/proc/self/mountinfo"):
    parts = line.split()
    mounts.append(parts[4])
expected_targets = {"/", "/workspace/repo", "/workspace/output", "/workspace/home", "/tmp", "/proc", "/dev", "/sys",
                    "/dev/pts", "/dev/mqueue", "/dev/shm", "/sys/fs/cgroup", "/etc/resolv.conf", "/etc/hostname",
                    "/etc/hosts", "/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger",
                    "/proc/acpi", "/proc/interrupts", "/proc/kcore", "/proc/keys", "/proc/latency_stats",
                    "/proc/timer_list", "/proc/scsi", "/sys/firmware", "/dev/console"}
unexpected = sorted(m for m in mounts if m not in expected_targets)
emit("mounts", "escape", "No unexpected mounts (no host directories, no sockets)", "only the mounts the runner sets",
     not unexpected, "unexpected=%s (%d mount points checked)" % (unexpected, len(mounts)))
host_dirs = [p for p in ("/mnt/c", "/mnt/host", "/host", "/run/desktop", "/Users", "/mnt/wsl") if os.path.exists(p)]
emit("host_dirs", "escape", "No host directories visible by their usual names", "none exist", not host_dirs, host_dirs)

# kernel interfaces and escape attempts
def mount_tmpfs():
    r = libc.mount(b"tmpfs", b"/tmp", b"tmpfs", 0, None)
    if r != 0:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return "mounted"
held, detail = fails(mount_tmpfs)
emit("mount", "escape", "mount(2) of a filesystem", "EPERM", held, detail)
def unshare_user():
    r = libc.unshare(0x10000000)  # CLONE_NEWUSER
    if r != 0:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return "new user namespace"
held, detail = fails(unshare_user)
emit("unshare_user", "escape", "Create a user namespace (unshare CLONE_NEWUSER)", "EPERM", held, detail)
held, detail = fails(lambda: os.chroot("/tmp"))
emit("chroot", "escape", "chroot(2)", "PermissionError", held, detail)
held, detail = fails(lambda: os.mknod("/tmp/null_dev", stat.S_IFCHR | 0o666, os.makedev(1, 3)))
emit("mknod", "escape", "Create a device node", "PermissionError", held, detail)
def bpf():
    r = libc.syscall(321, 0, 0, 0)
    if r != 0 and ctypes.get_errno():
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return r
held, detail = fails(bpf)
emit("bpf", "escape", "bpf(2) syscall", "EPERM", held, detail)
for pid, path in (("proc_sys", "/proc/sys/kernel/hostname"), ("proc_sysrq", "/proc/sysrq-trigger"),
                  ("cgroup_write", "/sys/fs/cgroup/cgroup.procs")):
    held, detail = fails(lambda path=path: open(path, "w").write("x"))
    emit(pid, "escape", "Write to " + path, "read-only or refused", held, detail)
for pid, path in (("kcore", "/proc/kcore"), ("dev_mem", "/dev/mem"), ("dev_kmsg", "/dev/kmsg")):
    try:
        data = open(path, "rb").read(16)
        held, detail = data == b"", "read %d bytes (an empty read means Docker masked the file with /dev/null)" % len(data)
    except Exception as exc:
        held, detail = True, "%s: %s" % (type(exc).__name__, exc)
    emit(pid, "escape", "Read " + path, "refused, absent, or masked (empty)", held, detail)
held, detail = fails(lambda: os.chown("/tmp", 0, 0))
emit("chown", "privilege", "chown to root", "PermissionError", held, detail)
# GPG_KEY is set by the official python image: the public key ID that signs CPython releases, not a secret.
env_names = sorted(k for k in os.environ
                   if k != "GPG_KEY" and any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASSWORD")))
emit("env_secrets", "escape", "No secret-looking environment variables in the container (the image's public GPG_KEY "
     "is ignored)", "none", not env_names, env_names)

# process limit: a bounded number of sleeping threads
started = []
def nap():
    time.sleep(5)
for _ in range(300):
    try:
        t = threading.Thread(target=nap, daemon=True); t.start(); started.append(t)
    except RuntimeError:
        break
emit("pids", "resource", "Thread bomb is limited by --pids-limit=100", "fewer than 300 of 300 threads start",
     len(started) < 300, "started %d of 300 threads" % len(started))
'''

PROBE_MEMORY = r'''
import time
print("allocating", flush=True)
chunks = []
for _ in range(2048):
    chunks.append(bytearray(1024 * 1024 * 4))
    for i in range(0, len(chunks[-1]), 4096):
        chunks[-1][i] = 1
print("allocated 8 GiB without being stopped", flush=True)
'''

PROBE_TIMEOUT = r'''
import time
print("sleeping", flush=True)
time.sleep(120)
print("woke up", flush=True)
'''

PROBE_KILL_PARENT = r'''
import os, signal, time
parent = os.getppid()
print("AUDIT parent pid", parent, open("/proc/%d/cmdline" % parent).read().replace(chr(0), " "), flush=True)
try:
    os.kill(parent, signal.SIGKILL)
    print("AUDIT killed the parent", flush=True)
except Exception as exc:
    print("AUDIT could not kill the parent:", exc, flush=True)
time.sleep(120)
'''

PROBE_BIG_OUTPUT = r'''
with open("/workspace/output/big.bin", "wb") as f:
    for _ in range(4096):
        f.write(b"x" * 1048576)
        f.flush()
print("AUDIT wrote 4096 MiB into /workspace/output without being stopped", flush=True)
'''

PROBE_SYMLINK = r'''
import os
for name, target in (("link_abs.txt", "/etc/passwd"), ("link_rel.txt", "../../../../etc/hosts")):
    try:
        os.symlink(target, "/workspace/output/" + name)
        print("AUDIT created", name, "->", target, flush=True)
    except Exception as exc:
        print("AUDIT could not create", name, exc, flush=True)
'''


def run_scenario(name: str, code: str, config: SandboxConfig) -> tuple[Any, dict[str, Any]]:
    out_dir = SANDBOX_RUNS_DIR / name
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    repo = Path(tempfile.mkdtemp(prefix=f"{name}_"))
    (repo / "probe.py").write_text(code, encoding="utf-8")
    try:
        result = DockerSandboxRunner(config).run(paper_id=name, repo_dir=repo, target_script="probe.py")
    finally:
        shutil.rmtree(repo, ignore_errors=True)
    meta_path = out_dir / "execution_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return result, meta


def audit_lines(stdout: str) -> list[str]:
    return [line[len("AUDIT "):] for line in stdout.splitlines() if line.startswith("AUDIT ")]


def verdict(held: bool, expect: str) -> str:
    if expect == "allowed":
        return "INFO"
    return "PASS" if held else "FAIL"


def main_probes(config: SandboxConfig) -> list[dict[str, Any]]:
    result, _ = run_scenario("security_audit_main", PROBES_MAIN, config)
    rows = []
    for line in result.stdout.splitlines():
        if line.startswith("PROBE "):
            probe = json.loads(line[len("PROBE "):])
            rows.append({"id": probe["id"], "area": probe["area"], "title": probe["title"], "expect": probe["expect"],
                         "observed": probe["detail"], "verdict": verdict(probe["held"], probe["expect"])})
    if not rows:
        raise SystemExit(f"the probe container printed no results (status {result.status}): {result.stderr[-500:]}")
    return rows


def scenario_rows() -> list[dict[str, Any]]:
    rows = []
    memory = SandboxConfig(memory_limit="256m", memory_swap="256m", timeout_seconds=60)
    result, meta = run_scenario("security_audit_memory", PROBE_MEMORY, memory)
    rows.append({"id": "memory", "area": "resource", "title": "Allocate 8 GiB under a 256 MiB limit (no swap)",
                 "expect": "killed by the memory limit (OOM_KILLED), quickly",
                 "observed": f"status={result.status} exit_code={result.exit_code} duration={result.duration_seconds:.1f}s "
                             f"peak_memory_bytes={meta.get('peak_memory_bytes')}",
                 "verdict": "PASS" if result.status == "OOM_KILLED" else "FAIL"})

    limit = 5
    timeout = SandboxConfig(timeout_seconds=limit)
    result, meta = run_scenario("security_audit_timeout", PROBE_TIMEOUT, timeout)
    rows.append({"id": "timeout", "area": "resource", "title": f"Sleep 120 s under a {limit} s timeout",
                 "expect": "TIMEOUT shortly after the limit",
                 "observed": f"status={result.status} exit_code={result.exit_code} duration={result.duration_seconds:.1f}s",
                 "verdict": "PASS" if result.status == "TIMEOUT" and result.duration_seconds < limit + 10 else "FAIL"})

    result, meta = run_scenario("security_audit_killparent", PROBE_KILL_PARENT, timeout)
    audit = " | ".join(audit_lines(result.stdout))
    misclassified = result.status == "TIMEOUT" and result.duration_seconds < limit
    rows.append({"id": "kill_parent", "area": "resource",
                 "title": f"Paper code kills its own watchdog (the parent `timeout` process), limit {limit} s",
                 "expect": f"the run ends within {limit + 10} s and is not reported as a timeout before the limit",
                 "observed": f"status={result.status} exit_code={result.exit_code} duration={result.duration_seconds:.1f}s; "
                             f"{audit}",
                 "verdict": "FAIL" if misclassified or result.duration_seconds >= limit + 12 else "PASS"})

    disk = SandboxConfig(timeout_seconds=120)
    result, meta = run_scenario("security_audit_bigoutput", PROBE_BIG_OUTPUT, disk)
    big = SANDBOX_RUNS_DIR / "security_audit_bigoutput" / "big.bin"
    size_mib = big.stat().st_size // 1048576 if big.exists() else 0
    allowed = disk.output_limit_mb + OUTPUT_OVERSHOOT_ALLOWANCE_MIB
    rows.append({"id": "output_disk", "area": "resource",
                 "title": "Write up to 4096 MiB into the output directory (a bind mount of a host folder)",
                 "expect": (f"stopped at the output limit ({disk.output_limit_mb} MiB, status OUTPUT_LIMIT_EXCEEDED); "
                            f"the host disk receives at most {allowed} MiB"),
                 "observed": f"status={result.status} duration={result.duration_seconds:.1f}s; {size_mib} MiB landed on "
                             "the host disk before the container was killed",
                 "verdict": "PASS" if result.status == "OUTPUT_LIMIT_EXCEEDED" and size_mib <= allowed else "FAIL"})

    result, meta = run_scenario("security_audit_symlink", PROBE_SYMLINK, SandboxConfig(timeout_seconds=60))
    out_dir = SANDBOX_RUNS_DIR / "security_audit_symlink"
    links = {}
    for link in sorted(out_dir.glob("link_*")):
        try:
            outcome = f"host read returned {len(link.read_bytes())} bytes"
        except OSError as exc:
            outcome = f"host read failed: {type(exc).__name__} errno {exc.errno}"
        links[link.name] = {"is_symlink": link.is_symlink(), "outcome": outcome}
    rows.append({"id": "output_symlink", "area": "escape",
                 "title": "Create symbolic links inside the output directory",
                 "expect": "recorded (host code must not follow them)",
                 "observed": f"{' | '.join(audit_lines(result.stdout))}; on the host: {links}",
                 "verdict": "INFO"})
    for name in ("security_audit_bigoutput",):
        shutil.rmtree(SANDBOX_RUNS_DIR / name, ignore_errors=True)
    return rows


def render_table(data: dict[str, Any]) -> str:
    lines = [(f"Run on {data['run_at']} against `{data['image']}`, Docker {data['docker']}, by "
              f"`scripts/security_audit.py` (source: `data/security_audit/results.json`)."), "",
             "| # | Area | Attempt | Expected | Observed | Verdict |", "|---|---|---|---|---|---|"]
    for i, row in enumerate(data["rows"], 1):
        cells = [str(row[k]).replace("|", "/").replace("\n", " ") for k in ("title", "expect", "observed")]
        lines.append(f"| {i} | {row['area']} | {cells[0]} | {cells[1]} | {cells[2]} | **{row['verdict']}** |")
    counts = {v: sum(1 for r in data["rows"] if r["verdict"] == v) for v in ("PASS", "FAIL", "INFO")}
    lines += ["", f"**Totals: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['INFO']} INFO.**"]
    return "\n".join(lines)


def splice(doc: str, table: str) -> str:
    a, b = doc.index(MARKER_START) + len(MARKER_START), doc.index(MARKER_END)
    return doc[:a] + "\n" + table + "\n" + doc[b:]


def write_doc(data: dict[str, Any]) -> None:
    if DOC_PATH.exists():
        raw = DOC_PATH.read_bytes().decode("utf-8")
        new = splice(raw.replace("\r\n", "\n"), render_table(data))
        DOC_PATH.write_bytes((new.replace("\n", "\r\n") if "\r\n" in raw else new).encode("utf-8"))


def docker_version() -> str:
    import subprocess
    res = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", check=False)
    return res.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Security audit of the container boundaries (needs Docker).")
    parser.add_argument("--check", action="store_true", help="Only check that the table in the document is current.")
    parser.add_argument("--render", action="store_true", help="Rewrite the table from results.json; runs no probe.")
    args = parser.parse_args(argv)
    if args.check:
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        doc = DOC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
        in_sync = splice(doc, render_table(data)) == doc
        print(json.dumps({"in_sync": in_sync}))
        return 0 if in_sync else 1
    if args.render:
        write_doc(json.loads(RESULTS_PATH.read_text(encoding="utf-8")))
        return 0
    runner = DockerSandboxRunner(SandboxConfig())
    if not runner.is_docker_available():
        print("Docker is not available.", file=sys.stderr)
        return 2
    rows = main_probes(SandboxConfig(timeout_seconds=120)) + scenario_rows()
    data = {"run_at": datetime.now().astimezone().isoformat(timespec="minutes"), "image": image_for(SandboxConfig().python_version),
            "docker": docker_version(), "host_os": os.name, "rows": rows}
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    write_doc(data)
    for row in rows:
        print(f"{row['verdict']:5} {row['id']:16} {row['observed'][:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""医路通本地服务控制器：以独立会话启动 / 停止 / 查看三个服务。

为什么需要它
------------
在终端里用 `cmd &` 启动的进程隶属该终端会话，终端关闭或宿主会话被回收时，
子进程会被一并清理（本项目就踩过这个坑）。这里用「双 fork + setsid」让服务
脱离会话，父进程退出后由 launchd 收养，从而长期驻留。

用法
----
    python backend/scripts/service_ctl.py start    # 启动全部
    python backend/scripts/service_ctl.py stop     # 停止全部
    python backend/scripts/service_ctl.py status   # 查看状态
    python backend/scripts/service_ctl.py start backend   # 只启动后端
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
LOG_DIR = PROJECT_ROOT / "logs"
PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
NODE_BIN = os.getenv(
    "MEDIX_NODE_BIN", "/Users/Admin/.workbuddy/binaries/node/versions/22.22.2-6/bin"
)

SERVICES: dict[str, dict] = {
    "backend": {
        "port": 8012,
        "argv": [str(PYTHON), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8012"],
        "cwd": str(BACKEND_ROOT),
        "log": "backend.log",
    },
    "admin": {
        "port": 8022,
        "argv": [
            str(PYTHON), "-m", "uvicorn", "admin_system.backend.main:app",
            "--host", "127.0.0.1", "--port", "8022",
        ],
        "cwd": str(PROJECT_ROOT),
        "log": "admin.log",
    },
    "frontend": {
        "port": 5178,
        "argv": ["/bin/bash", "-c", "exec npm run dev"],
        "cwd": str(PROJECT_ROOT / "frontend"),
        "log": "frontend.log",
        "env": {"PATH": f"{NODE_BIN}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
    },
}


def port_pid(port: int) -> int | None:
    """返回监听指定端口的进程 pid（无则 None）。"""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        return None
    for line in out.stdout.split():
        if line.strip().isdigit():
            return int(line.strip())
    return None


def _daemonize(argv: list[str], cwd: str, log_path: str, extra_env: dict | None) -> None:
    pid = os.fork()
    if pid > 0:
        os.waitpid(pid, 0)   # 第一层子进程立刻退出，等它收尸避免僵尸
        return
    os.setsid()              # 脱离控制终端
    if os.fork() > 0:
        os._exit(0)          # 第二层退出，孙进程成为独立会话首进程
    os.chdir(cwd)
    os.umask(0o022)
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        os.execvpe(argv[0], argv, env)
    except Exception as exc:  # noqa: BLE001
        os.write(2, f"exec failed: {exc}\n".encode())
        os._exit(127)


def start(names: list[str]) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        svc = SERVICES[name]
        pid = port_pid(svc["port"])
        if pid:
            print(f"  {name:<9} 端口 {svc['port']} 已在运行 (pid {pid})，跳过")
            continue
        _daemonize(svc["argv"], svc["cwd"], str(LOG_DIR / svc["log"]), svc.get("env"))
        print(f"  {name:<9} 已启动 -> 端口 {svc['port']}")
    return 0


def stop(names: list[str]) -> int:
    for name in names:
        svc = SERVICES[name]
        pid = port_pid(svc["port"])
        if not pid:
            print(f"  {name:<9} 端口 {svc['port']} 未在运行")
            continue
        try:
            os.kill(pid, 15)
            for _ in range(20):
                time.sleep(0.25)
                if not port_pid(svc["port"]):
                    break
            else:
                os.kill(pid, 9)
            print(f"  {name:<9} 已停止 (pid {pid})")
        except ProcessLookupError:
            print(f"  {name:<9} 进程已消失")
        except PermissionError:
            print(f"  {name:<9} 无权限停止 pid {pid}")
    return 0


def status(names: list[str]) -> int:
    up = 0
    for name in names:
        svc = SERVICES[name]
        pid = port_pid(svc["port"])
        flag = "UP  " if pid else "DOWN"
        up += 1 if pid else 0
        print(f"  {name:<9} {flag}  端口 {svc['port']:<5} {f'pid {pid}' if pid else ''}")
    return 0 if up == len(names) else 1


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    targets = sys.argv[2:] or list(SERVICES)
    unknown = [t for t in targets if t not in SERVICES]
    if unknown:
        print(f"未知服务: {', '.join(unknown)}；可选: {', '.join(SERVICES)}")
        return 2
    if action == "start":
        return start(targets)
    if action == "stop":
        return stop(targets)
    if action == "restart":
        stop(targets)
        time.sleep(1)
        return start(targets)
    if action == "status":
        return status(targets)
    print("用法: service_ctl.py {start|stop|restart|status} [服务名...]")
    return 2


if __name__ == "__main__":
    sys.exit(main())

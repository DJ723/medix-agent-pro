#!/bin/bash
# 医路通 Agent Pro 停止服务
# 按端口定位真实监听进程，避免 pid 文件过期导致停不掉

PROJECT_ROOT="/Users/Admin/Downloads/项目/医路通Agent_Pro"
PY="${PROJECT_ROOT}/backend/.venv/bin/python"
CTL="${PROJECT_ROOT}/backend/scripts/service_ctl.py"

echo "== 停止服务 =="
"${PY}" "${CTL}" stop

# 清理历史遗留的 pid 文件
rm -f "${PROJECT_ROOT}/logs/"*.pid

echo ""
echo "全部服务已停止"

#!/bin/bash
# 医路通 Agent Pro 一键启动（macOS）
# 服务通过 backend/scripts/service_ctl.py 以独立会话启动：关闭此终端窗口不影响服务
# 启动顺序：用户端后端 8012 -> 管理后台 8022 -> 用户端前端 5178

PROJECT_ROOT="/Users/Admin/Downloads/项目/医路通Agent_Pro"
PY="${PROJECT_ROOT}/backend/.venv/bin/python"
CTL="${PROJECT_ROOT}/backend/scripts/service_ctl.py"
LOG_DIR="${PROJECT_ROOT}/logs"
ENV_FILE="${PROJECT_ROOT}/backend/.env"

mkdir -p "${LOG_DIR}"

echo "== 加载本地密钥 =="
if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
  echo "已加载 ${ENV_FILE}"
else
  echo "⚠️  未找到 ${ENV_FILE}"
  echo "   请复制 backend/.env.example 为 backend/.env 并填入密钥"
  echo "   否则模型调用会失败（可能被静默降级为模拟回答）"
fi

echo "== 密钥配置自检 =="
cd "${PROJECT_ROOT}/backend" || exit 1
"${PY}" - <<'PY'
from app.core.config import SETTINGS
llm = SETTINGS["llm"].get("api_key") or ""
vlm = SETTINGS["vlm"].get("api_key") or ""
print(f"  对话模型 key : {'已配置 (' + llm[:6] + '…' + llm[-4:] + ')' if llm else '缺失'}")
print(f"  视觉模型 key : {'已配置 (' + vlm[:6] + '…' + vlm[-4:] + ')' if vlm else '缺失（报告读图会不可用）'}")
print(f"  令牌签名密钥 : {'已配置' if SETTINGS['auth'].get('token_secret') else '缺失'}")
if not llm:
    print("  ⚠️  对话 key 缺失：服务仍会启动，但会走模拟回答")
PY
cd "${PROJECT_ROOT}" || exit 1

echo "== 启动服务（独立会话）=="
"${PY}" "${CTL}" start

echo "== 等待就绪（向量模型首次加载约 15-25 秒）=="
for i in $(seq 1 25); do
  sleep 1
  printf "."
done
echo ""

"${PY}" "${CTL}" status
READY=$?

echo ""
if [ ${READY} -eq 0 ]; then
  echo "全部就绪。服务已脱离本终端，关闭窗口不影响运行。"
  echo "停止服务请双击「停止服务.command」"
else
  echo "有服务未就绪，请查看 ${LOG_DIR} 下对应日志"
fi

echo ""
echo "用户端：   http://127.0.0.1:5178/"
echo "管理后台： http://127.0.0.1:8022/   （账号密码见 backend/.env）"
echo "接口文档： http://127.0.0.1:8012/docs"

open "http://127.0.0.1:5178/"

#!/bin/bash
# =============================================
# 小A智能问答系统 — 一键部署脚本
# 在云服务器 1.95.49.216 上执行
# =============================================

set -e

echo "===== 小A智能问答系统 部署开始 ====="

# ---------- 1. 系统依赖 ----------
echo "[1/6] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv nginx

# ---------- 2. 目录结构 ----------
echo "[2/6] 创建目录结构..."
sudo mkdir -p /opt/xiaoA-qa/static
sudo mkdir -p /var/log/xiaoA-qa
sudo chown -R $USER:$USER /opt/xiaoA-qa

# ---------- 3. Python 环境 ----------
echo "[3/6] 配置 Python 虚拟环境..."
cd /opt/xiaoA-qa
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ---------- 4. Gunicorn 启动 ----------
echo "[4/6] 启动 Gunicorn..."
bash start.sh restart

# ---------- 5. Nginx 配置 ----------
echo "[5/6] 配置 Nginx..."
sudo cp nginx.conf /etc/nginx/sites-available/xiaoA-qa
sudo ln -sf /etc/nginx/sites-available/xiaoA-qa /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# ---------- 6. 防火墙 ----------
echo "[6/6] 配置防火墙..."
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true

echo "===== 部署完成 ====="
echo "访问地址: http://1.95.49.216"
echo "健康检查: http://1.95.49.216/health"
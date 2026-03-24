#!/bin/bash

# 1. 权限检查
if [ "$EUID" -ne 0 ]; then 
  echo "请使用 root 权限运行此脚本。"
  exit 1
fi

# 定义路径 [1]
INSTALL_DIR="/usr/lib/pve_monitor"
DB_DIR="/var/lib/pve"
DOWNLOAD_URL="https://raw.githubusercontent.com/Lorry-San/PVETrafficManager/refs/heads/main/pve_monitor.py"

echo "==== 1. 准备运行环境 ===="
apt-get update
apt-get install -y python3 python3-pip wget sqlite3
mkdir -p $INSTALL_DIR
mkdir -p $DB_DIR

echo "==== 2. 从 GitHub 下载程序 ===="
wget -O $INSTALL_DIR/pve_monitor.py $DOWNLOAD_URL
if [ $? -ne 0 ]; then
    echo "下载失败，请检查网络连接。"
    exit 1
fi

echo "==== 3. 安装依赖 (系统级别) ===="
# 使用 --break-system-packages 以适配最新的 Debian/PVE 环境
pip3 install python-telegram-bot --break-system-packages

echo "==== 4. 交互式配置核心参数 [1] ===="
echo "请输入您的 Telegram Bot Token:"
read -p "> " user_token
echo "请输入您的管理员 Telegram ID (数字) [1]:"
read -p "> " user_admin_id

# 使用 sed 修改脚本中的配置信息 [1]
sed -i "s/TOKEN = \"\"/TOKEN = \"$user_token\"/" $INSTALL_DIR/pve_monitor.py
sed -i "s/ADMIN_ID =/ADMIN_ID = $user_admin_id/" $INSTALL_DIR/pve_monitor.py

echo "==== 5. 设置开机自动启动 (Systemd) ===="
cat <<EOF > /etc/systemd/system/pve-tg.service
[Unit]
Description=PVE VM Traffic Manager Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/pve_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 重新加载配置并启动服务
systemctl daemon-reload
systemctl enable pve-tg
systemctl start pve-tg

echo "------------------------------------------------"
echo "✅ 安装成功！"
echo "服务已注册为: pve-tg，并已设置为开机自动启动。"
echo "您可以发送 /help 给您的机器人来开始管理您的虚拟机 [1]。"
echo "------------------------------------------------"

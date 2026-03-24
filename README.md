# PVETrafficManager

🚀 **PVETrafficManager** 是一个基于 Python 的 Proxmox VE 流量配额管理方案，通过 Telegram Bot 实现对虚拟机的实时监控、超流自动关停及自助查询。

---

## ✨ 核心特性

- **高效监控**：直接从宿主机 `/proc/net/dev` 获取 `tap[vmid]i` 接口流量，精确统计上传与下载。
- **配额控制**：支持为指定 VM 设置流量上限（GB），一旦超出即自动执行网卡禁用指令。
- **自动逻辑**：支持自定义每月重置日期（1-28日），到期自动清空流量计数。
- **多级交互**：
  - **管理员**：拥有监控添加、所有者变更、手动重置、删除监控等全量权限。
  - **用户**：通过 `/status` 随时查询自己名下虚拟机的流量剩余情况。
- **数据持久化**：使用 SQLite 数据库存储。

---

## 🛠️ 安装要求

- **环境**：Proxmox VE 8 以上
- **依赖**：Python 3.x, `python-telegram-bot` 

---

## 🚀 快速开始

### 1. 本地部署
```bash
mkdir -p /usr/lib/pve_monitor
# 将 pve_monitor.py 放置在此目录下
python3 /usr/lib/pve_monitor/pve_monitor.py
```

---

## 🎮 指令指南 [1]

### 管理员指令 (👑 Admin Only)
- `/add [VMID] [GB] [USER_ID]` - 添加监控，设置流量限额及所属用户 ID。
- `/setowner [VMID] [USER_ID]` - 转移虚拟机所有权。
- `/setday [VMID] [1-28]` - 设置每月流量重置的日期。
- `/reset [VMID]` - 强制重置当前流量计数，并解封网络。
- `/del [VMID]` - 彻底移除该虚拟机的流量监控。

### 普通用户指令 (👤 User)
- `/status` - 查看自己名下所有虚拟机的已用/总计流量。
- `/uid` - 获取自己的 Telegram 数字 ID。
- `/help` - 获取帮助菜单。

---

## ⚠️ 免责声明
本工具仅供学习与管理参考，由于其具备控制虚拟机网络的能力，请在部署前充分测试。请务必保护好您的 **BOT TOKEN** 以防非法访问。

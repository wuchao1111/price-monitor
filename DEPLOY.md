# 部署指南

## 前置条件

- Python 3.8+
- Node.js (用于 opencli smzdm 查询)

## 安装步骤

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 opencli

```bash
npm install -g @jackwener/opencli
# 验证安装
opencli smzdm haojia "测试" --limit 5
```

### 3. 配置文件

```bash
cp configs/config.yaml configs/config.local.yaml
```

编辑 `configs/config.local.yaml`，至少配置企业微信 Webhook：

```yaml
notification:
  wecom:
    enabled: true
    webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

> **安全提醒**: Webhook URL 包含敏感 key，不要提交到 git。

### 4. 初始化数据库

```bash
python -c "from src.storage.database import Database; db = Database('data/price_monitor.db'); db.init_schema('migrations/003_activity_claimed.sql')"
```

`003_activity_claimed.sql` 是最终迁移脚本，包含所有表结构。

## 启动服务

### 启动 Web UI

```bash
python app.py
```

访问 `http://localhost:9000`

### 启动后台监控

```bash
./start_monitor.sh
```

脚本会自动启动 Web UI + 监控进程，并使用 `caffeinate` 防止 Mac 休眠。

### 查看日志

```bash
tail -f log/monitor_20260529_*.log   # 监控日志
tail -f log/webui.log                # Web UI 日志
```

### 停止服务

```bash
./stop_monitor.sh
```

### 手动运行一次价格检查

```bash
python run_monitor_once.py
```

---

## 内网其他设备访问

### 获取本机 IP

```bash
ipconfig getifaddr en0  # WiFi
# 或
ipconfig getifaddr en1  # 有线网络
```

### 其他设备访问

浏览器打开 `http://<你的电脑IP>:9000`

> 如果无法访问，检查 Mac 「系统设置 → 网络 → 防火墙」是否允许 Python 接收连接。

---

## Mac 开机自启动

### 方法一：使用 launchd（推荐）

1. 编辑 `deploy/price-monitor.plist`，修改路径为你的实际路径

2. 复制到 LaunchAgents：
```bash
cp deploy/price-monitor.plist ~/Library/LaunchAgents/com.price.monitor.plist
```

3. 加载服务：
```bash
launchctl load ~/Library/LaunchAgents/com.price.monitor.plist
```

4. 常用命令：
```bash
launchctl list | grep price.monitor     # 查看状态
launchctl start com.price.monitor       # 手动启动
launchctl stop com.price.monitor        # 手动停止
launchctl unload ~/Library/LaunchAgents/com.price.monitor.plist  # 卸载
tail -f ~/Library/Logs/price-monitor.log  # 查看日志
```

### 方法二：使用 tmux

```bash
# 创建会话
tmux new -s price-monitor
python app.py
# Ctrl+B, D 分离

# 重新连接
tmux attach -t price-monitor
```

---

## 数据库备份

```bash
# 手动备份
cp data/price_monitor.db data/price_monitor.db.backup_$(date +%Y%m%d)

# 使用备份脚本
python backup.py

# 恢复
python restore.py
```

## 数据导出

```bash
python export.py
```

导出为 CSV 文件：`price_monitor_export_*.csv`

---

## 日志文件位置

| 文件 | 说明 |
|------|------|
| `log/monitor_*.log` | 监控脚本运行日志 |
| `log/webui.log` | Web UI 日志 (nohup 模式) |
| `log/sent_urls.txt` | 已发送通知的链接记录 (去重) |
| `~/Library/Logs/price-monitor.log` | launchd 模式日志 |

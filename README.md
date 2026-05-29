# 保价追踪系统 (Price Monitor Agent)

一个价格监控和保价管理工具，帮助用户追踪商品价格变动、管理保价记录。用户参加团购后可获得 100 天无理由保价权益，本系统帮助记录和管理这一流程。

## 核心功能

### 1. 商品保价管理 (Web UI)
- **新增/编辑/删除** 保价商品，记录原价、渠道、订单号、店铺活动、团购活动
- **保价流程管理**：提交低价 → 提交客服(processing) → 确认到账(confirmed) / 拒绝(rejected) → 撤销(pending)
- **搜索与筛选**：按关键词搜索、按保价状态筛选、分页查看
- **活动领取标记**：标记店铺活动和团购活动是否已领取
- 访问 `http://localhost:9000` 使用

### 2. 自动价格监控
- 每 10 分钟检查所有商品的价格
- 使用什么值得买 (smzdm) 浏览器自动化查询好价
- 只保留最近 2 天内的价格结果
- 比较基准 = min(商品原价, 待保价, 已保价)
- 发现更低价格时通过**企业微信**发送通知
- 已发送通知的链接记录在 `log/sent_urls.txt`，避免重复通知

### 3. AI Agent (可选)
- 基于 Anthropic Claude / OpenAI 的 LLM Agent
- 支持自然语言交互：添加商品、查询价格、查看历史
- 可通过 CLI 命令行使用

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 opencli (smzdm 查询)

```bash
npm install -g @jackwener/opencli
# 验证
opencli smzdm haojia "测试" --limit 5
```

### 3. 配置

```bash
cp configs/config.yaml configs/config.local.yaml
```

编辑 `configs/config.local.yaml`，填入企业微信 Webhook 地址：
```yaml
notification:
  wecom:
    enabled: true
    webhook_url: "你的企业微信webhook地址"
```

### 4. 初始化数据库

```bash
python -c "from src.storage.database import Database; db = Database('data/price_monitor.db'); db.init_schema('migrations/003_activity_claimed.sql')"
```

### 5. 启动 Web UI

```bash
python app.py
# 访问 http://localhost:9000
```

### 6. 启动后台监控

```bash
./start_monitor.sh
```

### 7. 停止

```bash
./stop_monitor.sh
```

## 项目架构

详细的目录结构和文件说明请参见 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)。

```text
price-monitor-agent/
├── app.py                   # Web UI 入口
├── monitor_all_products.py  # 后台监控
├── src/                     # 核心源码
├── templates/               # HTML 模板
├── configs/                 # 配置文件
├── migrations/              # 数据库迁移
├── data/                    # 数据库
├── log/                     # 日志
└── tests/                   # 测试
```

## 数据库表

| 表名 | 说明 |
|------|------|
| `products` | 商品信息 (名称、关键词、原价、渠道、订单号、保价金额、活动标记) |
| `price_guarantee_records` | 保价记录 (低价渠道、低价金额、状态流转) |
| `price_history` | 价格查询历史 |
| `change_log` | 最低价变更日志 |
| `monitor_config` | 监控定时配置 |

## 保价流程

```
发现低价 → 添加保价记录(pending)
              ↓
         提交客服(processing)
              ↓
      ┌──────┴──────┐
  确认到账        拒绝
 (confirmed)    (rejected)
      ↓
  撤销可回到 pending
```

## 技术栈

- **Web 框架**: FastAPI + Jinja2 模板
- **数据库**: SQLite (WAL 模式)
- **价格查询**: opencli (浏览器自动化) → smzdm 好价
- **定时任务**: APScheduler (AsyncIOScheduler)
- **通知**: 企业微信 Webhook (Markdown 消息)
- **LLM Agent**: Anthropic Claude / OpenAI (可选)
- **部署**: launchd (Mac 开机自启)

## 许可

MIT

# 项目目录结构详解

Price Monitor 是一个价格监控和保价管理工具，支持通过 Web UI 管理商品和保价记录，后台自动监控什么值得买好价，发现低价时推送企业微信通知。

## 目录树

```
price-monitor-agent/
├── app.py                      # Web UI 入口 (FastAPI, 监听 0.0.0.0:9000)
├── monitor_all_products.py     # 后台监控脚本 (APScheduler 每10分钟)
├── run_monitor_once.py         # 手动运行一次价格检查
├── start_monitor.sh            # 启动后台监控 (nohup + caffeinate 防休眠)
├── stop_monitor.sh             # 停止 Web UI + 监控进程
├── requirements.txt            # Python 依赖列表
│
├── src/                        # 核心源码
│   ├── models/
│   │   └── schemas.py          # Pydantic 数据模型定义
│   ├── storage/
│   │   ├── database.py         # SQLite 连接封装 (WAL 模式, Row factory)
│   │   └── crud.py             # 5 个表: Product/PriceGuarantee/PriceHistory/ChangeLog/MonitorConfig
│   ├── skills/
│   │   ├── base.py             # BaseSkill 抽象基类 (query_price 接口)
│   │   ├── smzdm_opencli.py    # smzdm 好价查询 (调用 opencli 浏览器自动化)
│   │   └── manager.py          # SkillManager 技能注册与并发查询
│   ├── modules/
│   │   ├── comparator.py       # 价格比较器 (最新价 vs 当前最低价)
│   │   ├── notification.py     # 通知管理器 (终端/企业微信/钉钉)
│   │   └── scheduler.py        # 定时调度器 (APScheduler cron)
│   ├── agent/
│   │   ├── core.py             # LLM Agent 核心 (Anthropic/OpenAI)
│   │   └── prompts.py          # Agent 系统提示词
│   └── ui/
│       └── cli.py              # CLI 命令行交互界面
│
├── templates/                  # Web UI 模板 (Jinja2)
│   ├── index.html              # 商品列表 + 搜索/筛选/分页
│   ├── product.html            # 商品详情 + 保价记录流转
│   └── product_form.html       # 新增/编辑商品表单
│
├── configs/
│   ├── config.yaml             # 配置模板
│   └── config.local.yaml       # 本地配置 (需自行创建, 含企业微信 webhook)
│
├── migrations/                 # 数据库迁移脚本 (按序号执行)
│   ├── 001_initial.sql         # 初始表: products, price_history, change_log, monitor_config
│   ├── 002_price_guarantee.sql # 新增: price_guarantee_records 表
│   └── 003_activity_claimed.sql# 新增: store_activity_claimed, group_activity_claimed 字段
│
├── data/                       # SQLite 数据库文件
│   └── price_monitor.db
│
├── log/                        # 运行时日志
│   ├── monitor_*.log           # 监控脚本日志
│   ├── sent_urls.txt           # 已发送通知的链接 (去重)
│   └── webui.log               # Web UI 日志 (nohup 模式)
│
├── opencli_adapters/           # opencli adapter 备份/参考
│   └── smzdm/notes.md          # smzdm adapter 实现笔记
│
├── deploy/
│   └── price-monitor.plist     # Mac launchd 开机自启配置
│
├── tests/                      # 测试脚本
│   ├── test_web_integration.py # HTTP 集成测试 (完整保价流程)
│   ├── test_pagination.py      # 分页测试
│   └── ... (其他历史测试文件)
│
├── backup.py                   # 数据库备份脚本
├── restore.py                  # 数据库恢复脚本
├── export.py                   # 数据导出 CSV
│
├── README.md                   # 项目说明
├── PROJECT_STRUCTURE.md        # 本文件 - 结构说明
├── DEPLOY.md                   # 部署指南
├── backgroud.md                # 项目背景
└── CLAUDE.md                   # Claude Code 开发规范
```

## 核心架构

### Web UI (`app.py`)

- FastAPI 框架，Jinja2 模板渲染
- 路由一览：

| 路径 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 商品列表 (支持搜索、状态筛选、分页) |
| `/product/new` | GET/POST | 新增商品 |
| `/product/{id}` | GET | 商品详情 (含保价记录) |
| `/product/{id}/edit` | GET/POST | 编辑商品 |
| `/product/{id}/delete` | POST | 删除商品 |
| `/product/{id}/guarantee` | POST | 添加保价记录 |
| `/product/{id}/activity` | POST | 标记活动已领取 |
| `/guarantee/{id}/submit` | POST | 提交客服处理 |
| `/guarantee/{id}/confirm` | POST | 确认保价到账 |
| `/guarantee/{id}/reject` | POST | 拒绝保价 |
| `/guarantee/{id}/undo` | POST | 撤销保价 (回到待处理) |

### 后台监控 (`monitor_all_products.py`)

- 独立进程，使用 APScheduler `AsyncIOScheduler`
- 启动后**立即运行一次**，之后每 10 分钟检查
- 监控逻辑：
  1. 读取 `configs/config.local.yaml` 获取数据库路径和企微配置
  2. 加载 `log/sent_urls.txt` 已发送链接集合 (内存去重)
  3. 查询数据库所有商品
  4. 逐个商品调用 `SmzdmOpencliSkill.query_price()`
  5. 过滤：只保留最近 2 天内的价格
  6. 比较基准 = min(原价, 待保价, 已保价)
  7. 如果 smzdm 最新价 < 基准价 且 链接未发送过 → 发送企业微信通知
  8. 记录已发送链接到 `sent_urls.txt`
- 使用 `caffeinate -i` 防止 Mac 休眠中断监控

### 技能系统 (`src/skills/`)

- **BaseSkill**: 抽象基类，定义 `query_price(keyword) -> List[PriceResult]`
- **SmzdmOpencliSkill**: 调用 `opencli smzdm haojia` 命令查询什么值得买好价
  - 使用 `asyncio.create_subprocess_exec` 异步执行子进程
  - 输出 JSON 格式，解析为 `PriceResult` 列表
  - 时间过滤：只保留最近 2 天内的价格 (MM-DD HH:MM 格式解析)
  - 按价格升序排序 (最便宜在前)
- **SkillManager**: 技能注册中心，支持并发查询多个技能

### 数据存储 (`src/storage/`)

- **Database**: SQLite 封装
  - WAL 模式 (支持读写并发)
  - `Row` factory (支持按列名访问)
  - `check_same_thread=False` (支持多线程访问)
- **CRUD 类**:
  - `ProductCRUD`: 商品增删改查、搜索、分页、状态筛选
  - `PriceGuaranteeCRUD`: 保价记录、状态流转
  - `PriceHistoryCRUD`: 价格查询历史
  - `ChangeLogCRUD`: 最低价变更日志
  - `MonitorConfigCRUD`: 监控定时配置

### LLM Agent (`src/agent/`)

- 可选模块，基于 Anthropic Claude 或 OpenAI
- 支持自然语言交互：添加商品、查询价格、查看历史、确认更新
- 通过 ToolRegistry 注册 8 个工具函数
- 通过 `src/ui/cli.py` 提供 CLI 交互界面

## 数据库表结构

### products

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| name | TEXT | 商品名称 |
| keywords | TEXT | 搜索关键词 (用于 smzdm 查询) |
| welfare_policy | TEXT | 福利政策说明 |
| current_lowest_price | REAL | 当前最低价 |
| original_price | REAL | 原价 (团购价) |
| original_order_no | TEXT | 原始订单号 |
| original_channel | TEXT | 原始购买渠道 |
| current_guaranteed_price | REAL | 已保最低价 |
| pending_guarantee_price | REAL | 待保价 |
| store_activity | TEXT | 店铺活动 |
| group_activity | TEXT | 团购活动 |
| store_activity_claimed | INTEGER | 店铺活动是否已领取 |
| group_activity_claimed | INTEGER | 团购活动是否已领取 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### price_guarantee_records

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| product_id | INTEGER FK | 关联商品 |
| low_price_channel | TEXT | 低价渠道 |
| low_price_order_no | TEXT | 低价订单号 |
| low_price | REAL | 发现的低价 |
| guarantee_amount | REAL | 保价金额 (原价 - 低价) |
| status | TEXT | pending / processing / confirmed / rejected |
| submitted_at | TEXT | 提交时间 |
| confirmed_at | TEXT | 确认时间 |
| note | TEXT | 备注 |

## 保价状态流转

```
添加保价 → pending (待处理)
             ↓
        提交客服 → processing (处理中)
             ↓
       ┌──────┴──────┐
    确认到账        拒绝
   confirmed      rejected
       ↓
    撤销 → pending (重新处理)
```

## 关键设计点

1. **opencli 浏览器自动化**: 使用成熟的 adapter 方案查询 smzdm，比自建爬虫稳定
2. **时间过滤**: 只使用最近 2 天内的价格，避免旧价格干扰
3. **三重价格基准**: 比较原价、待保价、已保价，取最小值
4. **防重复通知**: 记录已发送链接 `sent_urls.txt`，避免重复推送
5. **独立监控进程**: 监控和 Web UI 解耦，独立运行
6. **caffeinate 防休眠**: Mac 环境下防止系统休眠导致监控中断

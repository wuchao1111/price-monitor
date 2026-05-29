# 什么值得买 (smzdm)

## 概述

smzdm adapter 是 opencli 的一个插件，用于通过浏览器自动化查询什么值得买网站的好价信息。

## 命令

- `opencli smzdm haojia <关键词> --limit N --format json` — 好价搜索
  - 对应 smzdm 分类 `c=faxian`（发现页）
  - 默认使用 `order=time` 按时间排序
  - 浏览器模式，直接从 DOM 提取 `li.feed-row-wide` 元素

- `opencli smzdm search <关键词>` — 综合搜索
  - 对应 `c=home`（首页综合）

## 集成方式

在 `src/skills/smzdm_opencli.py` 中通过 `asyncio.create_subprocess_exec` 异步调用 `opencli smzdm haojia` 命令，解析 JSON 输出并转换为 `PriceResult` 对象。

### 处理逻辑

1. 调用 `opencli smzdm haojia <关键词> --limit 20 --format json`
2. 解析返回的 JSON 数组
3. 解析每条结果的时间 (格式: `MM-DD HH:MM`)，过滤掉超过 2 天的旧数据
4. 过滤无效价格 (price <= 0)
5. 按价格升序排序，最便宜的排在最前面
6. 返回 `List[PriceResult]`

### PriceResult 字段映射

| JSON 字段 | PriceResult 字段 | 说明 |
|-----------|-----------------|------|
| title | product_name | 好价标题 |
| price | price | 价格 |
| mall | source | 来源 (平台)，加 `smzdm:` 前缀 |
| url | url | 商品链接 |
| time | timestamp | 发布时间 (用于时间过滤) |

## 时间过滤说明

- 输入格式: `MM-DD HH:MM`（如 `05-25 14:30`）
- 年份默认当前年，但会做跨年处理
- 只保留最近 2 天内的价格
- 超过 2 天的旧价格会被跳过

## 历史

- 2026-05-25: 创建 `smzdm haojia` 命令
- 好价页面使用 `c=faxian` + `order=time` 按时间排序

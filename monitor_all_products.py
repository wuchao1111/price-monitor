#!/usr/bin/env python3
"""
价格监控主脚本 - 每10分钟检查所有商品的价格
"""
import asyncio
import os
import sys
import logging
from datetime import datetime

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.skills.smzdm_opencli import SmzdmOpencliSkill
from src.storage.database import Database
from src.storage import ProductCRUD, PriceGuaranteeCRUD, PriceHistoryCRUD
from src.models.schemas import PriceHistory


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 已发送通知的链接记录
SENT_URLS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log', 'sent_urls.txt')
sent_urls = set()

def load_sent_urls():
    """加载已发送的链接记录"""
    global sent_urls
    if os.path.exists(SENT_URLS_FILE):
        with open(SENT_URLS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    sent_urls.add(url)
        logger.info(f"Loaded {len(sent_urls)} sent URLs")

def save_sent_url(url):
    """保存已发送的链接"""
    global sent_urls
    if url not in sent_urls:
        sent_urls.add(url)
        with open(SENT_URLS_FILE, 'a', encoding='utf-8') as f:
            f.write(url + '\n')
        logger.debug(f"Saved sent URL: {url}")

def is_url_sent(url):
    """检查链接是否已发送过"""
    return url in sent_urls


async def send_wecom_notification(webhook_url, product_name, result_title, old_price, new_price, source, url):
    """发送企业微信通知"""
    message = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"""## 🎉 发现低价！

**商品**: {product_name}
**好价标题**: {result_title}
**原价**: ¥{old_price:.2f}
**现价**: ¥{new_price:.2f}
**差价**: ¥{old_price - new_price:.2f}
**来源**: {source}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

[查看商品链接]({url})
"""
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as resp:
                result = await resp.text()
                logger.info(f"企业微信通知发送结果: {result}")
                success = resp.status == 200
                return success
    except Exception as e:
        logger.error(f"发送企业微信通知失败: {e}")
        return False


async def check_single_product(product, skill, wecom_webhook_url, product_crud, price_history_crud):
    """检查单个商品的价格"""
    logger.info(f"检查商品: {product.name} (关键词: {product.keywords})")

    try:
        # 用关键词查询价格
        results = await skill.query_price(product.keywords)

        if not results:
            logger.warning(f"没有找到 {product.name} 的结果")
            return

        logger.info(f"找到 {len(results)} 个结果，最低价: ¥{results[0].price:.2f}")

        # 获取比较基准：原价、待保价格、已保价格的最小值
        prices = []
        if product.original_price:
            prices.append(product.original_price)
        if product.current_guaranteed_price:
            prices.append(product.current_guaranteed_price)
        if product.pending_guarantee_price:
            prices.append(product.pending_guarantee_price)

        if not prices:
            logger.warning(f"{product.name} 没有设置原价、待保价格或已保价格，跳过比较")
            return

        compare_price = min(prices)
        logger.info(f"比较基准价格: ¥{compare_price:.2f} (来源: {prices})")

        # 比较价格
        if results[0].price < compare_price:
            logger.info(f"🎉 发现更低价格！基准价: ¥{compare_price:.2f}, 现价: ¥{results[0].price:.2f}")

            # 检查是否已发送过通知
            if is_url_sent(results[0].url):
                logger.info(f"该链接已发送过通知，跳过: {results[0].url}")
            else:
                # 发送企业微信通知
                if wecom_webhook_url:
                    sent = await send_wecom_notification(
                        wecom_webhook_url,
                        product.name,
                        results[0].product_name,
                        compare_price,
                        results[0].price,
                        results[0].source,
                        results[0].url
                    )
                    if sent:
                        save_sent_url(results[0].url)
        else:
            logger.info(f"当前价格 ¥{results[0].price:.2f} 没有比基准价 ¥{compare_price:.2f} 低")

    except Exception as e:
        logger.error(f"检查商品 {product.name} 时出错: {e}", exc_info=True)


async def check_all_products():
    """检查所有商品的价格"""
    logger.info("=" * 60)
    logger.info("开始检查所有商品价格")
    logger.info("=" * 60)

    # 1. 读取配置
    config_path = os.path.join(os.path.dirname(__file__), "configs", "config.local.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 2. 连接数据库
    db_path = config["database"]["path"]
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    db = Database(db_path)
    product_crud = ProductCRUD(db)
    price_history_crud = PriceHistoryCRUD(db)

    # 3. 获取企业微信配置
    wecom_webhook_url = None
    wecom_config = config.get("notification", {}).get("wecom", {})
    if wecom_config.get("enabled") and wecom_config.get("webhook_url"):
        wecom_webhook_url = wecom_config["webhook_url"]
        logger.info("企业微信通知已启用")

    # 4. 获取所有商品
    products = product_crud.list_all()
    logger.info(f"数据库中有 {len(products)} 个商品")

    if not products:
        logger.warning("没有商品需要检查")
        return

    # 5. 初始化 skill
    skill = SmzdmOpencliSkill({"enabled": True})

    # 6. 逐个检查商品
    for product in products:
        await check_single_product(
            product,
            skill,
            wecom_webhook_url,
            product_crud,
            price_history_crud
        )
        await asyncio.sleep(2)  # 稍微间隔，避免请求过快

    logger.info("=" * 60)
    logger.info("所有商品检查完成")
    logger.info("=" * 60)


async def run_monitor():
    """运行监控"""
    print("=" * 60)
    print("价格监控系统启动")
    print("=" * 60)

    # 加载已发送链接记录
    load_sent_urls()

    # 创建 scheduler，每10分钟运行一次
    scheduler = AsyncIOScheduler()

    # 添加任务
    scheduler.add_job(
        check_all_products,
        'interval',
        minutes=10,
        id='check_all_products',
        name='检查所有商品价格',
        replace_existing=True
    )

    # 启动 scheduler
    scheduler.start()
    logger.info("定时任务已启动，每10分钟运行一次")
    print("定时任务已启动，按 Ctrl+C 停止")

    # 立即运行一次
    logger.info("立即运行第一次检查...")
    await check_all_products()

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到停止信号，正在关闭...")
        scheduler.shutdown()
        print("已停止")


def main():
    """主函数"""
    asyncio.run(run_monitor())


if __name__ == "__main__":
    main()

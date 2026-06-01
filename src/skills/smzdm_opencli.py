"""
什么值得买 好价搜索 Skill - 支持 opencli / playwright 双驱动
"""
import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List
from logging import getLogger

from src.skills.base import BaseSkill
from src.models.schemas import PriceResult

logger = getLogger(__name__)

COOKIES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "smzdm_cookies.json",
)


class SmzdmOpencliSkill(BaseSkill):
    """什么值得买好价搜索 Skill - 支持 opencli / playwright 双驱动

    通过 config 中的 driver 字段切换：
      - "opencli" (默认): 调用 opencli smzdm haojia，依赖本地 Chrome + Browser Bridge
      - "playwright": 使用 Playwright 无头浏览器，适合无图形界面的服务器
    """

    def __init__(self, config: Dict):
        self._config = config
        self._enabled = config.get('enabled', True)
        self._driver = config.get('driver', 'opencli')
        self._cookie_expired = False

    @property
    def name(self) -> str:
        return "smzdm"

    @property
    def description(self) -> str:
        return "什么值得买好价搜索"

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def query_price(self, keyword: str) -> List[PriceResult]:
        if self._driver == 'playwright':
            return await self._query_playwright(keyword)
        return await self._query_opencli(keyword)

    async def _query_opencli(self, keyword: str) -> List[PriceResult]:
        """调用 opencli smzdm haojia 来搜索好价"""
        logger.info(f"Searching smzdm haojia for: {keyword}")

        try:
            cmd = [
                "opencli", "smzdm", "haojia",
                keyword, "--limit", "20", "--format", "json"
            ]

            logger.debug(f"Running command: {cmd}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

            if process.returncode != 0:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                logger.error(f"opencli command failed with code {process.returncode}: {stderr_text}")
                return []

            output = stdout.decode('utf-8', errors='ignore')
            logger.debug(f"opencli output: {output[:500]}...")

            data = json.loads(output)

            if not isinstance(data, list):
                logger.warning(f"Unexpected output format: {type(data)}")
                return []

            return self._parse_results(data)

        except asyncio.TimeoutError:
            logger.error("opencli command timed out")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse opencli output: {e}")
            return []
        except Exception as e:
            logger.exception(f"Failed to query smzdm haojia: {e}")
            return []

    def check_cookie_health(self) -> str:
        """检查 playwright 驱动所需的 cookies 是否健康

        Returns:
            "ok" — 正常
            "missing" — cookies 文件不存在
            "expired" — cookies 已过期（所有 session cookie 均已失效）
            "unknown" — 无法判断（非 playwright 模式）
        """
        if self._driver != 'playwright':
            return "unknown"
        if not os.path.exists(COOKIES_PATH):
            return "missing"
        try:
            with open(COOKIES_PATH) as f:
                cookies = json.load(f)
            if not cookies:
                return "expired"
            # 检查是否有未过期的 session cookie
            now = datetime.now().timestamp()
            valid = any(
                c.get('expires', 0) > now
                for c in cookies
                if c.get('expires') and c.get('expires', 0) > 0
            )
            # session cookies (expires=0 或 -1) 无法判断，视为有效
            has_session = any(
                not c.get('expires') or c.get('expires', -1) <= 0
                for c in cookies
            )
            if valid or has_session:
                return "ok"
            return "expired"
        except Exception:
            return "expired"

    async def _query_playwright(self, keyword: str) -> List[PriceResult]:
        """使用 Playwright 无头浏览器搜索什么值得买好价"""
        logger.info(f"Searching smzdm (playwright) for: {keyword}")

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36",
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
            )
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
            """)

            # 加载已保存的 cookies（登录态）
            if os.path.exists(COOKIES_PATH):
                try:
                    with open(COOKIES_PATH) as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    logger.info(f"Loaded {len(cookies)} cookies")
                except Exception as e:
                    logger.warning(f"Failed to load cookies: {e}")

            page = await context.new_page()

            q = keyword.strip()
            url = f"https://search.smzdm.com/?c=faxian&s={q}&order=time&v=b"
            logger.debug(f"Navigating to: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # 检测 cookie 是否过期（页面被重定向到登录页或出现验证码）
            page_url = page.url
            if 'zhiyou.smzdm.com' in page_url or 'passport.smzdm.com' in page_url:
                logger.warning("Cookie expired: redirected to login page")
                self._cookie_expired = True
                await browser.close()
                return []

            # 检测是否出现腾讯验证码
            captcha = await page.query_selector('#t_mask, .t-captcha-popup-mask')
            if captcha:
                logger.warning("Cookie expired: captcha challenge triggered")
                self._cookie_expired = True
                await browser.close()
                return []

            await page.wait_for_selector("li.feed-row-wide", timeout=30000)

            data = await page.evaluate("""(maxItems) => {
                const items = document.querySelectorAll('li.feed-row-wide');
                const results = [];
                items.forEach((li) => {
                    if (results.length >= maxItems) return;
                    const titleEl = li.querySelector('h5.feed-block-title > a')
                                 || li.querySelector('h5 > a');
                    if (!titleEl) return;
                    const title = (titleEl.getAttribute('title') || titleEl.textContent || '').trim();
                    const url = titleEl.getAttribute('href') || titleEl.href || '';
                    const priceEl = li.querySelector('.z-highlight');
                    let price = priceEl ? priceEl.textContent.trim() : '';
                    const priceMatch = price.match(/(\\d+(?:\\.\\d+)?)/);
                    price = priceMatch ? priceMatch[1] : null;
                    let mall = '';
                    const mallEl = li.querySelector('.z-feed-foot-r .feed-block-extras span')
                                || li.querySelector('.z-feed-foot-r span');
                    if (mallEl) mall = mallEl.textContent.trim();
                    if (!mall) {
                        const mallMatch = li.textContent.match(/(京东|天猫|淘宝|拼多多|唯品会|苏宁|国美|亚马逊|当当)/);
                        mall = mallMatch ? mallMatch[1] : '';
                    }
                    let time = '';
                    const timeMatch = li.textContent.match(/(\\d{2})-(\\d{2})\\s+(\\d{2}):(\\d{2})/);
                    time = timeMatch ? timeMatch[0] : '';
                    results.push({ title, price, mall, time, url });
                });
                return results;
            }""", 20)

            await browser.close()

            if not data:
                logger.info(f"No results found for: {keyword}")
                return []

            self._cookie_expired = False
            return self._parse_results(data)

    def _parse_results(self, data: List[Dict]) -> List[PriceResult]:
        """将原始数据解析为 PriceResult，只保留最近两天内的价格"""
        results = []
        now = datetime.now()
        cutoff = now - timedelta(days=2)
        current_year = now.year

        for item in data:
            try:
                price_str = item.get('price')
                if not price_str:
                    continue
                price = float(price_str)
                if price <= 0:
                    continue

                time_str = item.get('time', '')
                item_time = None
                if time_str:
                    try:
                        item_date = datetime.strptime(time_str, '%m-%d %H:%M')
                        item_time = item_date.replace(year=current_year)

                        if now.month == 1 and item_time.month == 12:
                            item_time = item_time.replace(year=current_year - 1)
                        if item_time > now:
                            item_time = item_time.replace(year=current_year - 1)
                    except ValueError:
                        logger.debug(f"Failed to parse time: {time_str}")
                        continue

                if item_time and item_time < cutoff:
                    logger.debug(f"Skipping old price: {time_str} ({price})")
                    continue

                results.append(PriceResult(
                    product_name=item.get('title', ''),
                    price=price,
                    source=f"smzdm:{item.get('mall', '')}" if item.get('mall') else "smzdm",
                    url=item.get('url', '')
                ))
            except Exception as e:
                logger.debug(f"Failed to parse item: {e}")
                continue

        results.sort(key=lambda x: x.price)
        logger.info(f"Found {len(results)} valid results (last 2 days)")
        return results

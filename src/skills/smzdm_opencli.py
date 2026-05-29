"""
什么值得买 好价搜索 Skill - 基于 opencli adapter
直接调用 opencli smzdm haojia 命令
"""
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List
from logging import getLogger

from src.skills.base import BaseSkill
from src.models.schemas import PriceResult

logger = getLogger(__name__)


class SmzdmOpencliSkill(BaseSkill):
    """什么值得买好价搜索 Skill - 基于 opencli"""

    def __init__(self, config: Dict):
        self._config = config
        self._enabled = config.get('enabled', True)

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
        """调用 opencli smzdm haojia 来搜索好价"""
        logger.info(f"Searching smzdm haojia for: {keyword}")

        try:
            # 构建命令
            cmd = [
                "opencli", "smzdm", "haojia",
                keyword, "--limit", "20", "--format", "json"
            ]

            logger.debug(f"Running command: {cmd}")

            # 运行命令
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

            # 解析输出
            output = stdout.decode('utf-8', errors='ignore')
            logger.debug(f"opencli output: {output[:500]}...")

            data = json.loads(output)

            if not isinstance(data, list):
                logger.warning(f"Unexpected output format: {type(data)}")
                return []

            # 转换为 PriceResult，只保留最近两天内的价格
            results = []
            now = datetime.now()
            cutoff = now - timedelta(days=2)
            current_year = now.year

            for item in data:
                try:
                    price = float(item.get('price', 0))
                    if price <= 0:
                        continue

                    # 解析时间，格式是 MM-DD HH:MM
                    time_str = item.get('time', '')
                    item_time = None
                    if time_str:
                        try:
                            # 解析月份日期时间，年份假设为当前年
                            # 如果当前是1月但解析出来是12月，说明是去年
                            item_date = datetime.strptime(time_str, '%m-%d %H:%M')
                            item_time = item_date.replace(year=current_year)

                            # 如果当前是1月但月份是12月，说明是去年
                            if now.month == 1 and item_time.month == 12:
                                item_time = item_time.replace(year=current_year - 1)

                            # 如果解析出来的时间比当前还晚，说明是去年
                            if item_time > now:
                                item_time = item_time.replace(year=current_year - 1)

                        except ValueError:
                            logger.debug(f"Failed to parse time: {time_str}")
                            continue

                    # 检查时间是否在最近两天内
                    if item_time and item_time < cutoff:
                        logger.debug(f"Skipping old price: {time_str} ({price})")
                        continue

                    result = PriceResult(
                        product_name=item.get('title', ''),
                        price=price,
                        source=f"smzdm:{item.get('mall', '')}" if item.get('mall') else "smzdm",
                        url=item.get('url', '')
                    )
                    results.append(result)
                except Exception as e:
                    logger.debug(f"Failed to parse item: {e}")
                    continue

            # 按价格排序
            results.sort(key=lambda x: x.price)

            logger.info(f"Found {len(results)} valid results (last 2 days) for {keyword}")
            return results

        except asyncio.TimeoutError:
            logger.error("opencli command timed out")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse opencli output: {e}")
            return []
        except Exception as e:
            logger.exception(f"Failed to query smzdm haojia: {e}")
            return []

"""
Relevance Filter - uses LLM to judge whether search results match the searched keyword
"""
import json
import asyncio
from logging import getLogger
from typing import Dict, List

from src.models.price import PriceResult, FilteredResult

logger = getLogger(__name__)

RELEVANCE_PROMPT_TEMPLATE = """You are a product relevance judge. Determine whether each search result matches the searched product.

Search keyword: "{keyword}"

Rules:
- A result is RELEVANT only if it is the EXACT SAME product model as the keyword
- Different models (e.g., "T80" vs "T90Pro", "iPhone 15" vs "iPhone 16") are IRRELEVANT even if from the same brand
- Different generations or variants (e.g., "Pro" vs non-"Pro") are IRRELEVANT
- Same model with different capacities/sizes/colors ARE RELEVANT (e.g., "科沃斯T90Pro 标准版" and "科沃斯T90Pro 旗舰版")
- If uncertain, mark as RELEVANT (be lenient)

Search results:
{formatted_results}

Return a JSON array where each element has:
- "index": the 0-based index of the result
- "relevant": true or false
- "reason": brief explanation in Chinese (1 sentence)

Return ONLY the JSON array, no other text.
"""


class RelevanceFilter:
    """Filters price search results by relevance to the keyword using LLM"""

    def __init__(self, llm_config: dict, enabled: bool = True):
        """
        Args:
            llm_config: The 'llm' section from the application config dict
            enabled: Set to False to skip filtering (pass through all results)
        """
        self._enabled = enabled
        self._cache: Dict[tuple, bool] = {}  # (keyword, url) -> is_relevant
        if enabled:
            from src.agent.llm import create_llm_client
            config_for_client = {"llm": llm_config}
            self._client = create_llm_client(config_for_client)
            logger.info(
                f"RelevanceFilter initialized: provider={llm_config.get('provider')}, "
                f"model={self._client.model}"
            )
        else:
            self._client = None
            logger.info("RelevanceFilter disabled (pass-through mode)")

    async def filter(
        self, keyword: str, results: List[PriceResult]
    ) -> FilteredResult:
        """
        Filter results by relevance to keyword.

        Uses an in-memory cache keyed by (keyword, url) to avoid repeated LLM calls
        for the same search result across monitoring cycles.

        Args:
            keyword: The search keyword (e.g., "科沃斯T90Pro")
            results: Raw price results from skills

        Returns:
            FilteredResult with kept and filtered lists
        """
        if not results:
            return FilteredResult(
                keyword=keyword, kept=[], filtered=[], filtered_details=[]
            )

        if not self._enabled:
            return FilteredResult(
                keyword=keyword, kept=results, filtered=[], filtered_details=[]
            )

        # Check cache: if all results are already judged, skip LLM call entirely
        cached_judgments = []
        all_cached = True
        for r in results:
            key = (keyword, r.url)
            if key in self._cache:
                cached_judgments.append({
                    "relevant": self._cache[key],
                    "reason": "cached",
                })
            else:
                cached_judgments.append(None)
                all_cached = False

        if all_cached:
            logger.debug(
                f"Cache hit for '{keyword}': all {len(results)} results cached, skipping LLM"
            )
            return self._build_filtered_result(keyword, results, cached_judgments)

        # Call LLM for uncached results
        lines = []
        for i, r in enumerate(results):
            title = r.product_name.replace('"', "'")
            lines.append(f'{i}. Title: "{title}" -- price: ¥{r.price}')
        formatted = "\n".join(lines)

        prompt = RELEVANCE_PROMPT_TEMPLATE.format(
            keyword=keyword, formatted_results=formatted
        )

        try:
            judgments = await self._call_llm(prompt, len(results))
        except Exception as e:
            logger.error(
                f"Relevance filter LLM call failed for '{keyword}': {e}. "
                f"Passing through all {len(results)} results."
            )
            return FilteredResult(
                keyword=keyword, kept=results, filtered=[], filtered_details=[]
            )

        # Write all results to cache
        for i, r in enumerate(results):
            entry = judgments[i] if i < len(judgments) else {}
            is_relevant = entry.get("relevant", True) if isinstance(entry, dict) else True
            self._cache[(keyword, r.url)] = is_relevant

        return self._build_filtered_result(keyword, results, judgments)

    def _build_filtered_result(
        self, keyword: str, results: List[PriceResult], judgments: List
    ) -> FilteredResult:
        """Build FilteredResult from results and their judgments."""
        kept: List[PriceResult] = []
        filtered: List[PriceResult] = []
        filtered_details: List[dict] = []

        for i, result in enumerate(results):
            entry = judgments[i] if i < len(judgments) else {}
            is_relevant = entry.get("relevant", True) if isinstance(entry, dict) else True
            reason = entry.get("reason", "") if isinstance(entry, dict) else ""

            if is_relevant:
                kept.append(result)
            else:
                filtered.append(result)
                filtered_details.append({
                    "title": result.product_name,
                    "reason": reason or "judged irrelevant",
                })

        logger.info(
            f"Relevance filter for '{keyword}': kept={len(kept)}/{len(results)}, "
            f"filtered={len(filtered)}"
        )
        for detail in filtered_details:
            logger.info(f"  Filtered: {detail['title']} - {detail['reason']}")

        return FilteredResult(
            keyword=keyword,
            kept=kept,
            filtered=filtered,
            filtered_details=filtered_details,
        )

    async def _call_llm(self, prompt: str, expected_count: int) -> List[dict]:
        """Call LLM and parse relevance judgments. Returns list of dicts with 'relevant' and 'reason'."""
        messages = [{"role": "user", "content": prompt}]

        # send_request is synchronous, run in thread to avoid blocking
        response = await asyncio.to_thread(
            self._client.send_request, messages, "", []
        )
        text = self._client.extract_text(response)

        return self._parse_response(text, expected_count)

    @staticmethod
    def _parse_response(text: str, expected_count: int) -> List[dict]:
        """
        Parse LLM response into a list of dicts with 'relevant' and 'reason'.
        Gracefully handles malformed JSON by falling back to pass-through.
        Each returned dict: {"relevant": bool, "reason": str}
        """
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
            elif "```" in text:
                text = text.rsplit("```", 1)[0]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                f"Failed to parse relevance filter response as JSON. "
                f"Response preview: {text[:200]}"
            )
            return [{"relevant": True, "reason": "parse error, default pass"} for _ in range(expected_count)]

        if not isinstance(data, list):
            logger.warning(
                f"Unexpected response type: {type(data)}. Falling back to pass-through."
            )
            return [{"relevant": True, "reason": "unexpected type, default pass"} for _ in range(expected_count)]

        # Build result list, defaulting to relevant for any unmentioned index
        result = [{"relevant": True, "reason": ""} for _ in range(expected_count)]
        for entry in data:
            idx = entry.get("index")
            if isinstance(idx, int) and 0 <= idx < expected_count:
                result[idx] = {
                    "relevant": entry.get("relevant", True),
                    "reason": entry.get("reason", ""),
                }

        return result

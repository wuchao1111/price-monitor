"""
Price Monitor Agent - main orchestrator
"""
import asyncio
import os
from typing import Any, Dict, List, Optional
from logging import getLogger

import yaml

from src.skills.manager import SkillManager
from src.modules.comparator import PriceComparator
from src.modules.notification import NotificationManager
from src.storage import ProductCRUD, PriceHistoryCRUD, ChangeLogCRUD
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.registry import ToolRegistry
from src.agent.tools import AgentToolsMixin
from src.agent.llm import create_llm_client

logger = getLogger(__name__)


class PriceMonitorAgent(AgentToolsMixin):
    """Main AI Agent for price monitoring"""

    def __init__(
        self,
        config_path: str,
        product_crud: ProductCRUD,
        price_history_crud: PriceHistoryCRUD,
        change_log_crud: ChangeLogCRUD,
        skill_manager: SkillManager,
        comparator: PriceComparator,
        notification_manager: NotificationManager,
    ):
        self.config = self._load_config(config_path)
        self.product_crud = product_crud
        self.price_history_crud = price_history_crud
        self.change_log_crud = change_log_crud
        self.skill_manager = skill_manager
        self.comparator = comparator
        self.notification_manager = notification_manager

        # Tool registry
        self.tool_registry = ToolRegistry()
        self._register_tools()

        # Initialize LLM client
        self.llm_client = create_llm_client(self.config)
        logger.info(
            f"Initialized LLM client: {self.config['llm']['provider']}, "
            f"model: {self.llm_client.model}"
        )

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from yaml"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Expand environment variables
        def expand_env(s):
            if isinstance(s, str) and s.startswith('${') and s.endswith('}'):
                env_var = s[2:-1]
                return os.environ.get(env_var, '')
            return s

        # Simple recursive expansion
        def expand_dict(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    expand_dict(v)
                elif isinstance(v, str):
                    d[k] = expand_env(v)
            return d

        return expand_dict(config)

    async def execute_tool_calls(self, tool_calls: List[Dict]) -> List[Dict[str, Any]]:
        """Execute a list of tool calls"""
        results = []
        for call in tool_calls:
            name = call.get('name')
            parameters = call.get('parameters', {})

            tool = self.tool_registry.get_tool(name)
            if tool is None:
                results.append({
                    "name": name,
                    "error": f"Tool '{name}' not found"
                })
                continue

            try:
                if asyncio.iscoroutinefunction(tool):
                    result = await tool(**parameters)
                else:
                    result = tool(**parameters)
                results.append({
                    "name": name,
                    "result": result
                })
            except Exception as e:
                logger.exception(f"Error executing tool {name}")
                results.append({
                    "name": name,
                    "error": str(e)
                })
        return results

    async def chat(self, user_input: str, max_turns: int = 5) -> str:
        """Main chat entry point with multi-turn tool calling"""
        messages = self.llm_client.create_initial_messages(user_input)
        tools = self.tool_registry.list_tools()

        for turn in range(max_turns):
            response = self.llm_client.send_request(messages, SYSTEM_PROMPT, tools)
            tool_calls = self.llm_client.parse_tool_calls(response)

            if not tool_calls:
                return self.llm_client.extract_text(response)

            # Execute tool calls
            results = await self.execute_tool_calls(tool_calls)

            # Format results and continue the loop
            messages = self.llm_client.format_tool_results(
                messages, tool_calls, results, original_response=response
            )

        # Max turns reached, get final text response
        final_response = self.llm_client.send_request(messages, SYSTEM_PROMPT, tools)
        return self.llm_client.extract_text(final_response)

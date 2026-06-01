"""
LLM Client Abstraction - Anthropic + OpenAI implementations
"""
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

from anthropic import Anthropic
from openai import OpenAI

from src.agent.prompts import SYSTEM_PROMPT


def json_default(obj):
    """Custom JSON encoder for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


class BaseLLMClient(ABC):
    """Abstract base for LLM clients"""

    def __init__(self, config: dict):
        self.model = config['llm'].get('model', self._default_model())

    @abstractmethod
    def _default_model(self) -> str:
        """Default model name for this provider"""
        ...

    @abstractmethod
    def create_initial_messages(self, user_input: str) -> List[Dict]:
        """Create initial message list from user input"""
        ...

    @abstractmethod
    def send_request(
        self, messages: List[Dict], system_prompt: str, tools: List[Dict]
    ) -> Any:
        """Send a request to the LLM and return the response"""
        ...

    @abstractmethod
    def parse_tool_calls(self, response: Any) -> List[Dict]:
        """Extract tool calls from the LLM response"""
        ...

    @abstractmethod
    def extract_text(self, response: Any) -> str:
        """Extract text content from the LLM response"""
        ...

    @abstractmethod
    def format_tool_results(
        self, messages: List[Dict], tool_calls: List[Dict], results: List[Dict],
        original_response: Any = None,
    ) -> List[Dict]:
        """Append tool call requests and results to the message list"""
        ...


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client"""

    def _default_model(self) -> str:
        return 'claude-sonnet-4-6'

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = config['llm']['api_key'] or os.environ.get('ANTHROPIC_API_KEY', '')
        self.client = Anthropic(api_key=api_key)

    def create_initial_messages(self, user_input: str) -> List[Dict]:
        return [{"role": "user", "content": user_input}]

    def send_request(
        self, messages: List[Dict], system_prompt: str, tools: List[Dict]
    ) -> Any:
        return self.client.beta.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            tools=tools,
            max_tokens=1024,
            temperature=0
        )

    def parse_tool_calls(self, response) -> List[Dict]:
        tool_calls = []
        for content_block in response.content:
            if content_block.type == 'tool_use':
                tool_calls.append({
                    'name': content_block.name,
                    'parameters': content_block.input
                })
        return tool_calls

    def extract_text(self, response) -> str:
        for block in response.content:
            if block.type == 'text':
                return block.text
        return ""

    def format_tool_results(
        self, messages: List[Dict], tool_calls: List[Dict], results: List[Dict],
        original_response: Any = None,
    ) -> List[Dict]:
        for call, result in zip(tool_calls, results):
            messages.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": call['name'],
                        "input": call['parameters'],
                        "id": f"tool_{call['name']}"
                    }
                ]
            })
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"tool_{call['name']}",
                        "content": json.dumps(result, ensure_ascii=False, default=json_default)
                    }
                ]
            })
        return messages


class OpenAIClient(BaseLLMClient):
    """OpenAI / compatible API client"""

    def _default_model(self) -> str:
        return 'gpt-4o'

    def __init__(self, config: dict):
        super().__init__(config)
        api_key = config['llm']['api_key'] or os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', '')
        base_url = config['llm'].get('base_url')
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def create_initial_messages(self, user_input: str) -> List[Dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]

    def send_request(
        self, messages: List[Dict], system_prompt: str, tools: List[Dict]
    ) -> Any:
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": s['name'],
                    "description": s['description'],
                    "parameters": s['input_schema']
                }
            }
            for s in tools
        ]
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=openai_tools,
            tool_choice="auto",
            temperature=0
        )

    def parse_tool_calls(self, response) -> List[Dict]:
        tool_calls = []
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.type == 'function':
                    arguments = json.loads(tool_call.function.arguments)
                    tool_calls.append({
                        'id': tool_call.id,
                        'name': tool_call.function.name,
                        'parameters': arguments
                    })
        return tool_calls

    def extract_text(self, response) -> str:
        return response.choices[0].message.content or "No response"

    def format_tool_results(
        self, messages: List[Dict], tool_calls: List[Dict], results: List[Dict],
        original_response: Any = None,
    ) -> List[Dict]:
        # OpenAI requires the assistant message with tool_calls in the conversation
        if original_response:
            msg = original_response.choices[0].message
            tool_calls_list = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls_list.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })
            messages.append({
                "role": msg.role,
                "content": msg.content or "",
                "tool_calls": tool_calls_list,
            })

        for call, result in zip(tool_calls, results):
            messages.append({
                "role": "tool",
                "tool_call_id": call.get('id', ''),
                "name": call['name'],
                "content": json.dumps(result, ensure_ascii=False, default=json_default)
            })
        return messages


def create_llm_client(config: dict) -> BaseLLMClient:
    """Factory: create appropriate LLM client from config"""
    provider = config['llm']['provider']
    if provider == 'anthropic':
        return AnthropicClient(config)
    elif provider == 'openai':
        return OpenAIClient(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

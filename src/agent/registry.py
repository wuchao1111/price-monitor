"""
Tool Registry - generic tool registration/lookup framework
"""
from typing import Any, Callable, Dict, List, Optional


class ToolRegistry:
    """Registry for agent tools"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: List[Dict] = []

    def register(self, name: str, func: Callable, schema: Dict) -> None:
        """Register a tool"""
        self._tools[name] = func
        schema['name'] = name
        self._schemas.append(schema)

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get tool by name"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict]:
        """List all tool schemas"""
        return self._schemas

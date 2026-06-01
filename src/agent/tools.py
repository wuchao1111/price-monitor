"""
Agent Tools - tool schemas and implementations
"""
from typing import Any, Dict, Optional
from logging import getLogger

from src.models.schemas import Product

logger = getLogger(__name__)


class AgentToolsMixin:
    """Mixin providing tool registration and implementations for PriceMonitorAgent"""

    def _register_tools(self) -> None:
        """Register all agent tools"""

        # add_product
        self.tool_registry.register(
            'add_product',
            self._tool_add_product,
            {
                "description": "Add a new product to monitor",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Product name"},
                        "keywords": {"type": "string", "description": "Search keywords for price query"},
                        "welfare_policy": {"type": "string", "description": "Welfare policy description (optional)"},
                        "initial_price": {"type": "number", "description": "Initial price (optional)"}
                    },
                    "required": ["name", "keywords"]
                }
            }
        )

        # list_products
        self.tool_registry.register(
            'list_products',
            self._tool_list_products,
            {
                "description": "List all monitored products",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        )

        # check_product
        self.tool_registry.register(
            'check_product',
            self._tool_check_product,
            {
                "description": "Manually trigger a price check for a product",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"}
                    },
                    "required": ["product_id"]
                }
            }
        )

        # confirm_update
        self.tool_registry.register(
            'confirm_update',
            self._tool_confirm_update,
            {
                "description": "Confirm update to the lowest price",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "new_price": {"type": "number", "description": "New lowest price"}
                    },
                    "required": ["product_id", "new_price"]
                }
            }
        )

        # get_price_history
        self.tool_registry.register(
            'get_price_history',
            self._tool_get_price_history,
            {
                "description": "Get price history for a product",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "limit": {"type": "integer", "description": "Maximum number of entries (optional, default 20)"}
                    },
                    "required": ["product_id"]
                }
            }
        )

        # get_change_log
        self.tool_registry.register(
            'get_change_log',
            self._tool_get_change_log,
            {
                "description": "Get change log for a product",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "limit": {"type": "integer", "description": "Maximum number of entries (optional, default 20)"}
                    },
                    "required": ["product_id"]
                }
            }
        )

        # delete_product
        self.tool_registry.register(
            'delete_product',
            self._tool_delete_product,
            {
                "description": "Delete a monitored product",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"}
                    },
                    "required": ["product_id"]
                }
            }
        )

    # Tool implementations

    def _tool_add_product(
        self,
        name: str,
        keywords: str,
        welfare_policy: Optional[str] = None,
        initial_price: Optional[float] = None
    ) -> Dict[str, Any]:
        product = Product(
            name=name,
            keywords=keywords,
            welfare_policy=welfare_policy,
            current_lowest_price=initial_price
        )
        product_id = self.product_crud.create(product)

        return {
            "success": True,
            "message": f"Added product '{name}' with ID {product_id}",
            "product_id": product_id
        }

    def _tool_list_products(self) -> Dict[str, Any]:
        products = self.product_crud.list_all()
        return {
            "success": True,
            "products": [p.model_dump() for p in products]
        }

    async def _tool_check_product(self, product_id: int) -> Dict[str, Any]:
        """Check price for a product"""
        product = self.product_crud.get_by_id(product_id)
        if not product:
            return {"success": False, "message": f"Product {product_id} not found"}

        # Query all skills
        results = await self.skill_manager.query_all(product.keywords)
        if not results:
            return {
                "success": False,
                "message": f"No prices found for product {product.name} from any skill"
            }

        # Apply relevance filtering
        filtered = await self.relevance_filter.filter(product.keywords, results)
        if not filtered.kept:
            return {
                "success": False,
                "message": (
                    f"No relevant prices found for {product.name}. "
                    f"All {len(filtered.filtered)} results were for different products."
                ),
                "filtered_results": filtered.filtered_details,
            }

        # Compare (use filtered results)
        compare_result = self.comparator.compare(product, filtered.kept)
        if not compare_result:
            return {
                "success": False,
                "message": f"No valid prices for product {product.name}"
            }

        response = {
            "success": True,
            "product_id": product_id,
            "product_name": product.name,
            "current_lowest": compare_result.current_lowest,
            "latest_price": compare_result.latest_price,
            "is_new_lowest": compare_result.is_new_lowest,
            "source": compare_result.source,
            "all_prices": [r.model_dump() for r in compare_result.all_prices],
            "filtered_results": filtered.filtered_details if filtered.filtered else None,
        }

        if compare_result.is_new_lowest:
            # Send notification
            self.notification_manager.send_new_low_alert(compare_result)
            response["message"] = (
                f"🎉 New lowest price found for {product.name}!\n"
                f"Old: {compare_result.current_lowest} → New: {compare_result.latest_price}\n"
                f"Please confirm the update to update the record."
            )
        else:
            response["message"] = (
                f"Checked {product.name}. "
                f"Current lowest: {compare_result.current_lowest}, "
                f"Latest found: {compare_result.latest_price}. "
                f"No new lower price found."
            )

        return response

    def _tool_confirm_update(
        self,
        product_id: int,
        new_price: float
    ) -> Dict[str, Any]:
        """Confirm price update"""
        product = self.product_crud.get_by_id(product_id)
        if not product:
            return {"success": False, "message": f"Product {product_id} not found"}

        old_price = product.current_lowest_price
        success = self.product_crud.update_lowest_price(
            product_id, new_price, old_price, "user"
        )

        if success:
            return {
                "success": True,
                "message": f"✅ Updated lowest price for {product.name}: {old_price} → {new_price}"
            }
        else:
            return {"success": False, "message": "Failed to update price"}

    def _tool_get_price_history(
        self,
        product_id: int,
        limit: int = 20
    ) -> Dict[str, Any]:
        history = self.price_history_crud.list_by_product(product_id, limit)
        return {
            "success": True,
            "product_id": product_id,
            "history": [h.model_dump() for h in history]
        }

    def _tool_get_change_log(
        self,
        product_id: int,
        limit: int = 20
    ) -> Dict[str, Any]:
        logs = self.change_log_crud.list_by_product(product_id, limit)
        return {
            "success": True,
            "product_id": product_id,
            "logs": [l.model_dump() for l in logs]
        }

    def _tool_delete_product(self, product_id: int) -> Dict[str, Any]:
        product = self.product_crud.get_by_id(product_id)
        if not product:
            return {"success": False, "message": f"Product {product_id} not found"}

        success = self.product_crud.delete(product_id)
        if success:
            return {
                "success": True,
                "message": f"Deleted product {product_id} ({product.name})"
            }
        else:
            return {"success": False, "message": "Failed to delete product"}

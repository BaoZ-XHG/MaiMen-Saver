"""麦门算账员 —— 包入口。"""
from .models import Coupon, OrderInput, Product, Promotion, SavingPlan, SolveResult
from .solver import budget_fill, solve
from .mcp_client import (McdMCPClient, parse_coupons, parse_products,
                         parse_promotions, yuan)

__version__ = "1.0.0"

__all__ = [
    "Coupon", "OrderInput", "Product", "Promotion", "SavingPlan", "SolveResult",
    "solve", "budget_fill",
    "McdMCPClient", "parse_coupons", "parse_products", "parse_promotions", "yuan",
    "__version__",
]

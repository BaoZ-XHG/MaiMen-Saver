"""麦门算账员 —— 包入口。"""
from .models import Coupon, OrderInput, Product, Promotion, SavingPlan, SolveResult
from .solver import TierRadar, budget_fill, coupon_radar, solve
from .mcp_client import (McdMCPClient, parse_coupons, parse_products,
                         parse_promotions, yuan)

__version__ = "1.0.0"

__all__ = [
    "Coupon", "OrderInput", "Product", "Promotion", "SavingPlan", "SolveResult",
    "TierRadar", "solve", "budget_fill", "coupon_radar",
    "McdMCPClient", "parse_coupons", "parse_products", "parse_promotions", "yuan",
    "__version__",
]

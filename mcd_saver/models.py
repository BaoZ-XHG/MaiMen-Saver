"""数据模型定义。

本项目所有核心数据均使用 dataclass 描述，便于序列化与单元测试。
价格统一使用「分」为单位（与麦当劳 MCP 的 calculate-price 返回值保持一致），
仅在输出展示时转换为「元」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Product:
    """单个餐品。"""
    code: str                 # 商品编码
    name: str                 # 商品名称
    price: int                # 单价（分）
    quantity: int = 1         # 数量

    @property
    def subtotal(self) -> int:
        return self.price * self.quantity


@dataclass
class Coupon:
    """优惠券（抽象统一结构，屏蔽 MCP 返回的字段差异）。"""
    coupon_id: str
    coupon_code: str
    name: str
    # 优惠类型：full_reduction 满减 / discount 折扣 / direct 立减
    kind: str
    # 满减门槛（分），如满 30 元减 5 元则 threshold=3000
    threshold: int = 0
    # 优惠金额（分）；discount 类型时为「折扣百分比整数」，如 80 表示 8 折
    value: int = 0
    # 适用商品编码集合；空表示全场通用
    product_codes: Optional[set] = None
    # 适用订单类型：1-到店 2-外送；空表示不限
    order_types: Optional[set] = None

    def discount_amount(self, total: int) -> int:
        """给定订单原价，计算该券可减免的金额（分）。

        折扣券的 value 以「百分比整数」存储（如 80 表示 8 折），
        全程整数运算避免浮点精度误差。
        """
        if total < self.threshold:
            return 0
        if self.kind == "discount":
            # value 为折扣百分比整数：省 = 原价 * (100 - value) / 100
            return total * (100 - int(self.value)) // 100
        # 满减 / 立减：直接减免固定金额
        return self.value


@dataclass
class Promotion:
    """团餐促销规则（满减 / 满折）。"""
    promotion_id: str
    promotion_type: int   # 31-满额减, 33-订单折扣
    rule_category: int    # 30-满折/折扣, 40-满减
    threshold: int = 0    # 门槛（分）
    value: int = 0        # 减免金额（分）或折扣率
    product_codes: Optional[set] = None  # 适用餐品；None 表示全部

    def discount_amount(self, total: int) -> int:
        if total < self.threshold:
            return 0
        if self.promotion_type == 33:  # 订单折扣
            return int(total * (1.0 - self.value))
        return self.value  # 满额减


@dataclass
class OrderInput:
    """用户点单输入。"""
    items: List[Product]
    order_type: int = 1          # 1-到店 2-外送
    budget: Optional[int] = None # 预算（分），可选

    @property
    def total(self) -> int:
        return sum(p.subtotal for p in self.items)


@dataclass
class SavingPlan:
    """一份省钱方案。"""
    items: List[Product]
    original_total: int          # 原价合计（分）
    coupon: Optional[Coupon] = None       # 选用的优惠券
    promotion: Optional[Promotion] = None # 选用的满减规则
    final_total: int = 0         # 最终实付（分）
    saved: int = 0               # 节省金额（分）
    note: str = ""               # 说明

    @property
    def saved_ratio(self) -> float:
        if self.original_total == 0:
            return 0.0
        return self.saved / self.original_total


@dataclass
class SolveResult:
    """求解结果。"""
    plans: List[SavingPlan] = field(default_factory=list)
    best: Optional[SavingPlan] = None

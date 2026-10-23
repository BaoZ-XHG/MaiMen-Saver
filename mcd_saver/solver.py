"""省钱求解引擎：核心算法模块。

思路：
1. 对用户点单，先计算「原价」。
2. 遍历可用优惠券，计算每张券的减免金额（券适用于全场或指定商品）。
3. 遍历团餐满减/满折规则，计算规则减免金额。
4. 由于优惠券与满减通常不可叠加，分别求解「仅用券」「仅满减」「无优惠」
   三种路径，取实付最低者作为最优方案。
5. 若指定了预算，额外给出「预算内最优凑单」建议（在预算约束下最大化
   商品组合价值，采用 0-1 背包 / 贪心启发式）。

所有计算均为确定性整数运算，不依赖大模型，结果可复现、可测试。
"""
from __future__ import annotations

from typing import List, Optional

from .models import Coupon, OrderInput, Product, Promotion, SavingPlan, SolveResult


def _applicable_total(coupon: Coupon, order: OrderInput) -> int:
    """计算券适用的商品金额合计（分）。"""
    if coupon.product_codes is None:
        return order.total
    return sum(p.subtotal for p in order.items if p.code in coupon.product_codes)


def _order_type_ok(coupon: Coupon, order_type: int) -> bool:
    if coupon.order_types is None:
        return True
    return order_type in coupon.order_types


def _build_plan(order: OrderInput, coupon: Optional[Coupon],
                promotion: Optional[Promotion], note: str) -> SavingPlan:
    original = order.total
    saved = 0
    used = []
    if coupon is not None:
        base = _applicable_total(coupon, order)
        d = coupon.discount_amount(base)
        saved += d
        used.append(f"券[{coupon.name}]省{d / 100:.2f}元")
    if promotion is not None:
        d = promotion.discount_amount(order.total)
        saved += d
        used.append(f"满减[{promotion.promotion_id}]省{d / 100:.2f}元")
    final = max(0, original - saved)
    return SavingPlan(
        items=order.items,
        original_total=original,
        coupon=coupon,
        promotion=promotion,
        final_total=final,
        saved=saved,
        note=(note + "；" + "，".join(used)) if used else note,
    )


def solve(order: OrderInput, coupons: Optional[List[Coupon]] = None,
          promotions: Optional[List[Promotion]] = None) -> SolveResult:
    """求解最优省钱方案。"""
    coupons = coupons or []
    promotions = promotions or []
    plans: List[SavingPlan] = []

    # 1) 无优惠基线
    plans.append(_build_plan(order, None, None, "不使用任何优惠"))

    # 2) 仅使用优惠券（单张，取最优）
    valid_coupons = [c for c in coupons if _order_type_ok(c, order.order_type)]
    for c in valid_coupons:
        plans.append(_build_plan(order, c, None, "使用优惠券"))

    # 3) 仅使用团餐满减/满折
    for p in promotions:
        plans.append(_build_plan(order, None, p, "使用团餐满减规则"))

    # 选实付最低者；实付相同则节省金额大者优先
    plans.sort(key=lambda x: (x.final_total, -x.saved, x.original_total))
    result = SolveResult(plans=plans, best=plans[0] if plans else None)
    return result


def budget_fill(order: OrderInput, budget: int,
                candidates: List[Product]) -> SavingPlan:
    """预算内最优凑单：在 budget 约束下从 candidates 中挑选加购商品，
    使加购商品的总价值最大（0-1 背包，每种商品可重复选，按数量拆分）。

    返回一个在「当前已点 + 最优加购」基础上的省钱方案（仅做凑单建议，
    优惠仍以订单原价为基础由 solve 负责）。
    """
    remaining = budget - order.total
    if remaining <= 0:
        return _build_plan(order, None, None, "预算已超，无法凑单")

    # 完全背包：dp[j] = 预算 j 内可达最大价值
    dp = [0] * (remaining + 1)
    pick: List[List[int]] = [[] for _ in range(remaining + 1)]
    for p in candidates:
        for j in range(p.price, remaining + 1):
            if dp[j - p.price] + p.price > dp[j]:
                dp[j] = dp[j - p.price] + p.price
                pick[j] = pick[j - p.price] + [p.code]

    best_j = max(range(remaining + 1), key=lambda j: dp[j])
    chosen_codes = pick[best_j]
    # 汇总加购商品数量
    from collections import Counter
    code_count = Counter(chosen_codes)
    new_items = list(order.items)
    for p in candidates:
        if p.code in code_count:
            new_items.append(Product(code=p.code, name=p.name,
                                     price=p.price, quantity=code_count[p.code]))
    filled = OrderInput(items=new_items, order_type=order.order_type,
                        budget=budget)
    plan = _build_plan(filled, None, None, f"预算{remaining / 100:.2f}元凑单建议")
    return plan

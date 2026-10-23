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

from dataclasses import dataclass

from .models import Coupon, OrderInput, Product, Promotion, SavingPlan, SolveResult


@dataclass
class TierRadar:
    """凑单雷达：当前订单离下一档满减的差距与建议。"""
    next_tier: Optional[Promotion]    # 下一档满减规则；None 表示已到最高档
    gap: int                          # 还差多少金额（分）触发下一档
    suggest: bool                     # 是否建议凑单（凑单净收益为正）
    net_saving: int = 0               # 凑单后的净节省（分）
    suggestion: str = ""              # 凑单建议文案
    fill_items: List[Product] = None  # 建议加购的商品组合（凑够 gap）

    def __post_init__(self):
        if self.fill_items is None:
            self.fill_items = []


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


def _min_cost_fill(gap: int, candidates: List[Product]) -> List[Product]:
    """用最小代价凑够 gap 金额：从 candidates 中挑选商品组合，
    使总价 >= gap 且超出最少（贪心 + 完全背包求最小超出的精确解）。

    返回加购商品列表（每种商品可能多份）。candidates 为空或无法凑够时返回空列表。
    """
    if gap <= 0 or not candidates:
        return []
    # 完全背包求「恰好或最小超出 gap」的最小总价，上限设为 gap + max(price)
    max_price = max(p.price for p in candidates)
    limit = gap + max_price
    INF = float("inf")
    # dp[j] = 达到总价 j 所需的最少件数；仅当 j 可由商品组合凑出
    dp = [INF] * (limit + 1)
    dp[0] = 0
    # 记录每个总价对应的商品选择
    pick: List[Optional[List[str]]] = [None] * (limit + 1)
    pick[0] = []
    for p in candidates:
        for j in range(p.price, limit + 1):
            if dp[j - p.price] + 1 < dp[j]:
                dp[j] = dp[j - p.price] + 1
                pick[j] = (pick[j - p.price] or []) + [p.code]

    # 找 >= gap 且可达的最小总价
    best_j = None
    for j in range(gap, limit + 1):
        if dp[j] < INF:
            best_j = j
            break
    if best_j is None:
        return []
    from collections import Counter
    cnt = Counter(pick[best_j])
    result = []
    for p in candidates:
        if p.code in cnt:
            result.append(Product(code=p.code, name=p.name,
                                  price=p.price, quantity=cnt[p.code]))
    return result


def coupon_radar(order: OrderInput,
                 promotions: Optional[List[Promotion]] = None,
                 candidates: Optional[List[Product]] = None) -> TierRadar:
    """凑单雷达：计算当前订单离「下一档满减」还差多少，并给出具体凑单建议。

    核心判断逻辑：
    - 找出所有门槛高于当前原价的满减档，取门槛最低的一档作为「下一档」。
    - 计算差额 gap = 门槛 - 原价。
    - 若 gap < 该档减免金额，说明「凑 gap 元能省 value 元」，净收益
      net_saving = value - gap > 0，值得凑单；否则不建议凑单。
    - 若提供了 candidates（候选加购商品），用最小代价算法给出具体
      「建议加购 X + Y」的组合，正好凑够 gap（超出最少）。

    这与网页端「满减冲刺条」逻辑保持一致，前后端可对拍。
    """
    promotions = promotions or []
    total = order.total
    tiers = [p for p in promotions if p.threshold > total]
    if not tiers:
        return TierRadar(next_tier=None, gap=0, suggest=False,
                         net_saving=0, suggestion="已触发所有满减档位",
                         fill_items=[])
    next_tier = min(tiers, key=lambda p: p.threshold)
    gap = next_tier.threshold - total
    value = next_tier.value
    if next_tier.promotion_type == 33:
        value = int(total * (100 - next_tier.value) // 100)
    net_saving = value - gap
    suggest = net_saving > 0

    fill_items = _min_cost_fill(gap, candidates or []) if suggest else []

    if suggest:
        if fill_items:
            desc = " + ".join(f"{p.name}×{p.quantity}" for p in fill_items)
            fill_sum = sum(p.subtotal for p in fill_items)
            suggestion = (f"再凑 ¥{gap / 100:.2f} 触发「{next_tier.promotion_id}」，"
                          f"建议加购：{desc}（共 ¥{fill_sum / 100:.2f}），"
                          f"净省 ¥{net_saving / 100:.2f}")
        else:
            suggestion = (f"再凑 ¥{gap / 100:.2f} 即可触发「{next_tier.promotion_id}」，"
                          f"凑单后净省 ¥{net_saving / 100:.2f}")
    else:
        suggestion = (f"离「{next_tier.promotion_id}」还差 ¥{gap / 100:.2f}，"
                      f"凑单不划算（减 ¥{value / 100:.2f} 小于凑单金额）")
    return TierRadar(next_tier=next_tier, gap=gap, suggest=suggest,
                     net_saving=net_saving, suggestion=suggestion,
                     fill_items=fill_items)


def budget_fill(order: OrderInput, budget: int,
                candidates: List[Product]) -> SavingPlan:
    """预算内最优凑单：在 budget 约束下从 candidates 中挑选加购商品，
    使加购商品的总价值最大（完全背包，每种商品可重复选）。

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

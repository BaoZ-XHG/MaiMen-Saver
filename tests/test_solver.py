"""核心求解器单元测试。

运行：python -m pytest tests/ -v
"""
from mcd_saver import (Coupon, OrderInput, Product, Promotion, budget_fill,
                       coupon_radar, solve)


def _order():
    return OrderInput(items=[
        Product(code="A", name="巨无霸", price=2400, quantity=2),
        Product(code="B", name="中薯条", price=1200, quantity=1),
        Product(code="C", name="可乐", price=800, quantity=1),
    ], order_type=1)


def test_no_coupon_baseline():
    r = solve(_order(), [], [])
    assert r.best.final_total == 6800
    assert r.best.saved == 0


def test_full_reduction_coupon():
    c = Coupon(coupon_id="1", coupon_code="x", name="满30减10",
               kind="full_reduction", threshold=3000, value=1000)
    r = solve(_order(), [c], [])
    # 原价68元，满足满30减10
    assert r.best.final_total == 5800
    assert r.best.saved == 1000


def test_discount_coupon():
    c = Coupon(coupon_id="2", coupon_code="y", name="8折",
               kind="discount", threshold=0, value=80)
    r = solve(_order(), [c], [])
    # 68 * 0.8 = 54.4 元
    assert r.best.final_total == 5440
    assert r.best.saved == 1360


def test_pick_best_between_coupon_and_promotion():
    c = Coupon(coupon_id="1", coupon_code="x", name="满30减10",
               kind="full_reduction", threshold=3000, value=1000)
    p = Promotion(promotion_id="p", promotion_type=31, rule_category=40,
                  threshold=5000, value=2000)
    r = solve(_order(), [c], [p])
    # 满减省20元 > 券省10元，应选满减
    assert r.best.promotion is not None
    assert r.best.final_total == 4800


def test_threshold_not_met():
    c = Coupon(coupon_id="1", coupon_code="x", name="满100减20",
               kind="full_reduction", threshold=10000, value=2000)
    r = solve(_order(), [c], [])
    # 原价68元不满100，券不可用，走无优惠
    assert r.best.final_total == 6800


def test_budget_fill():
    order = _order()  # 原价68元
    candidates = [
        Product(code="D", name="鸡块", price=900, quantity=1),
        Product(code="E", name="苹果派", price=700, quantity=1),
    ]
    filled = budget_fill(order, budget=8000, candidates=candidates)
    # 剩余12元预算，可加购 鸡块(9元) 或 苹果派(7元) 或 组合
    # 12元内最大价值：鸡块9 + 甜筒? 无甜筒，故选 鸡块(9) 最优
    added = [p for p in filled.items if p.code in ("D", "E")]
    assert sum(p.subtotal for p in added) <= 1200


def test_product_specific_coupon():
    # 券仅适用于巨无霸(A)
    c = Coupon(coupon_id="3", coupon_code="z", name="巨无霸满2减1",
               kind="full_reduction", threshold=4000, value=500,
               product_codes={"A"})
    r = solve(_order(), [c], [])
    # 巨无霸合计48元，满足满40减5
    assert r.best.saved == 500
    assert r.best.final_total == 6300


def test_coupon_radar_gap():
    # 原价 68 元，下一档满 80 减 20，还差 12 元
    order = _order()
    promotions = [
        Promotion(promotion_id="P1", promotion_type=31, rule_category=40,
                  threshold=5000, value=1500),   # 满50减15（已触发）
        Promotion(promotion_id="P2", promotion_type=31, rule_category=40,
                  threshold=8000, value=2000),   # 满80减20（下一档）
    ]
    radar = coupon_radar(order, promotions)
    assert radar.gap == 1200
    assert radar.suggest is True
    # 净省 = 20 - 12 = 8 元
    assert radar.net_saving == 800


def test_coupon_radar_fill_items():
    # 差 12 元，候选商品有甜筒(4元)、苹果派(7元)、鸡块(9元)
    order = _order()  # 原价 68 元
    promotions = [
        Promotion(promotion_id="P2", promotion_type=31, rule_category=40,
                  threshold=8000, value=2000),
    ]
    candidates = [
        Product(code="D", name="甜筒", price=400, quantity=1),
        Product(code="E", name="苹果派", price=700, quantity=1),
        Product(code="F", name="鸡块", price=900, quantity=1),
    ]
    radar = coupon_radar(order, promotions, candidates)
    assert radar.suggest is True
    assert radar.fill_items
    # 凑够 12 元，最小超出：鸡块(9) + 甜筒(4) = 13 元，超出 1 元
    fill_sum = sum(p.subtotal for p in radar.fill_items)
    assert fill_sum >= 1200
    assert fill_sum - 1200 <= 100  # 超出不超过 1 元


def test_coupon_radar_not_worth():
    # 原价 68 元，下一档满 100 减 10，还差 32 元，凑单不划算
    order = _order()
    promotions = [
        Promotion(promotion_id="P1", promotion_type=31, rule_category=40,
                  threshold=10000, value=1000),
    ]
    radar = coupon_radar(order, promotions)
    assert radar.gap == 3200
    assert radar.suggest is False
    assert radar.net_saving < 0


def test_coupon_radar_max_tier():
    # 已超过所有档位
    order = _order()
    promotions = [
        Promotion(promotion_id="P1", promotion_type=31, rule_category=40,
                  threshold=5000, value=1500),
    ]
    radar = coupon_radar(order, promotions)
    assert radar.next_tier is None
    assert radar.suggest is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

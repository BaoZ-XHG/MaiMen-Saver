"""命令行 Demo：麦门算账员。

用法：
    # 方式一：离线演示（无需 MCP Token，使用示例数据）
    python cli.py demo

    # 方式二：真实调用麦当劳 MCP（需设置 MCP_TOKEN 环境变量）
    MCP_TOKEN=xxx python cli.py real --store-code 123456 --order-type 1

通过 Demo 展示核心求解能力：给定「想吃的商品 + 可用券 + 满减规则」，
输出最优省钱方案与省钱金额。
"""
from __future__ import annotations

import argparse
import json
import sys

from mcd_saver import (Coupon, OrderInput, Product, Promotion, budget_fill,
                       parse_coupons, parse_promotions, solve, yuan)


def _print_plan(plan, title="最优方案"):
    print(f"\n=== {title} ===")
    print(f"商品: {', '.join(f'{p.name}x{p.quantity}' for p in plan.items)}")
    print(f"原价合计: ¥{yuan(plan.original_total)}")
    print(f"优惠: {plan.note}")
    print(f"实付金额: ¥{yuan(plan.final_total)}")
    print(f"节省金额: ¥{yuan(plan.saved)} (省 {plan.saved_ratio * 100:.1f}%)")


def demo():
    # 构造一份示例点单 + 可用券 + 满减规则
    order = OrderInput(
        items=[
            Product(code="A001", name="巨无霸", price=2400, quantity=2),
            Product(code="B002", name="中薯条", price=1200, quantity=1),
            Product(code="C003", name="可乐", price=800, quantity=1),
        ],
        order_type=1,
    )
    coupons = [
        Coupon(coupon_id="C1", coupon_code="CC1", name="满30减10", kind="full_reduction",
               threshold=3000, value=1000),
        Coupon(coupon_id="C2", coupon_code="CC2", name="全场8折", kind="discount",
               threshold=0, value=80),
    ]
    promotions = [
        Promotion(promotion_id="P1", promotion_type=31, rule_category=40,
                  threshold=5000, value=1500),
    ]

    result = solve(order, coupons, promotions)
    print("已尝试方案：")
    for i, p in enumerate(result.plans, 1):
        print(f"  {i}. 实付 ¥{yuan(p.final_total)} — {p.note}")
    _print_plan(result.best)

    # 预算凑单示例
    candidates = [
        Product(code="D004", name="鸡块", price=900, quantity=1),
        Product(code="E005", name="苹果派", price=700, quantity=1),
        Product(code="F006", name="甜筒", price=400, quantity=1),
    ]
    filled = budget_fill(order, budget=8000, candidates=candidates)
    _print_plan(filled, "预算 ¥80 凑单建议")


def real(store_code, order_type):
    from mcd_saver import McdMCPClient
    client = McdMCPClient()
    # 1) 拉取餐品列表
    meals_raw = client.call_tool("query-meals", {
        "storeCode": store_code, "orderType": order_type, "beType": 1,
    })
    print("餐品数据：")
    print(json.dumps(meals_raw, ensure_ascii=False, indent=2)[:2000])

    # 2) 拉取门店可用券
    coupons_raw = client.call_tool("query-store-coupons", {
        "storeCode": store_code, "orderType": order_type, "beType": 1,
    })
    coupons = parse_coupons(coupons_raw if isinstance(coupons_raw, list)
                            else coupons_raw.get("data", []))
    print(f"\n解析到 {len(coupons)} 张优惠券")


def main():
    parser = argparse.ArgumentParser(description="麦门算账员 CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("demo", help="离线演示（无需 Token）")

    real_p = sub.add_parser("real", help="调用真实麦当劳 MCP")
    real_p.add_argument("--store-code", required=True)
    real_p.add_argument("--order-type", type=int, default=1, choices=[1, 2])

    args = parser.parse_args()
    if args.cmd == "demo":
        demo()
    elif args.cmd == "real":
        real(args.store_code, args.order_type)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

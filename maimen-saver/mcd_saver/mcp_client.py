"""麦当劳 MCP 集成层。

职责：
1. 将麦当劳 MCP 各工具返回的原始 JSON 解析为项目内部模型（Product/Coupon/Promotion）。
2. 提供一个轻量的 MCP 客户端，用于在本地脚本中直接调用麦当劳 MCP 工具。

说明：
- 本项目既可运行在 WorkBuddy 等支持 MCP 的智能体环境中（由智能体调用
  mcp__mcd-mcp__* 工具，再将原始数据交给 solver 求解），
- 也可独立运行：通过 streamablehttp 协议直连 https://mcp.mcd.cn，
  使用 MCP_TOKEN 环境变量鉴权。

设计原则：解析层与求解层解耦，求解算法不感知 MCP 细节，可离线测试。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import Coupon, Product, Promotion


# --------------------------------------------------------------------------- #
# 原始 JSON -> 内部模型
# --------------------------------------------------------------------------- #
def parse_products(raw_items: List[Dict[str, Any]]) -> List[Product]:
    """解析餐品列表（query-meals / calculate-price 返回的商品结构）。"""
    products: List[Product] = []
    for it in raw_items:
        code = it.get("productCode") or it.get("code") or ""
        name = it.get("productName") or it.get("name") or code
        price = int(it.get("price") or it.get("productPrice") or 0)
        qty = int(it.get("quantity") or 1)
        products.append(Product(code=code, name=name, price=price, quantity=qty))
    return products


def parse_coupons(raw_items: List[Dict[str, Any]]) -> List[Coupon]:
    """解析优惠券（query-store-coupons / query-my-coupons 返回结构）。

    麦当劳 MCP 的券字段可能因接口而异，这里做容错解析，统一映射到 Coupon。
    """
    coupons: List[Coupon] = []
    for it in raw_items:
        cid = str(it.get("couponId") or it.get("id") or "")
        ccode = str(it.get("couponCode") or it.get("code") or cid)
        name = str(it.get("couponName") or it.get("name") or "优惠券")
        # 尝试识别优惠类型
        kind = "direct"           # 默认按立减处理
        threshold = int(it.get("threshold") or it.get("useThreshold") or 0)
        value = int(it.get("value") or it.get("discountValue")
                    or it.get("amount") or 0)
        if "折" in name or "discount" in str(it.get("type", "")).lower():
            kind = "discount"
            # 折扣统一转为百分比整数：0.8 -> 80, "8折" -> 80
            if isinstance(value, float) and value <= 1:
                value = int(value * 100)
        elif threshold > 0:
            kind = "full_reduction"
        coupons.append(Coupon(
            coupon_id=cid, coupon_code=ccode, name=name,
            kind=kind, threshold=threshold, value=value,
        ))
    return coupons


def parse_promotions(raw_items: List[Dict[str, Any]]) -> List[Promotion]:
    """解析团餐促销规则（query-promotions 返回结构）。

    promotionType: 31-满额减, 33-订单折扣
    ruleCategory: 30-满折/折扣, 40-满减
    ruleDetail 通常形如 {"threshold": 3000, "value": 500} 或 {"discount": 0.8}
    """
    promotions: List[Promotion] = []
    for it in raw_items:
        pid = str(it.get("promotionId") or "")
        ptype = int(it.get("promotionType") or 0)
        rcat = int(it.get("ruleCategory") or 0)
        detail = it.get("ruleDetail") or {}
        threshold = int(detail.get("threshold") or it.get("threshold") or 0)
        value = int(detail.get("value") or it.get("value") or 0)
        if ptype == 33:  # 折扣
            # 折扣可能以 0.8 或 80 表示，统一为 0-1
            if value > 1:
                value = value / 100.0
            promotions.append(Promotion(
                promotion_id=pid, promotion_type=ptype, rule_category=rcat,
                threshold=threshold, value=int(value * 100) if value <= 1 else value,
            ))
        else:
            promotions.append(Promotion(
                promotion_id=pid, promotion_type=ptype, rule_category=rcat,
                threshold=threshold, value=value,
            ))
    return promotions


# --------------------------------------------------------------------------- #
# 轻量 MCP 客户端（独立运行 / 本地调试用）
# --------------------------------------------------------------------------- #
class McdMCPClient:
    """通过 streamablehttp 直连麦当劳 MCP 的极简客户端。

    仅用于本地独立运行 Demo，正常参赛建议在 WorkBuddy 智能体中由
    系统调用 mcp__mcd-mcp__* 工具后，把原始 JSON 交给 parse_* 函数。
    """

    def __init__(self, token: Optional[str] = None, url: str = "https://mcp.mcd.cn"):
        import os
        self.token = token or os.environ.get("MCP_TOKEN", "")
        self.url = url

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """调用单个 MCP 工具（JSON-RPC 2.0 over streamable HTTP）。"""
        import json
        import urllib.request

        if not self.token:
            raise RuntimeError(
                "缺少 MCP_TOKEN，请设置环境变量 MCP_TOKEN 或传入 token 参数")

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            }, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(f"MCP 调用失败: {data['error']}")
        return data.get("result", {})


def yuan(cents: int) -> str:
    """分 -> 元，用于展示。"""
    return f"{cents / 100:.2f}"

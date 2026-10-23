# 麦门算账员（MaiMen Saver）

> 一键算出「你这单到底怎么买最省」的麦当劳省钱解题引擎。
> 麦当劳程序员创意开发大赛参赛作品。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

---

## 一句话介绍

别人做的省钱工具是"帮你查有哪些券"，**麦门算账员**做的是"直接告诉你这单怎么买、用哪张券、凑多少、省多少钱"。

你只需说一句人话，例如：

> 「我想吃 2 个巨无霸、1 份中薯、1 杯可乐，预算 80 块」

它就会调用麦当劳 MCP 拉取**实时餐品价格 + 可用优惠券 + 满减规则**，通过一个**确定性组合优化算法**，自动算出：

- ✅ 最低实付金额是多少
- ✅ 该用哪张券 / 哪个满减规则（不能叠加，选最省的）
- ✅ 预算内还该凑点什么最划算
- ✅ 一共帮你省了多少钱、省了几个百分点

---

## 核心亮点（为什么值得一个 Star）

| 亮点 | 说明 |
|---|---|
| 🎯 **确定性算法** | 核心求解器是纯整数运算的贪心 + 完全背包组合优化，**不依赖大模型猜测**，同输入必得同结果，可测试、可复现 |
| 🧮 **可量化省钱反馈** | 每个方案都输出「省 ¥X / 省 Y%」，社交传播性强 |
| 📡 **凑单雷达** | 独有的「满减冲刺」逻辑：实时判断离下一档满减还差几块、凑单是否划算 |
| 🖥️ **可交互网页** | 提供在线试算落地页，选餐品、调预算实时出最优方案（见 `docs/index.html`） |
| 🔌 **双模式运行** | 既可在 WorkBuddy 等智能体中由系统调用 MCP 工具，也可独立通过 `MCP_TOKEN` 直连 `mcp.mcd.cn` |
| 📦 **零重依赖** | 仅用 Python 标准库，`pip install` 即可跑，开箱即用 |
| 🧪 **完整测试** | 11 个单元测试覆盖满减/折扣/门槛/商品限定券/预算凑单/凑单雷达等场景 |

---

## 在线试算

🎮 **打开即玩**：直接打开 [`docs/index.html`](./docs/index.html)，或在浏览器访问部署后的页面——选择餐品、拖动预算、切换到店/外送，实时算出最优省钱方案与省钱金额。

---

## 快速开始

### 方式一：离线演示（无需任何配置）

```bash
git clone https://github.com/BaoZ-XHG/MaiMen-Saver.git
cd MaiMen-Saver
python cli.py demo
```

即可看到一份完整的最优省钱方案演示输出。

### 方式二：真实调用麦当劳 MCP（可选）

> 需先申请麦当劳 MCP Token，详见 [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)。

```bash
# Windows (PowerShell)
$env:MCP_TOKEN = "你的Token"
python cli.py real --store-code 123456 --order-type 1

# macOS / Linux
MCP_TOKEN=你的Token python cli.py real --store-code 123456 --order-type 1
```

### 方式三：在 WorkBuddy 中使用

1. 在 WorkBuddy 左侧「连接器」→「自定义连接器」→「配置 MCP」，填入：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

2. 启用 `mcd-mcp` 后，直接对 WorkBuddy 说：**「我想吃巨无霸和薯条，帮我算算怎么买最省」**，AI 会调用麦当劳 MCP 工具，再将结果交给本项目的求解器计算最优方案。

---

## 项目结构

```
MaiMen-Saver/
├── README.md                  # 本文件
├── CONTEST_DECLARATION.md     # 参赛声明（官方原文，不可改动）
├── MCP_INTEGRATION.md         # MCP 集成说明
├── mcp-config.example.json    # 脱敏配置示例
├── workbuddy.md               # WorkBuddy 对话上下文（联动奖励用）
├── cli.py                     # 命令行入口
├── LICENSE
├── docs/
│   └── index.html             # 可交互在线试算网页
├── mcd_saver/
│   ├── __init__.py
│   ├── models.py              # 数据模型（Product/Coupon/Promotion/SavingPlan）
│   ├── solver.py              # 核心省钱求解算法
│   └── mcp_client.py          # MCP 集成层（解析 + 轻量客户端）
└── tests/
    └── test_solver.py         # 单元测试
```

---

## 算法说明

求解流程（见 `mcd_saver/solver.py`）：

1. **原价计算**：对用户点单累加各商品 `price × quantity`。
2. **券匹配**：遍历可用优惠券，过滤订单类型与适用商品范围，计算每张券的减免金额（满减 / 折扣 / 立减）。
3. **满减匹配**：遍历团餐满减 / 满折规则，计算规则减免金额。
4. **不可叠加求解**：因优惠券与满减通常互斥，分别求解「仅用券」「仅满减」「无优惠」三条路径，取实付最低者。
5. **凑单雷达**：找出离当前原价最近的下一档满减，计算差额，判断「再凑 X 元能省 Y 元」是否划算（净收益 = 减免额 − 凑单额），并用**最小代价算法**给出具体「建议加购某商品」的组合（总价刚好 ≥ 差额且超出最少）。
6. **预算凑单**（可选）：在预算约束下用**完全背包**算法，从候选加购商品中挑选使加购总价值最大的组合。

所有金额以「分」为单位做整数运算，避免浮点精度误差。

> 「凑单雷达」与网页端「满减冲刺条」为同一套逻辑，前后端结果可对拍一致。

---

## 运行测试

```bash
pip install pytest
python -m pytest tests/ -v
```

预期输出：`11 passed`。

---

## 目标用户

- 麦当劳忠实用户 / 「麦门」信徒，想吃得爽又花得少的人
- 需要为团队点团餐、想精准用满减规则的上班族
- 对「用算法解决生活问题」感兴趣的开发者

---

## 免责声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，非麦当劳官方产品。项目输出仅供参考，不构成任何专业建议；餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。详见 [CONTEST_DECLARATION.md](./CONTEST_DECLARATION.md)。

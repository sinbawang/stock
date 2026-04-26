"""
=============================================================================
Tushare 港股分钟 K 线数据获取指南
=============================================================================

【第 1 步】申请免费 Token
-----------
1. 打开网站：https://tushare.pro
2. 点击【注册】，用邮箱注册账号
3. 邮箱验证后进入个人中心
4. 找到【Token】或【个人账户信息】
5. 获取你的 token（32 位字符串）
6. 复制并保存好 token（不要泄露）

示例 token 格式：
  abc123def456ghi789jkl012mno345pqr

【第 2 步】设置环境变量或在代码中使用 Token
-----------
方式 A：设置 Windows 环境变量（推荐）
  1. Win + R，输入 "sysdm.cpl"，打开系统属性
  2. 点击【环境变量】
  3. 新建用户变量：
     变量名: TUSHARE_TOKEN
     变量值: 你的 token（从第1步复制）
  4. 重启 Python 进程

方式 B：在代码中硬编码（不推荐）
  import tushare as ts
  ts.set_token("你的token")

【第 3 步】港股分钟线数据说明
-----------
- 免费额度：有限制（通常 1000 条/天）
- 付费方案：开通高端版可获得更高额度
- 港股代码格式：例如 03690（支持 5 位数字）
- 数据延迟：实时（延迟通常 15 分钟内）

【第 4 步】使用示例
-----------
详见下方脚本：fetch_with_tushare.py

【常见问题】
-----------
Q: Token 过期了怎么办？
A: 在 tushare.pro 网站重新复制，环境变量重新设置

Q: 免费额度不够怎么办？
A: 
   - 分批获取（每天获取部分数据）
   - 或考虑付费版本
   - 或改用其他数据源

Q: 港股有没有其他免费来源？
A:
   - yfinance（易被限流）
   - akshare（仅支持日线）
   - 平安证券 API（需开户）

=============================================================================
"""

import os
import tushare as ts

# 获取 tushare token
TOKEN = os.environ.get("TUSHARE_TOKEN")

if not TOKEN:
    print("❌ 错误：未找到 TUSHARE_TOKEN 环境变量")
    print("\n请按以下步骤操作：")
    print("1. 访问 https://tushare.pro（用邮箱注册）")
    print("2. 获取你的 token")
    print("3. 设置 Windows 环境变量 TUSHARE_TOKEN=你的token")
    print("4. 重启终端/IDE，再运行此脚本")
    exit(1)

print(f"✓ Token 已加载 (前8位: {TOKEN[:8]}...)")

# 初始化 tushare
pro = ts.pro_api(TOKEN)

# 获取港股 03690 的 60 分钟 K 线
print("\n正在获取美团 03690 60 分钟 K 线...")

try:
    # tushare 港股代码格式：HK.03690
    df = pro.hk_equity_kline(
        ts_code="HK.03690",
        start_date="20260303",
        end_date="20260412",
        freq="60"  # 60 分钟
    )
    
    print(f"\n✓ 成功获取 {len(df)} 根 K 线")
    print(f"\n前 3 条：")
    print(df.head(3))
    
    # 保存到 CSV
    output_path = "data/03690_美团/60m/3690_60m_tushare.csv"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\n已保存到：{output_path}")
    
except Exception as e:
    print(f"\n✗ 获取失败：{type(e).__name__}")
    print(f"  {str(e)}")
    print("\n可能的原因：")
    print("  1. Token 无效或过期")
    print("  2. 免费额度已用尽")
    print("  3. 港股分钟线需要付费版权限")
    print("  4. 网络连接问题")

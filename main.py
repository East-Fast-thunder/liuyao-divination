# -*- coding: utf-8 -*-
"""
六爻卜卦 · 命令行交互程序
==========================
流程：
  1. 引导填写问卦信息（问题、类别、主体、时间范围等）
  2. 检查问题适合度（宿命化提问会提示改写）
  3. 收集起卦时间（默认现在，可手动指定 / 可换真太阳时）
  4. 三枚铜钱随机起卦（自下而上六次）
  5. 排盘并显示完整卦象（不作解卦）

运行：
  python main.py            交互模式
  python main.py --demo     演示模式（固定时间与种子，可复现）
  python main.py --no-color 关闭彩色输出

仅供传统文化学习与娱乐参考，请理性看待。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Optional

# 让脚本无论从哪个目录运行都能找到 liuyao 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from liuyao import 构建干支时间, 起卦, 排盘, 取用神, 输出排盘, 问事
from liuyao.wengua import 问题类别列表, 主体列表, 检查问题适合度, 优化建议
from liuyao.record import 保存记录, 列出记录, 默认存档目录
from liuyao.divination import 起卦结果

# ---------------------------------------------------------------------------
# 终端兼容（Windows 控制台 UTF-8）
# ---------------------------------------------------------------------------

def _启用utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


import unicodedata

def get_str_width(text):
    """计算字符串的视觉宽度（中文占2个单位，英文/符号占1个单位）"""
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)

def center_text(text, width):
    """根据视觉宽度进行居中补齐"""
    w = get_str_width(text)
    if w >= width:
        return text
    pad = width - w
    left = pad // 2
    right = pad - left
    return ' ' * left + text + ' ' * right

def generate_banner(lines, total_width=65):
    """生成对齐的边框"""
    inner_width = total_width - 2
    banner = []
    banner.append('╔' + '═' * inner_width + '╗')
    for line in lines:
        if not line:
            banner.append('║' + ' ' * inner_width + '║')
        else:
            banner.append('║' + center_text(line, inner_width) + '║')
    banner.append('╚' + '═' * inner_width + '╝')
    return '\n'.join(banner)

# 你的文字内容
lines = [
    "",
    "六 爻 卜 卦 · 铜 钱 起 卦 排 盘",
    "",
    "起卦 → 四象六爻 → 动爻变卦 → 干支排盘 → 断卦要素",
    "（只排盘，不解卦）",
    ""
]

BANNER = generate_banner(lines)



# ---------------------------------------------------------------------------
# 交互辅助
# ---------------------------------------------------------------------------

def 询问(prompt: str, default: str = "", allow_empty: bool = True) -> str:
    """基本输入"""
    suffix = f"（默认：{default}）" if default else "（可留空）"
    try:
        raw = input(f"  {prompt}{suffix}：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  已取消。")
        sys.exit(0)
    if not raw:
        return default
    return raw


def 选择(prompt: str, options: list, default_idx: int = 0, allow_skip: bool = True) -> str:
    """编号选择"""
    print(f"\n  {prompt}")
    for i, op in enumerate(options):
        mark = " ←默认" if i == default_idx else ""
        print(f"    {i + 1}. {op}{mark}")
    while True:
        try:
            raw = input(f"  请输入序号 1-{len(options)}"
                        f"{'（直接回车取默认）' if allow_skip else ''}：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  已取消。")
            sys.exit(0)
        if not raw:
            return options[default_idx]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  ⚠ 输入无效，请重新输入。")


def 询问时间() -> datetime:
    """询问起卦时间"""
    print("\n  【起卦时间】")
    print("    1. 现在（默认）")
    print("    2. 手动指定（格式 2026-10-27 14:30）")
    while True:
        raw = input("    请选择 1-2（回车默认现在）：").strip()
        if raw in ("", "1"):
            return datetime.now()
        if raw == "2":
            while True:
                s = input("    请输入时间（YYYY-MM-DD HH:MM）：").strip()
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                            "%Y/%m/%d %H:%M", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        continue
                print("    ⚠ 格式不正确，请重新输入。")


def 询问真太阳时() -> Optional[float]:
    """询问是否换算真太阳时，返回经度"""
    ans = input("\n  是否换算真太阳时？（提高排盘精度，需知道当地经度）[y/N]：").strip().lower()
    if ans not in ("y", "yes", "是"):
        return None
    while True:
        s = input("  请输入当地经度（东经为正，如北京 116.4）：").strip()
        try:
            lon = float(s)
            if -180 <= lon <= 180:
                return lon
        except ValueError:
            pass
        print("    ⚠ 请输入 -180 到 180 之间的数字。")


# ---------------------------------------------------------------------------
# 问卦信息收集
# ---------------------------------------------------------------------------

def 收集问事() -> 问事:
    print("\n" + "─" * 66)
    print("  第 1 步 · 填写问卦信息（六爻极依赖「所问之事」是否明确）")
    print("─" * 66)

    problem = 询问("请输入你要问的具体问题（越具体越好）")

    print()
    类别 = 选择("问题类别（用于取用神）", 问题类别列表,
                default_idx=问题类别列表.index("综合"))
    主体 = 选择("问卦主体", 主体列表, default_idx=0)

    关系 = ""
    if "关系" in 主体 or 类别 == "婚姻感情":
        关系 = 询问("你与对方的关系定位（如：恋人/同事/父子/朋友）")

    背景 = 询问("事情背景（简要描述即可）")
    时限 = 询问("时间范围（如：未来一个月/三个月/今年内，可留空）")
    明确 = 询问("是否有明确时限或截止日期（有则填写，如 11 月底）")

    wq = 问事(
        问题=problem or "（未填写具体问题）",
        类别=类别,
        主体=主体,
        关系定位=关系,
        背景=背景,
        时间范围=时限,
        明确时限=明确,
    )

    # 问题适合度检查
    tips = 检查问题适合度(wq)
    if tips:
        print("\n  " + "─" * 62)
        print("  ⚠ 问卦提示")
        print("  " + "─" * 62)
        for t in tips:
            print(f"    · {t}")
        for e in 优化建议(wq):
            print(f"    · 可参考问法：{e}")
        print("  " + "─" * 62)
        cont = input("\n  是否仍用当前问题继续起卦？[Y/n]：").strip().lower()
        if cont in ("n", "no", "否"):
            newq = 询问("\n  请重新输入问题", default=wq.问题)
            wq.问题 = newq
            wq.类别 = 选择("问题类别", 问题类别列表,
                           default_idx=问题类别列表.index(wq.类别))

    return wq


# ---------------------------------------------------------------------------
# 起卦方式
# ---------------------------------------------------------------------------

def 起卦确认() -> Optional[起卦结果]:
    """
    展示三枚铜钱规则并向用户确认后起卦。
    """
    print("\n" + "─" * 66)
    print("  第 2 步 · 起卦（三枚铜钱法，自下而上六掷）")
    print("─" * 66)
    print("    每爻掷三枚铜钱，正面记 3、反面记 2：")
    print("      三正    9 → 老阳 ○（动，变阴）")
    print("      两正一反 8 → 少阴（静）")
    print("      一正两反 7 → 少阳（静）")
    print("      三反    6 → 老阴 ✕（动，变阳）")
    print("    第 1 掷 = 初爻（最下），第 6 掷 = 上爻（最上）")
    print()

    mode = 选择("起卦方式", [
        "随机起卦（真随机，不可复现）",
        "随机起卦（指定种子，可复现）",
        "手工报数（输入一个整数，以其为种子）",
        "手工指定六爻（手动输入 6 个 6/7/8/9）",
    ], default_idx=0)

    print("\n  正在摇卦……")
    if mode.startswith("随机起卦（真随机"):
        return 起卦(seed=None)
    if mode.startswith("随机起卦（指定种子"):
        while True:
            s = input("  请输入随机种子（整数）：").strip()
            try:
                return 起卦(seed=int(s))
            except ValueError:
                print("    ⚠ 请输入整数。")
    if mode.startswith("手工报数"):
        while True:
            s = input("  请输入一个整数（按传统报数，以其为种子）：").strip()
            try:
                return 起卦(seed=int(s))
            except ValueError:
                print("    ⚠ 请输入整数。")
    # 手工指定
    while True:
        s = input("  请输入 6 个爻值（从下到上，用空格分隔，如 7 8 9 6 7 8）：").strip()
        parts = s.replace(",", " ").split()
        try:
            vals = [int(x) for x in parts]
            return 起卦(手动输入=vals)
        except ValueError as e:
            print(f"    ⚠ {e}，请重新输入。")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def 运行交互(demo: bool = False, 存档目录: Optional[str] = None,
            不存档: bool = False):
    print(BANNER)

    if demo:
        wq = 问事(问题="未来三个月我在这个项目上的发展如何",
                  类别="事业工作", 主体="问自己",
                  背景="演示模式", 时间范围="未来三个月")
        print("  【演示模式】固定问事、时间与随机种子（可复现）。")
        起卦时间 = datetime(2026, 10, 27, 12, 0)
        经度 = None
        结果 = 起卦(seed=7)
    else:
        wq = 收集问事()
        起卦时间 = 询问时间()
        经度 = 询问真太阳时()
        print()
        结果 = 起卦确认()

    # 干支时间
    干支 = 构建干支时间(起卦时间, tz_hours=8.0, longitude=经度)

    # 排盘
    盘 = 排盘(结果, 干支)

    # 取用神
    用神 = 取用神(wq.类别)

    # 输出
    print(输出排盘(盘, wq.转为字典(), 用神))

    # 存档
    if not 不存档:
        保存结果(盘, wq, 用神, 存档目录)

    print("─" * 66)
    print("  排盘完成。愿你以此为参考，理性看待，顺势而为。")
    print("─" * 66)


def 保存结果(盘, wq, 用神, 存档目录: Optional[str] = None):
    """存档并打印保存结果；失败不中断主流程"""
    try:
        paths = 保存记录(盘, wq, 用神, 存档目录=存档目录)
    except Exception as e:      # noqa: BLE001
        print("\n  ⚠ 存档失败（不影响本次占卜结果）：")
        print(f"    {type(e).__name__}: {e}")
        return None

    print("\n" + "─" * 66)
    print("  【已存档】")
    print(f"    报告：{paths['文本']}")
    if paths.get("JSON"):
        print(f"    数据：{paths['JSON']}")
    print(f"    目录：{paths['目录']}")
    print("─" * 66)
    return paths


def 显示历史(存档目录: Optional[str] = None):
    """打印历史占卜记录"""
    records = 列出记录(存档目录)
    print(BANNER)
    if not records:
        print("  （暂无历史记录）\n")
        return
    print(f"  共 {len(records)} 条记录（按时间倒序）\n")
    print(f"  {'#':<4}{'起卦时间':<22}{'干支':<24}{'本卦':<6}{'变卦':<8}{'卦宫':<10}所问")
    print("  " + "─" * 88)
    for i, r in enumerate(records, 1):
        q = r["问题"] or ""
        if len(q) > 20:
            q = q[:20] + "…"
        print(f"  {i:<4}{r['公历']:<22}{r['干支']:<24}"
              f"{r['本卦']:<6}{r['变卦']:<8}"
              f"{r['卦宫'] + '宫' + r['世卦'] if r['卦宫'] else '':<10}{q}")
    print()
    idx = os.path.join(存档目录 or 默认存档目录, "index.md")
    print(f"  索引文件：{os.path.abspath(idx)}")
    print(f"  单条 JSON 可用 liuyao.record.读记录(\"文件名\") 读取\n")


def main(argv=None):
    _启用utf8()
    parser = argparse.ArgumentParser(
        description="六爻卜卦 · 铜钱起卦排盘（只排盘，不解卦）")
    parser.add_argument("--demo", action="store_true",
                        help="演示模式：固定时间与随机种子")
    parser.add_argument("--save-dir", dest="save_dir", default=None,
                        help="存档目录（默认：项目下「占卜记录」）")
    parser.add_argument("--no-save", dest="no_save", action="store_true",
                        help="本次占卜不存档")
    parser.add_argument("--history", action="store_true",
                        help="查看历史占卜记录后退出")
    args = parser.parse_args(argv)

    try:
        if args.history:
            显示历史(args.save_dir)
            return 0
        运行交互(demo=args.demo, 存档目录=args.save_dir,
                 不存档=args.no_save)
    except KeyboardInterrupt:
        print("\n  已取消。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

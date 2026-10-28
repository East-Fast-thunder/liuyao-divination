# -*- coding: utf-8 -*-
"""
liuyao/display.py
=================
显示层：把排盘结果渲染成传统六爻盘面文本。

不涉及解卦，只把「排盘数据」完整、清晰地展示出来。
"""

from __future__ import annotations

from typing import List, Optional

from .paipan import 卦盘, 爻盘
from .panduan import 用神信息, 判断要素, 六神含义, 综合旺衰
from .ganzhi import 地支五行

线宽 = 78


def 分隔(char: str = "─") -> str:
    return char * 线宽


def 居中(text: str, width: int = 线宽) -> str:
    # 中文字符按 2 宽计算
    disp = sum(2 if ord(c) > 127 else 1 for c in text)
    pad = max(0, width - disp)
    left = pad // 2
    return " " * left + text + " " * (pad - left)


def 标题(text: str) -> str:
    return "\n" + 分隔("═") + "\n" + 居中(text) + "\n" + 分隔("═")


def 小节(text: str) -> str:
    return "\n" + 分隔("─") + "\n" + f"【{text}】" + "\n" + 分隔("─")


# ---------------------------------------------------------------------------
# 单爻行渲染
# ---------------------------------------------------------------------------

def _爻行(y: 爻盘, 宽: int = 14) -> str:
    """
    生成一爻的传统显示行：
        六神   伏神   本卦爻象 世应  本卦干支  六亲  动  变卦爻象  变爻干支  变爻六亲
    """
    # 六神（2字）
    shen = y.六神

    # 伏神（若有）
    fu = "      "
    for f in getattr(y, "_fu", []):
        fu = f"伏 {f['干支']} {f['六亲']}"

    # 本爻
    yao_line = y.符号
    if y.动:
        move = "→"
    else:
        move = " "

    shiying = f"[{y.世应}]" if y.世应 else "[  ]"

    # 标记：空亡 / 月破
    marks = ""
    if y.空亡:
        marks += "空"
    if y.月破:
        marks += "破"

    # 本爻干支与六亲
    ben = f"{y.干支}{y.五行} {y.六亲}"
    if marks:
        ben += f"({marks})"

    # 变爻
    if y.动 and y.变爻:
        b = y.变爻
        bian = f"{b['干支']}{b['五行']} {b['六亲']}"
    else:
        bian = ""

    return f"{shen:<4}{fu:<12} {yao_line} {move} {shiying} {ben:<16}{bian}"


def 卦象图(盘: 卦盘) -> str:
    """
    输出传统六爻盘：上爻在上，初爻在下。
    """
    lines = []
    变名 = 盘.变卦 or "（静卦无变）"
    lines.append(f"  本卦：{盘.本卦}卦（{盘.上卦}上{盘.下卦}下）"
                 f"    变卦：{变名}")
    lines.append("")
    lines.append(f"  {'六神':<4}{'伏神':<12} {'爻象':<10}   {'本卦':<18}{'变卦'}")
    lines.append(分隔())

    # 伏神映射到爻位
    fu_map = {}
    for f in 盘.伏神列表:
        fu_map.setdefault(f["伏爻"], []).append(f)
    for y in 盘.六爻:
        y._fu = fu_map.get(y.序号, [])

    for y in reversed(盘.六爻):      # 上爻先显示
        lines.append(_爻行(y))
    lines.append(分隔())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 完整排盘输出
# ---------------------------------------------------------------------------

def 输出排盘(盘: 卦盘, 问事: Optional[dict] = None,
           用神: Optional[用神信息] = None) -> str:
    out: List[str] = []
    t = 盘.时间

    # ===== 标题 =====
    out.append(标题("六爻排盘 · 铜钱起卦"))

    # ===== 问事信息 =====
    if 问事:
        out.append(小节("问事"))
        for k, v in 问事.items():
            if v:
                out.append(f"  {k}：{v}")

    # ===== 起卦时间 =====
    out.append(小节("起卦时间（干支）"))
    out.append(f"  公历：{t.原始时间.strftime('%Y年%m月%d日 %H:%M')}"
               f"（UTC{t.时区:+.0f}）")
    if t.dt != t.原始时间:
        out.append(f"  真太阳时：{t.dt.strftime('%H:%M')}")
    out.append(f"  干支：{t.年月日时}")
    out.append(f"  月建：{t.月建}　日建：{t.日建}　"
               f"日干：{t.日干}　旬空：{t.旬空文本}")
    if t.节气:
        out.append(f"  节气：已过「{t.节气}」（月令按节气划分）")

    # 起卦过程
    out.append(小节("起卦过程（三枚铜钱，自下而上）"))
    for y in 盘.起卦.爻列表:
        dong = "★动爻" if y.动 else ""
        out.append(f"  第{ y.序号 }爻（{y.爻位名}）："
                   f"{y.传统掷法} = {y.数值} {y.象名} {dong}")
    out.append(f"  随机源：{盘.起卦.随机源}"
               + (f"（种子 {盘.起卦.种子}）" if 盘.起卦.种子 is not None else ""))

    # ===== 卦象 =====
    out.append(小节("卦象"))
    out.append(卦象图(盘))

    # ===== 卦体信息 =====
    out.append(小节("卦体"))
    out.append(f"  本卦：{盘.本卦}（{盘.上卦}上{盘.下卦}下）　"
               f"卦宫：{盘.宫}宫（{盘.卦五行}）　{盘.世卦}卦")
    out.append(f"  世爻：{盘.世.爻位名} {盘.世.干支} {盘.世.六亲}"
               f"　应爻：{盘.应.爻位名} {盘.应.干支} {盘.应.六亲}")
    if 盘.变卦:
        out.append(f"  变卦：{盘.变卦}（{盘.变上卦}上{盘.变下卦}下）")
    else:
        out.append("  变卦：无（静卦）")

    from .paipan import 卦象属性
    tags = 卦象属性(盘)
    if tags:
        out.append(f"  卦性：{'、'.join(tags)}")

    # ===== 六亲分布 =====
    out.append(小节("六亲与伏神"))
    from .paipan import 六亲名
    for q in 六亲名:
        lst = 盘.按六亲(q)
        if lst:
            detail = "、".join(f"{y.爻位名}{y.干支}"
                               f"{'动' if y.动 else ''}"
                               f"{'世' if y.世应 == '世' else ''}"
                               f"{'应' if y.世应 == '应' else ''}"
                               for y in lst)
            out.append(f"  {q}：{detail}")
        else:
            out.append(f"  {q}：不现")
    if 盘.伏神列表:
        out.append("  ── 伏神（本卦所缺六亲，取本宫八纯卦补）──")
        for f in 盘.伏神列表:
            位名 = ["初", "二", "三", "四", "五", "上"][f["伏爻"] - 1] + "爻"
            out.append(f"    伏于{位名}（飞神{f['飞神六亲']}{f['飞神干支']}）之下："
                       f"{f['干支']} {f['六亲']}（{f['五行']}）")

    # ===== 断卦要素 =====
    if 用神:
        要素 = 判断要素(盘, 用神)
        out.append(小节("断卦要素（仅陈列规则，不作最终论断）"))

        out.append("  ▸ 取用神")
        out.append(f"    问题类别：{用神.类别}　优先级：{' > '.join(用神.候选)}")
        for item in 要素["用神"]:
            if item.get("缺失"):
                伏 = [f for f in 盘.伏神列表 if f["六亲"] == item["候选"]]
                if 伏:
                    位名 = ["初", "二", "三", "四", "五", "上"][伏[0]["伏爻"] - 1] + "爻"
                    out.append(f"    {item['候选']}爻：卦中不现，伏于{位名}"
                               f"（伏神{伏[0]['干支']}{伏[0]['五行']}）")
                else:
                    out.append(f"    {item['候选']}爻：卦中不现（本宫八纯卦亦无对应伏神）")
                continue
            y = item["爻"]
            w = item["旺衰"]
            评级 = w.get("评级") or 综合旺衰(地支五行[盘.时间.月建],
                                          地支五行[盘.时间.日建], y.五行)["评级"]
            out.append(f"    {item['label']}：{y.爻位名} {y.干支}{y.五行}"
                       f" 月令{w['月令']} 日辰{w['日辰']}"
                       f" → {评级}"
                       + ("（空亡）" if y.空亡 else "")
                       + ("（月破）" if y.月破 else ""))
            if item["动变"]:
                for k, v in item["动变"].items():
                    out.append(f"      动变：{k} — {v}")

        out.append("  ▸ 世应关系")
        sy = 要素["世应"]
        out.append(f"    世：{sy['世']}")
        out.append(f"    应：{sy['应']}")
        out.append(f"    生克：{sy['生克']}"
                   + ("　六冲" if sy["六冲"] else "")
                   + ("　六合" if sy["六合"] else ""))
        out.append(f"    世爻旺衰：{要素['世衰']['评级']}"
                   f"（月{要素['世衰']['月令']} 日{要素['世衰']['日辰']}）")
        out.append(f"    应爻旺衰：{要素['应衰']['评级']}"
                   f"（月{要素['应衰']['月令']} 日{要素['应衰']['日辰']}）")

        out.append("  ▸ 动爻分析")
        if not 要素["动爻"]:
            out.append("    无动爻（静卦，以用神与日月生克为主）")
        for it in 要素["动爻"]:
            out.append(f"    {it['爻位']} {it['六亲']}{it['干支']} 动")
            if it["变爻"]:
                b = it["变爻"]
                out.append(f"      化 {b['干支']}{b['五行']} {b['六亲']}")
            for k, v in it["动变"].items():
                out.append(f"      {k}：{v}")
            out.append(f"      对本爻关系——对世：{it['对世']}")

        if 要素["冲合"]:
            out.append("  ▸ 冲合刑害")
            for s in 要素["冲合"]:
                out.append(f"    {s}")

        if 要素["三合"]:
            out.append("  ▸ 三合/半合（含月建日建）")
            for s in 要素["三合"]:
                out.append(f"    {s}")

        if 要素["空亡爻"]:
            out.append("  ▸ 空亡")
            out.append(f"    空亡爻：{'、'.join(要素['空亡爻'])}"
                       f"（日旬空：{t.旬空文本}）")
        else:
            out.append("  ▸ 空亡")
            out.append(f"    六爻无空亡（日旬空：{t.旬空文本}）")

        if 要素["月破爻"]:
            out.append("  ▸ 月破")
            out.append(f"    月破爻：{'、'.join(要素['月破爻'])}（月建：{t.月建}）")

        out.append("  ▸ 六神（辅助性质，不作主判）")
        for s in 要素["六神"]:
            out.append(f"    {s}")

    # ===== 免责说明 =====
    out.append(小节("说明"))
    out.append("  本程序只完成「起卦 + 排盘 + 列断卦要素」，不含卦辞解读与吉凶论断。")
    out.append("  六爻判断依赖具体问题、背景与时间范围，请结合自身情况理性参考。")
    out.append("")

    return "\n".join(out)


def 简化卦象(盘: 卦盘) -> str:
    """仅输出卦象图（用于快速查看）"""
    return 卦象图(盘)

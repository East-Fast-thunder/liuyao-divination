# -*- coding: utf-8 -*-
"""
liuyao/record.py
================
存档层：把每次占卜结果保存到文件

每次占卜保存两样东西：
1. <存档目录>/<时间戳>_<本卦>卦.txt   —— 完整可读的排盘报告（与屏幕输出一致）
2. <存档目录>/<时间戳>_<本卦>卦.json  —— 结构化记录（便于将来检索/统计/复现）
另在存档目录维护 index.md —— 全部占卜记录的总目录

设计要点：
- 归档不依赖解卦，只存「起卦过程 + 排盘数据 + 断卦要素」
- 文件名带毫秒时间戳 + 卦名，天然可排序、不会互相覆盖
- 同名冲突时自动追加序号，绝不覆盖旧记录
- 全程 try/except：存档失败只提示，不影响占卜主流程
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from .paipan import 卦盘, 六亲名, 卦象属性
from .panduan import 用神信息, 判断要素
from .wengua import 问事
from .display import 输出排盘

# 默认存档目录（相对项目根）
默认存档目录 = "占卜记录"


# ---------------------------------------------------------------------------
# 序列化：卦盘 → 结构化数据
# ---------------------------------------------------------------------------

def 盘转字典(盘: 卦盘, 问事信息: Optional[问事] = None,
          用神: Optional[用神信息] = None) -> Dict:
    """把一次完整占卜转成可 JSON 序列化的字典（也用于复现/统计）"""
    t = 盘.时间

    # 起卦过程
    起卦数据 = {
        "方式": 盘.起卦.方式,
        "随机源": 盘.起卦.随机源,
        "种子": 盘.起卦.种子,
        "有动爻": 盘.起卦.有动爻,
        "爻": [
            {
                "序号": y.序号,
                "爻位": y.爻位名,
                "数值": y.数值,
                "四象": y.象名,
                "阴阳": "阳" if y.阳 else "阴",
                "动": y.动,
                "传统掷法": y.传统掷法,
            }
            for y in 盘.起卦.爻列表
        ],
    }

    # 排盘六爻
    六爻数据 = []
    for y in 盘.六爻:
        item = {
            "爻位": y.爻位名,
            "阴阳": "阳" if y.阴阳 else "阴",
            "动": y.动,
            "干支": y.干支,
            "五行": y.五行,
            "六亲": y.六亲,
            "六神": y.六神,
            "世应": y.世应,
            "空亡": y.空亡,
            "月破": y.月破,
        }
        if y.变爻:
            item["变爻"] = {
                "干支": y.变爻["干支"],
                "五行": y.变爻["五行"],
                "六亲": y.变爻["六亲"],
            }
        六爻数据.append(item)

    data = {
        "存档版本": 1,
        "问事": 问事信息.转为字典() if 问事信息 else {},
        "起卦时间": {
            "公历": t.原始时间.strftime("%Y-%m-%d %H:%M:%S"),
            "时区": f"UTC{t.时区:+.0f}",
            "真太阳时": t.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "年柱": t.年柱,
            "月柱": t.月柱,
            "日柱": t.日柱,
            "时柱": t.时柱,
            "月建": t.月建,
            "日建": t.日建,
            "日干": t.日干,
            "旬空": t.旬空文本,
            "节气": t.节气,
        },
        "起卦": 起卦数据,
        "卦象": {
            "本卦": 盘.本卦,
            "上卦": 盘.上卦,
            "下卦": 盘.下卦,
            "变卦": 盘.变卦,
            "变上卦": 盘.变上卦,
            "变下卦": 盘.变下卦,
            "卦宫": 盘.宫,
            "卦五行": 盘.卦五行,
            "世卦": 盘.世卦,
            "世爻": 盘.世爻,
            "应爻": 盘.应爻,
            "卦性": 卦象属性(盘),
            "六爻": 六爻数据,
            "伏神": 盘.伏神列表,
        },
    }

    if 用神:
        data["用神"] = {
            "类别": 用神.类别,
            "主用神": 用神.主用神,
            "候选": 用神.候选,
        }
    return data


# ---------------------------------------------------------------------------
# 文件名与目录
# ---------------------------------------------------------------------------

def _安全文件名(s: str) -> str:
    """去掉文件系统非法字符"""
    for ch in '\\/:*?"<>|\r\n\t':
        s = s.replace(ch, "")
    return s.strip() or "未命名"


def 生成文件名基(盘: 卦盘) -> str:
    """时间戳 + 本卦，例如 20261027-231450-晋"""
    ts = 盘.时间.原始时间.strftime("%Y%m%d-%H%M%S")
    return _安全文件名(f"{ts}-{盘.本卦}卦")


def _不重名路径(目录: str, 基名: str, 后缀: str) -> str:
    """同名时追加 -2, -3 …，绝不覆盖旧文件"""
    path = os.path.join(目录, 基名 + 后缀)
    n = 2
    while os.path.exists(path):
        path = os.path.join(目录, f"{基名}-{n}{后缀}")
        n += 1
    return path


# ---------------------------------------------------------------------------
# 保存
# ---------------------------------------------------------------------------

def 保存记录(
    盘: 卦盘,
    问事信息: Optional[问事] = None,
    用神: Optional[用神信息] = None,
    存档目录: Optional[str] = None,
    只保存文本: bool = False,
) -> Dict[str, str]:
    """
    把一次占卜保存到文件。

    返回：{"文本": 路径, "JSON": 路径, "目录": 目录}
    出错时抛出异常，由调用方决定是否提示（调用方应 try/except，不中断主流程）。
    """
    目录 = 存档目录 or 默认存档目录
    os.makedirs(目录, exist_ok=True)

    基名 = 生成文件名基(盘)
    结果: Dict[str, str] = {"目录": os.path.abspath(目录)}

    # 1) 可读报告
    txt_path = _不重名路径(目录, 基名, ".txt")
    报告 = 输出排盘(盘, 问事信息.转为字典() if 问事信息 else None, 用神)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(报告)
    结果["文本"] = os.path.abspath(txt_path)

    # 2) 结构化记录
    if not 只保存文本:
        json_path = _不重名路径(目录, 基名, ".json")
        data = 盘转字典(盘, 问事信息, 用神)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        结果["JSON"] = os.path.abspath(json_path)

    # 3) 刷新索引
    try:
        刷新索引(目录)
    except Exception:
        pass

    return 结果


# ---------------------------------------------------------------------------
# 索引与历史
# ---------------------------------------------------------------------------

def 列出记录(存档目录: Optional[str] = None) -> List[Dict]:
    """扫描存档目录，返回按时间倒序的记录清单"""
    目录 = 存档目录 or 默认存档目录
    if not os.path.isdir(目录):
        return []

    records = []
    for name in os.listdir(目录):
        if not name.endswith(".json"):
            continue
        path = os.path.join(目录, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        t = data.get("起卦时间", {})
        g = data.get("卦象", {})
        wq = data.get("问事", {})
        records.append({
            "文件": name,
            "路径": os.path.abspath(path),
            "公历": t.get("公历", ""),
            "干支": " ".join(x for x in (
                t.get("年柱"), t.get("月柱"), t.get("日柱"), t.get("时柱")) if x),
            "本卦": g.get("本卦", ""),
            "变卦": g.get("变卦") or "（静卦）",
            "卦宫": g.get("卦宫", ""),
            "世卦": g.get("世卦", ""),
            "问题": wq.get("所问", ""),
            "类别": wq.get("类别", ""),
            "种子": data.get("起卦", {}).get("种子"),
        })
    # 按公历倒序（字符串时间可直接比较）
    records.sort(key=lambda r: r["公历"], reverse=True)
    return records


def 刷新索引(存档目录: Optional[str] = None) -> str:
    """重建 index.md 总目录"""
    目录 = 存档目录 or 默认存档目录
    os.makedirs(目录, exist_ok=True)
    records = 列出记录(目录)

    lines = [
        "# 六爻占卜记录 · 总目录",
        "",
        f"更新于：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}　共 {len(records)} 条",
        "",
    ]
    if records:
        lines += [
            "| # | 起卦时间 | 干支 | 本卦 | 变卦 | 卦宫 | 所问 | 文件 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(records, 1):
            q = (r["问题"] or "").replace("|", "\\|")
            if len(q) > 24:
                q = q[:24] + "…"
            link = r["文件"].replace("|", "\\|")
            lines.append(
                f"| {i} | {r['公历']} | {r['干支']} | {r['本卦']} | "
                f"{r['变卦']} | {r['卦宫']}宫{r['世卦']} | {q} | "
                f"[{link}]({link}) |"
            )
    else:
        lines.append("（暂无记录）")

    lines.append("")
    path = os.path.join(目录, "index.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return os.path.abspath(path)


def 读记录(文件名或路径: str, 存档目录: Optional[str] = None) -> Optional[Dict]:
    """读取一条 JSON 记录"""
    目录 = 存档目录 or 默认存档目录
    path = 文件名或路径
    if not os.path.isabs(path):
        path = os.path.join(目录, path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

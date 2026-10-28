# -*- coding: utf-8 -*-
"""
liuyao/divination.py
====================
起卦层：把随机数变成「四象六爻」

核心规则（三枚铜钱法）：
    掷三枚铜钱，每枚正面(阳面)记 3，反面(阴面)记 2：
        三正        3+3+3 = 9  → 老阳（阳爻，动，变阴）
        两正一反    3+3+2 = 8  → 少阴（阴爻，静）
        一正两反    3+2+2 = 7  → 少阳（阳爻，静）
        三反        2+2+2 = 6  → 老阴（阴爻，动，变阳）

    八种组合因三枚铜钱等价于无序选取而合并为四种结果，
    概率比 = 老阴:少阳:少阴:老阳 = 1:3:3:1

起卦顺序：
    自下而上，先起第一爻（初爻），再二、三、四、五、上爻，共掷六次。
    第 1 爻 = 初爻（最下），第 6 爻 = 上爻（最上）。

动爻：
    9（老阳）和 6（老阴）为动爻，动则生变。
变卦：
    动爻取反：老阳变阴、老阴变阳；静爻不变。
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence


# ---------------------------------------------------------------------------
# 四象定义
# ---------------------------------------------------------------------------

# 爻值 → (名称, 是否阳爻, 是否动爻, 变后阴阳)
四象 = {
    6: ("老阴", False, True, True),    # 老阴：阴爻动，变阳
    7: ("少阳", True, False, True),    # 少阳：阳爻静，不变
    8: ("少阴", False, False, False),  # 少阴：阴爻静，不变
    9: ("老阳", True, True, False),    # 老阳：阳爻动，变阴
}

爻值名 = {6: "老阴 ✕", 7: "少阳", 8: "少阴", 9: "老阳 ○"}

# 爻符号
爻符 = {
    (True, False): "───────",     # 阳爻静
    (False, False): "─── ───",    # 阴爻静
    (True, True): "───○───",      # 老阳动
    (False, True): "───✕───",     # 老阴动
}


@dataclass
class 爻:
    """单爻数据"""
    序号: int               # 1=初爻(最下) … 6=上爻(最上)
    数值: int               # 6/7/8/9
    传统掷法: str           # 例如 "两正一反"
    随机源: str             # "真随机" / "可复现种子"

    @property
    def 象名(self) -> str:
        return 四象[self.数值][0]

    @property
    def 阳(self) -> bool:
        return 四象[self.数值][1]

    @property
    def 动(self) -> bool:
        return 四象[self.数值][2]

    @property
    def 变阳(self) -> bool:
        return 四象[self.数值][3]

    @property
    def 符号(self) -> str:
        return 爻符[(self.阳, self.动)]

    @property
    def 描述(self) -> str:
        yin_yang = "阳" if self.阳 else "阴"
        dong = "动" if self.动 else "静"
        return f"{self.传统掷法} = {self.数值} {self.象名}（{yin_yang}爻·{dong}）"

    @property
    def 爻位名(self) -> str:
        return ["初", "二", "三", "四", "五", "上"][self.序号 - 1]


@dataclass
class 起卦结果:
    """完整起卦结果：本卦 + 动爻 + 变卦"""
    爻列表: List[爻]
    方式: str = "三枚铜钱"
    随机源: str = "真随机"
    种子: Optional[int] = None

    # ---- 本卦 / 变卦 阴阳序列（从下往上，True=阳）----
    @property
    def 本卦阴阳(self) -> List[bool]:
        return [y.阳 for y in self.爻列表]

    @property
    def 变卦阴阳(self) -> List[bool]:
        return [y.变阳 if y.动 else y.阳 for y in self.爻列表]

    @property
    def 动爻序号(self) -> List[int]:
        return [y.序号 for y in self.爻列表 if y.动]

    @property
    def 有动爻(self) -> bool:
        return bool(self.动爻序号)

    @property
    def 静卦(self) -> bool:
        return not self.有动爻


# ---------------------------------------------------------------------------
# 六十四卦查表
# ---------------------------------------------------------------------------

# 卦名（上坤下乾 = 上卦/下卦），键为 (上卦名, 下卦名)
卦名表 = {
    ("乾", "乾"): "乾", ("坤", "坤"): "坤",
    ("坎", "震"): "屯", ("艮", "坎"): "蒙",
    ("坎", "乾"): "需", ("乾", "坎"): "讼",
    ("坤", "坎"): "师", ("坎", "坤"): "比",
    ("巽", "乾"): "小畜", ("乾", "兑"): "履",
    ("坤", "乾"): "泰", ("乾", "坤"): "否",
    ("乾", "离"): "同人", ("离", "乾"): "大有",
    ("坤", "艮"): "谦", ("震", "坤"): "豫",
    ("兑", "震"): "随", ("艮", "巽"): "蛊",
    ("坤", "兑"): "临", ("巽", "坤"): "观",
    ("离", "震"): "噬嗑", ("艮", "离"): "贲",
    ("艮", "坤"): "剥", ("坤", "震"): "复",
    ("乾", "震"): "无妄", ("艮", "乾"): "大畜",
    ("艮", "震"): "颐", ("兑", "巽"): "大过",
    ("坎", "坎"): "坎", ("离", "离"): "离",
    ("兑", "艮"): "咸", ("震", "巽"): "恒",
    ("乾", "艮"): "遁", ("震", "乾"): "大壮",
    ("离", "坤"): "晋", ("坤", "离"): "明夷",
    ("巽", "离"): "家人", ("离", "兑"): "睽",
    ("坎", "艮"): "蹇", ("震", "坎"): "解",
    ("艮", "兑"): "损", ("巽", "震"): "益",
    ("兑", "乾"): "夬", ("乾", "巽"): "姤",
    ("兑", "坤"): "萃", ("坤", "巽"): "升",
    ("兑", "坎"): "困", ("坎", "巽"): "井",
    ("兑", "离"): "革", ("离", "巽"): "鼎",
    ("震", "震"): "震", ("艮", "艮"): "艮",
    ("巽", "艮"): "渐", ("震", "兑"): "归妹",
    ("震", "离"): "丰", ("离", "艮"): "旅",
    ("巽", "巽"): "巽", ("兑", "兑"): "兑",
    ("巽", "坎"): "涣", ("坎", "兑"): "节",
    ("巽", "兑"): "中孚", ("震", "艮"): "小过",
    ("坎", "离"): "既济", ("离", "坎"): "未济",
}

# 八经卦三爻（从下往上 True=阳）
八经卦 = {
    "乾": (True, True, True),
    "兑": (True, True, False),
    "离": (True, False, True),
    "震": (True, False, False),
    "巽": (False, True, True),
    "坎": (False, True, False),
    "艮": (False, False, True),
    "坤": (False, False, False),
}

# 反查
经卦由三爻 = {v: k for k, v in 八经卦.items()}

# 卦之宫位五行（八纯卦五行）
卦五行 = {
    "乾": "金", "兑": "金", "离": "火", "震": "木",
    "巽": "木", "坎": "水", "艮": "土", "坤": "土",
}


def 三爻成卦(bits) -> str:
    """三爻 → 经卦名（bits 从下往上）"""
    return 经卦由三爻[tuple(bits)]


def 六爻成卦(bits) -> tuple[str, str, str]:
    """六爻（从下往上）→ (上卦, 下卦, 卦名)"""
    lower = 三爻成卦(bits[:3])
    upper = 三爻成卦(bits[3:])
    return upper, lower, 卦名表[(upper, lower)]


def 卦序号(bits) -> int:
    """把六爻转成 0-63 的二进制序号（初爻为最低位）"""
    n = 0
    for i, b in enumerate(bits):
        if b:
            n |= (1 << i)
    return n


# ---------------------------------------------------------------------------
# 随机源：支持真随机 / 可复现种子
# ---------------------------------------------------------------------------

class 随机源:
    """
    随机源封装。

    - 默认：使用 secrets（真随机），每次起卦不可复现
    - seed：使用 random.Random(seed)，同一种子可复现同一卦
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self._rng = random.Random(seed) if seed is not None else None

    def 掷一枚(self) -> bool:
        """返回 True=正面(阳/3)，False=反面(阴/2)"""
        if self._rng is not None:
            return self._rng.random() < 0.5
        return secrets.randbits(1) == 1

    def 掷一爻(self) -> tuple[int, str]:
        """
        掷三枚铜钱一次，返回 (爻值, 传统掷法描述)
        硬币正面记 3、反面记 2，三枚求和。
        """
        coins = [self.掷一枚() for _ in range(3)]
        total = sum(3 if c else 2 for c in coins)
        heads = sum(1 for c in coins if c)
        desc = {3: "三正", 2: "两正一反", 1: "一正两反", 0: "三反"}[heads]
        return total, desc


# ---------------------------------------------------------------------------
# 起卦
# ---------------------------------------------------------------------------

def 起卦(seed: Optional[int] = None,
       手动输入: Optional[Sequence[int]] = None) -> 起卦结果:
    """
    执行一次完整起卦。

    参数：
        seed      随机种子（None = 真随机）
        手动输入  若给出，则为六个 6/7/8/9 组成的序列（从下往上），
                  用于「报数/手工摇卦」场景，跳过随机。

    返回：起卦结果（六爻 + 动爻 + 变卦推导）
    """
    src = 随机源(seed)

    if 手动输入 is not None:
        if len(手动输入) != 6:
            raise ValueError("手动输入必须恰好 6 个爻值")
        for v in 手动输入:
            if v not in (6, 7, 8, 9):
                raise ValueError(f"爻值必须是 6/7/8/9，收到 {v}")
        yao_list = [
            爻(序号=i + 1, 数值=v,
              传统掷法={9: "三正", 8: "两正一反", 7: "一正两反", 6: "三反"}[v],
              随机源="手动输入")
            for i, v in enumerate(手动输入)
        ]
        return 起卦结果(爻列表=yao_list, 方式="手工指定",
                    随机源="手动输入", 种子=None)

    yao_list = []
    for i in range(6):
        value, desc = src.掷一爻()
        yao_list.append(
            爻(序号=i + 1, 数值=value, 传统掷法=desc,
              随机源="可复现种子" if seed is not None else "真随机")
        )

    return 起卦结果(
        爻列表=yao_list,
        方式="三枚铜钱",
        随机源="可复现种子" if seed is not None else "真随机",
        种子=seed,
    )


def 报数起卦(数字: int) -> 起卦结果:
    """
    传统「报数起卦」：给一个数，按取模规则生成六爻。
    规则：数字逐位/递推取 6/7/8/9，从下往上。
    这是备选的次要起卦法，此处简单以数字本身作为种子。
    """
    return 起卦(seed=数字)

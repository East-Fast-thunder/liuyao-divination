# -*- coding: utf-8 -*-
"""
liuyao/ganzhi.py
================
干支历法模块（纯标准库实现，无第三方依赖）

负责把公历时间换算为六爻排盘所需的时间要素：

1. 年柱：以「立春」为界（六爻/八字传统，非公历元旦，也非农历正月初一）
2. 月柱：以「节气」为界（立春=寅月、惊蛰=卯月……小寒=丑月）
3. 日柱：连续计日，使用 1900-01-01 为甲戌日的锚点推算
4. 时柱：以「真太阳时/标准经度时」换算后，五鼠遁起时干
5. 旬空：按日柱所在旬确定空亡地支
6. 月建、日建：月柱地支、日柱地支

说明与精度：
- 节气使用天文近似（Meeus 太阳视黄经低精度算法），
  误差约在 ±2 分钟量级，对「日」级别的六爻判断足够；
  若出生/起卦时刻恰好卡在节气交接的几分钟内，可人工微调。
- 默认使用东八区（UTC+8, 经度 120°E）标准时间；
  「真太阳时」选项会按经度 + 均时差修正，用于极高精度场合。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# 基础常量
# ---------------------------------------------------------------------------

天干 = "甲乙丙丁戊己庚辛壬癸"
地支 = "子丑寅卯辰巳午未申酉戌亥"

# 天干五行
天干五行 = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

# 地支五行
地支五行 = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 地支阴阳（子寅辰午申戌为阳）
阳支 = set("子寅辰午申戌")

# 五行生克关系
五行 = ("木", "火", "土", "金", "水")
相生 = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}   # 生
相克 = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}   # 克

# 地支六冲
六冲 = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}

# 地支六合
六合 = {
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳", "午": "未", "未": "午",
}

# 三合局（半合亦据此判断）
三合局 = {
    "申子辰": "水",
    "亥卯未": "木",
    "寅午戌": "火",
    "巳酉丑": "金",
}

# 三刑：子卯刑（无礼之刑）、寅巳申（无恩之刑）、丑戌未（恃势之刑）、辰午酉亥自刑
三刑组 = [
    {"寅", "巳", "申"},
    {"丑", "戌", "未"},
    {"子", "卯"},
]
自刑 = set("辰午酉亥")

# 地支六害
六害 = {
    "子": "未", "未": "子", "丑": "午", "午": "丑",
    "寅": "巳", "巳": "寅", "卯": "辰", "辰": "卯",
    "申": "亥", "亥": "申", "酉": "戌", "戌": "酉",
}

# 五行生旺死绝（十二长生）—— 以「我」之五行为基准：
# 长生、沐浴、冠带、临官、帝旺、衰、病、死、墓、绝、胎、养
十二长生 = ("长生", "沐浴", "冠带", "临官", "帝旺",
            "衰", "病", "死", "墓", "绝", "胎", "养")

# 五行长生起点地支
五行长生起点 = {"木": "亥", "火": "寅", "金": "巳", "水": "申", "土": "申"}

# 阳顺阴逆——这里按五行本身阴阳：木火属阳顺行，金水属阴逆行，土随水行
五行阳顺 = {"木": True, "火": True, "土": False, "金": False, "水": False}

# 六神（按日干起）
六神序 = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")
六神起法 = {
    "甲": 0, "乙": 0,
    "丙": 1, "丁": 1,
    "戊": 2,
    "己": 3,
    "庚": 4, "辛": 4,
    "壬": 5, "癸": 5,
}


# ---------------------------------------------------------------------------
# 节气计算（太阳视黄经近似）
# ---------------------------------------------------------------------------

# 二十四节气在回归年内的近似「序数」（以春分=0 起的黄经度数对应）
节气名 = (
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
)

# 各节气对应太阳黄经（度）
节气黄经 = {
    "春分": 0, "清明": 15, "谷雨": 30, "立夏": 45, "小满": 60, "芒种": 75,
    "夏至": 90, "小暑": 105, "大暑": 120, "立秋": 135, "处暑": 150, "白露": 165,
    "秋分": 180, "寒露": 195, "霜降": 210, "立冬": 225, "小雪": 240, "大雪": 255,
    "冬至": 270, "小寒": 285, "大寒": 300, "立春": 315, "雨水": 330, "惊蛰": 345,
}

# 十二节（真正影响月令的节气），从立春起对应寅月
十二节 = ("立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
          "立秋", "白露", "寒露", "立冬", "大雪", "小寒")
# 十二节对应月份地支
节令月支 = ("寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")


def _julian_day(dt: datetime) -> float:
    """公历 UTC 时间 → 儒略日"""
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_apparent_longitude(jd: float) -> float:
    """太阳视黄经（度），Meeus 低精度公式"""
    t = (jd - 2451545.0) / 36525.0
    # 几何平黄经
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t
    # 平近点角
    m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t
    m_rad = math.radians(m)
    # 中心差
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(m_rad)
         + (0.019993 - 0.000101 * t) * math.sin(2 * m_rad)
         + 0.000289 * math.sin(3 * m_rad))
    true_long = l0 + c
    # 章动与光行差修正（简化）
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    return app_long % 360


def 节气时刻(year: int, term: str, tz_hours: float = 8.0) -> datetime:
    """
    计算某年某节气的时刻（返回指定时区的 datetime）。
    做法：以目标黄经为基准做牛顿式迭代求根。
    """
    target = 节气黄经[term]
    # 初值：春分约 3/20，每年节气相对固定
    approx_day = {
        "小寒": (1, 6), "大寒": (1, 20), "立春": (2, 4), "雨水": (2, 19),
        "惊蛰": (3, 5), "春分": (3, 20), "清明": (4, 5), "谷雨": (4, 20),
        "立夏": (5, 5), "小满": (5, 21), "芒种": (6, 5), "夏至": (6, 21),
        "小暑": (7, 7), "大暑": (7, 23), "立秋": (8, 7), "处暑": (8, 23),
        "白露": (9, 7), "秋分": (9, 23), "寒露": (10, 8), "霜降": (10, 23),
        "立冬": (11, 7), "小雪": (11, 22), "大雪": (12, 7), "冬至": (12, 22),
    }
    mo, dy = approx_day[term]
    guess = datetime(year, mo, dy, 12, 0, tzinfo=timezone(timedelta(hours=tz_hours)))
    jd = _julian_day(guess.astimezone(timezone.utc))
    for _ in range(30):
        lon = _sun_apparent_longitude(jd)
        diff = (target - lon + 180) % 360 - 180
        if abs(diff) < 1e-7:
            break
        # 太阳每天走约 0.9856 度
        jd += diff / 0.98564736
    # 儒略日 → datetime（UTC）
    unix_sec = (jd - 2440587.5) * 86400.0
    utc_dt = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=unix_sec)
    return utc_dt.astimezone(timezone(timedelta(hours=tz_hours)))


# ---------------------------------------------------------------------------
# 四柱（干支）计算
# ---------------------------------------------------------------------------

def _ganzhi(index: int) -> str:
    """按六十甲子序号取干支（0=甲子）"""
    return 天干[index % 10] + 地支[index % 12]


def 日柱(dt: datetime) -> str:
    """
    日柱：以 1900-01-01 为甲戌日（六十甲子序号 10）为锚点。
    以「日」为单位，按当地日历日期计算（子初换日按 23:00 后算次日）。
    """
    # 子时跨日处理：23:00 及以后按次日日柱
    day_dt = dt
    if dt.hour >= 23:
        day_dt = dt + timedelta(days=1)
    base = datetime(1900, 1, 1, tzinfo=day_dt.tzinfo)
    delta = (day_dt.date() - base.date()).days
    idx = (10 + delta) % 60
    return _ganzhi(idx)


def 时柱(dt: datetime, day_gan: str) -> str:
    """
    时柱：两小时一个时辰，五鼠遁起时干。
    子时 23:00-00:59 → 时辰地支「子」
    五鼠遁：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途
    """
    h = dt.hour
    # 23 点算次日早子时，但地支仍是子
    branch_idx = ((h + 1) // 2) % 12
    branch = 地支[branch_idx]
    # 五鼠遁系数
    day_gan_idx = 天干.index(day_gan)
    # 甲(0)/己(5) → 子时干=甲(0)；乙(1)/庚(6)→丙(2)；丙(2)/辛(7)→戊(4)；丁(3)/壬(8)→庚(6)；戊(4)/癸(9)→壬(8)
    base = {0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8}[day_gan_idx]
    gan = 天干[(base + branch_idx) % 10]
    return gan + branch


def _month_branch(dt: datetime, tz_hours: float) -> str:
    """按节气判断当前所处的月令地支"""
    # 找到 dt 之前最近的「节」
    best = None
    for year in (dt.year - 1, dt.year, dt.year + 1):
        for i, term in enumerate(十二节):
            t = 节气时刻(year, term, tz_hours)
            if t <= dt and (best is None or t > best[0]):
                best = (t, 节令月支[i])
    return best[1]


def 月柱(dt: datetime, year_gan: str, month_branch: str) -> str:
    """
    月柱：五虎遁起月干。
    甲己之年丙作首，乙庚之岁戊为头，丙辛必定寻庚起，丁壬壬位顺行流，戊癸何方发，甲寅之上好追求。
    即：年干对应寅月天干，之后顺推。
    """
    tigher_base = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
                   "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}
    base_gan = tigher_base[year_gan]
    offset = (地支.index(month_branch) - 地支.index("寅")) % 12
    gan = 天干[(天干.index(base_gan) + offset) % 10]
    return gan + month_branch


def 年柱(dt: datetime, tz_hours: float) -> str:
    """年柱：以立春为界"""
    lichun = 节气时刻(dt.year, "立春", tz_hours)
    solar_year = dt.year if dt >= lichun else dt.year - 1
    # 公元 4 年为甲子年（序 0）
    idx = (solar_year - 4) % 60
    return _ganzhi(idx)


def 旬空(day_ganzhi: str) -> tuple[str, str]:
    """日柱 → 旬空两个地支"""
    g = 天干.index(day_ganzhi[0])
    z = 地支.index(day_ganzhi[1])
    # 旬首序号
    xun_start = (z - g) % 12
    # 空亡为旬首前两个地支
    k1 = 地支[(xun_start - 2) % 12]
    k2 = 地支[(xun_start - 1) % 12]
    return k1, k2


# ---------------------------------------------------------------------------
# 时间上下文数据类
# ---------------------------------------------------------------------------

@dataclass
class 干支时间:
    dt: datetime               # 起卦时间（已按需校正）
    原始时间: datetime
    年柱: str
    月柱: str
    日柱: str
    时柱: str
    月建: str                  # 月令地支
    日建: str                  # 日辰地支
    空亡: tuple[str, str]
    时区: float
    节气: Optional[str]        # 当前所处节气（最近已过之节）

    @property
    def 日干(self) -> str:
        return self.日柱[0]

    @property
    def 日支(self) -> str:
        return self.日柱[1]

    @property
    def 月支(self) -> str:
        return self.月柱[1]

    @property
    def 年月日时(self) -> str:
        return f"{self.年柱}年 {self.月柱}月 {self.日柱}日 {self.时柱}时"

    @property
    def 旬空文本(self) -> str:
        return f"{self.空亡[0]}{self.空亡[1]}"


def 真太阳时(dt: datetime, longitude: float, tz_hours: float = 8.0) -> datetime:
    """标准时 → 真太阳时（经度差 + 均时差近似）"""
    # 经度修正：每 1 度 = 4 分钟
    lon_corr = (longitude - tz_hours * 15.0) * 4.0
    # 均时差（简化，单位分钟）
    n = dt.timetuple().tm_yday
    b = math.radians(360.0 * (n - 81) / 364.0)
    eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    return dt + timedelta(minutes=lon_corr + eot)


def 构建干支时间(
    dt: datetime,
    tz_hours: float = 8.0,
    longitude: Optional[float] = None,
) -> 干支时间:
    """
    公历时间 → 完整干支时间上下文。

    参数：
        dt         起卦的公历时间（naive 视为当地时区时间）
        tz_hours   时区偏移（默认东八区）
        longitude  若给出则换算真太阳时再排盘
    """
    tz = timezone(timedelta(hours=tz_hours))
    if dt.tzinfo is None:
        local = dt.replace(tzinfo=tz)
    else:
        local = dt.astimezone(tz)

    原始 = local
    work = local
    if longitude is not None:
        work = 真太阳时(local, longitude, tz_hours)

    yz = 年柱(work, tz_hours)
    mb = _month_branch(work, tz_hours)
    mz = 月柱(work, yz[0], mb)
    dz = 日柱(work)
    hz = 时柱(work, dz[0])
    kong = 旬空(dz)

    # 当前节气
    cur_term = None
    for year in (work.year - 1, work.year, work.year + 1):
        for term in 节气名:
            t = 节气时刻(year, term, tz_hours)
            if t <= work and (cur_term is None or t > cur_term[0]):
                cur_term = (t, term)

    return 干支时间(
        dt=work,
        原始时间=原始,
        年柱=yz,
        月柱=mz,
        日柱=dz,
        时柱=hz,
        月建=mb,
        日建=dz[1],
        空亡=kong,
        时区=tz_hours,
        节气=cur_term[1] if cur_term else None,
    )


if __name__ == "__main__":
    now = datetime.now()
    gz = 构建干支时间(now)
    print("测试：", gz.年月日时, "空亡:", gz.旬空文本, "节气:", gz.节气)

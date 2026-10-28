# -*- coding: utf-8 -*-
"""
liuyao/__init__.py
==================
六爻卜卦（排盘版）—— 仅起卦与排盘，不作解卦

用法：
    from liuyao import 起卦, 排盘, 构建干支时间, 输出排盘
"""

from .ganzhi import 构建干支时间, 干支时间, 干支时间 as 时间上下文
from .divination import 起卦, 起卦结果, 爻, 六爻成卦, 卦名表
from .paipan import 排盘, 卦盘, 爻盘, 查卦宫
from .panduan import 取用神, 用神信息, 判断要素
from .wengua import 问事, 问题类别列表
from .display import 输出排盘, 卦象图
from .record import 保存记录, 列出记录, 读记录, 刷新索引, 盘转字典

__all__ = [
    "构建干支时间", "干支时间", "时间上下文",
    "起卦", "起卦结果", "爻", "六爻成卦", "卦名表",
    "排盘", "卦盘", "爻盘", "查卦宫",
    "取用神", "用神信息", "判断要素",
    "问事", "问题类别列表",
    "输出排盘", "卦象图",
    "保存记录", "列出记录", "读记录", "刷新索引", "盘转字典",
]

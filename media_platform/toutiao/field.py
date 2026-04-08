# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条枚举定义
"""

from enum import Enum


class SearchOrderType(Enum):
    """搜索排序类型"""
    DEFAULT = "default"      # 综合排序
    NEWEST = "newest"        # 最新优先
    HOT = "hot"              # 热度优先


class CommentOrderType(Enum):
    """评论排序类型"""
    DEFAULT = "0"            # 默认排序
    TIME = "1"               # 时间排序
    HOT = "2"                # 热度排序

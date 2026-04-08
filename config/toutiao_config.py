# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 今日头条平台配置

# 搜索排序类型
# default - 综合排序
# newest - 最新优先
# hot - 热度优先
TOUTIAO_SEARCH_ORDER = "default"

# 是否获取文章详情（全文内容）
# True  - 会访问每篇文章详情页，获取完整内容、互动数据（点赞/评论/分享数）
# False - 只获取搜索结果中的摘要信息（更快，适合大量文章抓取）
ENABLE_FETCH_ARTICLE_DETAIL = True

# 指定文章ID列表（用于 detail 模式）
TOUTIAO_SPECIFIED_ID_LIST = [
    # 示例: "7623725527030940166",
]

# 指定创作者ID列表（用于 creator 模式）
TOUTIAO_CREATOR_ID_LIST = [
    # 示例: "123456789",
]

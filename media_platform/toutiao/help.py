# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条工具函数
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import NamedTuple


class ArticleInfo(NamedTuple):
    """文章信息"""
    article_id: str
    title: str = ""


class CreatorInfo(NamedTuple):
    """创作者信息"""
    creator_id: str
    name: str = ""


def parse_article_id_from_url(url: str) -> str:
    """
    从文章URL解析文章ID
    示例:
        https://www.toutiao.com/article/7623725527030940166/
        https://www.toutiao.com/a7623725527030940166/
    :param url: 文章URL
    :return: 文章ID
    """
    # 匹配 /article/7623725527030940166 格式
    pattern1 = r'/article/(\d+)'
    match = re.search(pattern1, url)
    if match:
        return match.group(1)

    # 匹配 /a7623725527030940166 格式
    pattern2 = r'/a(\d+)'
    match = re.search(pattern2, url)
    if match:
        return match.group(1)

    raise ValueError(f"无法从URL解析文章ID: {url}")


def parse_creator_id_from_url(url: str) -> str:
    """
    从创作者主页URL解析创作者ID
    示例:
        https://www.toutiao.com/c/user/token/xxx/
        https://www.toutiao.com/c/user/123456/
    :param url: 创作者主页URL
    :return: 创作者ID
    """
    # 匹配 /c/user/xxx 格式
    pattern = r'/c/user/(\w+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    raise ValueError(f"无法从URL解析创作者ID: {url}")


def extract_group_id_from_url(url: str) -> str:
    """
    从URL中提取group_id（用于评论接口）
    :param url: 文章或视频URL
    :return: group_id
    """
    return parse_article_id_from_url(url)


def clean_html_content(html: str) -> str:
    """
    清理HTML内容，提取纯文本
    :param html: HTML内容
    :return: 纯文本
    """
    # 移除script和style标签
    text = re.sub(r'<(script|style)[^>]*>[^<]*</\1>', '', html, flags=re.IGNORECASE)
    # 移除其他HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 替换HTML实体
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    # 清理多余空白
    text = ' '.join(text.split())
    return text.strip()


def extract_content_text_from_html(html: str) -> str:
    """
    从文章详情HTML中提取纯文本内容
    只提取文章内容部分，不包含标题、来源、标签等
    :param html: HTML内容
    :return: 纯文本内容
    """
    if not html:
        return ""

    # 移除script、style、header、footer等标签
    text = re.sub(r'<(script|style|header|footer|nav|aside)[^>]*>[^<]*</\1>', '', html, flags=re.IGNORECASE)

    # 移除标题标签（通常是文章标题，不是正文内容）
    text = re.sub(r'<h[1-6][^>]*>[^<]*</h[1-6]>', '', text, flags=re.IGNORECASE)

    # 移除 article-meta 区域（包含时间、来源、作者）
    text = re.sub(r'<div[^>]*class="article-meta".*?</div>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # 移除特定的标签内容
    text = re.sub(r'<div[^>]*class="[^"]*tag[^"]*"[^>]*>.*?</div>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<div[^>]*class="[^"]*source[^"]*"[^>]*>.*?</div>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<div[^>]*class="[^"]*author[^"]*"[^>]*>.*?</div>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # 移除所有HTML标签
    text = re.sub(r'<[^>]+>', '', text)

    # 替换HTML实体
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = text.replace('&mdash;', '—').replace('&ndash;', '–')
    text = text.replace('&hellip;', '…').replace('&middot;', '·')

    # 清理多余空白
    text = ' '.join(text.split())
    return text.strip()


def extract_create_time_from_html(html: str) -> str:
    """
    从文章详情HTML中提取创建时间
    匹配 <div class="article-meta"><span>2025-03-15 18:00</span> 格式
    :param html: HTML内容
    :return: 创建时间字符串，如 "2025-03-15 18:00"
    """
    if not html:
        return ""

    # 匹配 article-meta 中的时间 span
    time_patterns = [
        # 匹配 <div class="article-meta"><span>2025-03-15 18:00</span>
        r'<div[^>]*class="article-meta"[^>]*>.*?<span[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</span>',
        # 匹配其他常见时间格式
        r'<span[^>]*class="[^"]*time[^"]*"[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</span>',
        r'<time[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</time>',
        r'<span[^>]*>(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})</span>.*?<span[^>]*class="dot"',
    ]

    for pattern in time_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return ""


def format_timestamp(timestamp: int) -> str:
    """
    格式化时间戳为可读日期
    :param timestamp: 时间戳（秒）
    :return: 格式化日期字符串
    """
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def calculate_hot_score(read_count: int, like_count: int, comment_count: int, share_count: int = 0) -> int:
    """
    计算热度分数
    :param read_count: 阅读数
    :param like_count: 点赞数
    :param comment_count: 评论数
    :param share_count: 分享数
    :return: 热度分数
    """
    # 简单算法：阅读*0.1 + 点赞*2 + 评论*5 + 分享*10
    score = int(read_count * 0.1) + (like_count * 2) + (comment_count * 5) + (share_count * 10)
    return score


def parse_search_keyword_from_url(url: str) -> str:
    """
    从搜索URL解析关键词
    示例:
        https://so.toutiao.com/search?keyword=AI新闻
    :param url: 搜索URL
    :return: 关键词
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    keyword = params.get('keyword', [''])[0]
    return keyword

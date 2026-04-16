# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# MCP Server for MediaCrawler
# 提供社交媒体平台数据爬取服务的 MCP 服务器
# 支持平台：小红书、抖音、快手、B站、微博、贴吧、知乎

import json
import os
import re
from datetime import datetime
import asyncio
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# 加载环境变量（从 .env 文件）
from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
from mcp_core.mcp_adapter import run_crawl_sync

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"

# 平台名称映射
PLATFORM_NAMES = {
    'xhs': '小红书',
    'dy': '抖音',
    'ks': '快手',
    'bili': 'B站',
    'wb': '微博',
    'tieba': '百度贴吧',
    'zhihu': '知乎',
    'toutiao': '今日头条'
}


# =========================
# 枚举类型定义
# =========================

class Platform(str, Enum):
    """支持的平台枚举"""
    XHS = "xhs"           # 小红书
    DY = "dy"             # 抖音
    KS = "ks"             # 快手
    BILI = "bili"         # B站
    WB = "wb"             # 微博
    TIEBA = "tieba"       # 百度贴吧
    ZHIHU = "zhihu"       # 知乎
    TOUTIAO = "toutiao"   # 今日头条


class CrawlerType(str, Enum):
    """爬取类型枚举"""
    SEARCH = "search"     # 关键词搜索
    DETAIL = "detail"     # 指定ID详情
    CREATOR = "creator"   # 创作者主页


class ReportType(str, Enum):
    """报告类型枚举"""
    SENTIMENT = "sentiment"      # 舆情分析报告
    TREND = "trend"              # 热门趋势报告
    COMPARISON = "comparison"    # 竞品对比报告


# =========================
# 数据模型
# =========================

@dataclass
class CrawlResult:
    """爬取结果数据模型"""
    platform: str
    crawler_type: str
    keywords: str
    is_get_comments: bool
    is_get_sub_comments: bool
    max_comments_count: int
    save_data_option: str
    count: int
    items: List[Dict[str, Any]]
    status: str = "success"
    message: Optional[str] = None


# =========================
# FastMCP 服务器实例
# =========================

mcp = FastMCP("mediacrawlermcp")


# =========================
# 平台数据处理器
# =========================

def process_xhs_data(data: List[Dict]) -> List[Dict]:
    """
    处理小红书数据

    数据结构特点:
    - note_id: 帖子ID
    - title: 标题
    - author/user: 作者信息
    - interact_info: 互动数据（点赞、收藏、评论数）
    - desc: 正文描述
    - comments: 评论列表，包含 sub_comments 子评论
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论
            sub_comment_list = []
            sub_comments = comment.get("sub_comments") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    "create_time": sub_comment.get("create_time", ""),
                    "like_count": sub_comment.get("like_count", 0),
                    "sub_comment_nickname": sub_comment.get("user_info", {}).get("nickname", "")
                })

            comment_list.append({
                "content": comment.get("content", ""),
                "sub_comment_count": comment.get("sub_comment_count", 0),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user_info", {}).get("nickname", ""),
                "sub_comment_list": sub_comment_list
            })

        # 获取作者昵称（兼容不同字段路径）
        author_nickname = ""
        if post.get("author"):
            author_nickname = post["author"].get("nickname", "")
        elif post.get("user"):
            author_nickname = post["user"].get("nickname", "")

        items.append({
            "note_id": post.get("note_id", ""),
            "title": post.get("title", ""),
            "nickname": author_nickname,
            "interact_info": post.get("interact_info", {}),
            "desc": post.get("desc", ""),
            "comments": comment_list
        })

    return items


def process_bili_data(data: List[Dict]) -> List[Dict]:
    """
    处理B站数据

    数据结构特点:
    - View: 视频基本信息（aid, title, desc, owner等）
    - Card: 卡片信息
    - stat: 统计数据（点赞、投币、收藏、分享等）
    - comments: 评论列表，包含 replies 子回复
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        view = post.get("View", {})
        name = post.get("Card", {}).get("card", {}).get("name", "")
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论（B站使用 replies）
            sub_comment_list = []
            replies = comment.get("replies") or []
            for sub_comment in replies:
                raw_content = sub_comment.get("content", {})
                # content 可能是字典或字符串
                if isinstance(raw_content, dict):
                    content_str = raw_content.get("message", "")
                elif isinstance(raw_content, str):
                    content_str = raw_content
                else:
                    content_str = ""

                sub_comment_list.append({
                    "content": content_str,
                    "create_time": sub_comment.get("ctime", ""),
                    "like_count": sub_comment.get("like", 0),
                    "sub_comment_nickname": sub_comment.get("member", {}).get("uname", "")
                })

            raw_content = comment.get("content", {})
            # content 可能是字典或字符串
            if isinstance(raw_content, dict):
                comment_content = raw_content.get("message", "")
            elif isinstance(raw_content, str):
                comment_content = raw_content
            else:
                comment_content = ""

            comment_list.append({
                "content": comment_content,
                "sub_comment_count": comment.get("rcount", 0),
                "like_count": comment.get("like", 0),
                "comment_nickname": comment.get("member", {}).get("uname", ""),
                "sub_comment_list": sub_comment_list
            })

        # 获取作者名称（优先使用owner.name，其次使用Card中的name）
        owner_name = view.get("owner", {}).get("name", "") or name

        items.append({
            "aid": view.get("aid", ""),
            "bvid": view.get("bvid", ""),
            "title": view.get("title", ""),
            "nickname": owner_name,
            "interact_info": view.get("stat", {}),
            "desc": view.get("desc", ""),
            "comments": comment_list
        })

    return items


def process_dy_data(data: List[Dict]) -> List[Dict]:
    """
    处理抖音数据

    数据结构特点:
    - aweme_id: 视频ID
    - create_time: 创建时间
    - author: 作者信息
    - statistics: 统计数据
    - desc: 视频描述
    - comments: 评论列表，包含 reply_comment 子评论
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论（抖音使用 reply_comment）
            sub_comment_list = []
            sub_comments = comment.get("reply_comment") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("text", ""),
                    "create_time": sub_comment.get("create_time", ""),
                    "like_count": sub_comment.get("digg_count", 0),
                    "sub_comment_nickname": sub_comment.get("user", {}).get("nickname", ""),
                    "reply_comment": sub_comment.get("reply_comment", 0),
                    "digg_count": sub_comment.get("digg_count", 0),
                    "user_digged": sub_comment.get("user_digged", 0),
                    "is_note_comment": sub_comment.get("is_note_comment", 0)
                })

            comment_list.append({
                "content": comment.get("text", ""),
                "create_time": comment.get("create_time", ""),
                "item_comment_total": comment.get("item_comment_total", 0),
                "reply_comment_total": comment.get("reply_comment_total", 0),
                "like_count": comment.get("digg_count", 0),
                "comment_nickname": comment.get("user", {}).get("nickname", ""),
                "digg_count": comment.get("digg_count", 0),
                "user_digged": comment.get("user_digged", 0),
                "is_note_comment": comment.get("is_note_comment", 0),
                "sub_comment_list": sub_comment_list
            })

        items.append({
            "create_time": post.get("create_time", ""),
            "aweme_id": post.get("aweme_id", ""),
            "nickname": post.get("author", {}).get("nickname", ""),
            "interact_info": post.get("statistics", {}),
            "desc": post.get("desc", ""),
            "comments": comment_list
        })

    return items


def strip_html(text: str) -> str:
    """去除HTML标签，保留纯文本内容。如 <a href='...'>@用户</a> → @用户，<img alt='[666]'/> → [666]"""
    if not text:
        return text
    # 将 <img> 标签替换为其 alt 属性值（表情符号）
    text = re.sub(r'<img\s+alt=["\']([^"\']*)["\'][^>]*/?\s*>', r'\1', text)
    # 去除所有其他 HTML 标签，保留内部文本
    text = re.sub(r'<[^>]+>', '', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def process_wb_data(data: List[Dict]) -> List[Dict]:
    """
    处理微博数据

    数据结构特点:
    - mblog: 微博正文数据
    - comments: 评论列表
    - user: 用户信息
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        mblog = post.get("mblog", {})
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论
            sub_comment_list = []
            sub_comments = comment.get("comments") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": strip_html(sub_comment.get("text", "")),
                    "create_time": sub_comment.get("created_at", ""),
                    "sub_comment_nickname": sub_comment.get("user", {}).get("screen_name", "")
                })

            comment_list.append({
                "created_at": comment.get("created_at", ""),
                "content": strip_html(comment.get("text", "")),
                "sub_comment_count": len(sub_comment_list),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user", {}).get("screen_name", ""),
                "sub_comment_list": sub_comment_list
            })

        # 构建互动信息
        interact_info = {
            "reposts_count": mblog.get("reposts_count", 0),
            "comments_count": mblog.get("comments_count", 0),
            "attitudes_count": mblog.get("attitudes_count", 0),
            "fans": mblog.get("fans", 0)
        }

        items.append({
            "created_at": mblog.get("created_at", ""),
            "note_id": mblog.get("id", ""),
            "nickname": mblog.get("user", {}).get("screen_name", ""),
            "interact_info": interact_info,
            "desc": strip_html(mblog.get("text", "")),
            "comments": comment_list
        })

    return items


def process_zhihu_data(data: List[Dict]) -> List[Dict]:
    """
    处理知乎数据

    数据结构特点:
    - content_id: 内容ID
    - title: 标题
    - user_nickname: 用户昵称
    - voteup_count: 赞同数
    - comment_count: 评论数
    - comments: 评论列表
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论
            sub_comment_list = []
            sub_comments = comment.get("sub_comment_list") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    "sub_comment_nickname": sub_comment.get("user_nickname", ""),
                    "like_count": sub_comment.get("like_count", 0)
                })

            comment_list.append({
                "comment_id": comment.get("comment_id", ""),
                "parent_comment_id": comment.get("parent_comment_id", ""),
                "content": comment.get("content", ""),
                "sub_comment_count": comment.get("sub_comment_count", 0),
                "like_count": comment.get("like_count", 0),
                "user_nickname": comment.get("user_nickname", ""),
                "sub_comment_list": sub_comment_list
            })

        interact_info = {
            "voteup_count": post.get("voteup_count", 0),
            "comment_count": post.get("comment_count", 0)
        }

        items.append({
            "note_id": post.get("content_id", ""),
            "title": post.get("title", ""),
            "nickname": post.get("user_nickname", ""),
            "interact_info": interact_info,
            "desc": post.get("desc", ""),
            "content_text": post.get("content_text", ""),
            "comments": comment_list
        })

    return items


def process_tieba_data(data: List[Dict]) -> List[Dict]:
    """
    处理百度贴吧数据

    数据结构特点:
    - note_id: 帖子ID
    - title: 标题
    - user_nickname: 用户昵称
    - total_replay_num: 回复数
    - like_count: 点赞数
    - comments: 评论列表
    """
    if not data:
        return []

    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论
            sub_comment_list = []
            sub_comments = comment.get("sub_comment_list") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    "sub_comment_nickname": sub_comment.get("user_nickname", ""),
                    "like_count": sub_comment.get("like_count", 0),
                    "ip_location": sub_comment.get("ip_location", "")
                })

            comment_list.append({
                "content": comment.get("content", ""),
                "parent_comment_id": comment.get("parent_comment_id", ""),
                "comment_id": comment.get("comment_id", ""),
                "sub_comment_count": comment.get("sub_comment_count", 0),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user_nickname", ""),
                "ip_location": comment.get("ip_location", ""),
                "sub_comment_list": sub_comment_list
            })

        interact_info = {
            "total_replay_num": post.get("total_replay_num", 0),
            "like_count": post.get("like_count", 0),
            "collect_count": post.get("collect_count", 0),
            "total_replay_page": post.get("total_replay_page", 0),
            "ip_location": post.get("ip_location", "")
        }

        items.append({
            "note_id": post.get("note_id", ""),
            "title": post.get("title", ""),
            "nickname": post.get("user_nickname", ""),
            "interact_info": interact_info,
            "desc": post.get("desc", ""),
            "comments": comment_list
        })

    return items


def process_ks_data(data: List[Dict]) -> List[Dict]:
    """
    处理快手数据

    数据结构特点:
    - photo: 视频信息（可能是字典或列表）
    - author: 作者信息
    - comments: 评论列表
    """
    if not data:
        return []

    items = []
    for post in data:
        # photo 可能是字典或列表，统一处理为字典
        photo = post.get("photo", {})
        if isinstance(photo, list):
            photo = photo[0] if photo else {}
        if not isinstance(photo, dict):
            photo = {}

        comments = post.get("comments") or []

        # 处理评论，提取子评论
        comment_list = []
        for comment in comments:
            sub_comment_list = []
            sub_comments = comment.get("subCommentsV2") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    # V2 REST API: author_name (flat), GraphQL: author.name (nested)
                    "sub_comment_nickname": sub_comment.get("author_name") or sub_comment.get("authorName") or sub_comment.get("author", {}).get("name", ""),
                    "like_count": sub_comment.get("likeCount", 0)
                })

            comment_list.append({
                "content": comment.get("content", ""),
                # V2 REST API: author_name (flat), GraphQL: author.name (nested)
                "comment_nickname": comment.get("author_name") or comment.get("authorName") or comment.get("author", {}).get("name", ""),
                "like_count": comment.get("likeCount", 0),
                "sub_comment_count": len(sub_comment_list),
                "sub_comment_list": sub_comment_list
            })

        interact_info = {
            "likeCount": photo.get("likeCount", 0),
            "viewCount": photo.get("viewCount", 0),
            "duration": photo.get("duration", 0),
            # commentCountV2 来自 V2 评论 API，通过 core.py 注入到 post 层级
            "commentCount": post.get("commentCountV2") or photo.get("commentCount") or 0,
            "realLikeCount": photo.get("realLikeCount", 0)
        }

        # author 可能在 photo 下，也可能在 post 下
        author_name = ""
        if photo.get("author"):
            author_name = photo["author"].get("name", "")
        elif post.get("author"):
            author_name = post["author"].get("name", "")

        items.append({
            "note_id": photo.get("id", ""),
            "caption": photo.get("caption", ""),
            "originCaption": photo.get("originCaption", ""),
            "nickname": author_name,
            "interact_info": interact_info,
            "comments": comment_list
        })

    return items


def process_toutiao_data(data: List[Dict]) -> List[Dict]:
    """
    处理今日头条数据

    数据结构特点 (_filter_note 返回):
    - article_id: 文章ID
    - title: 文章标题
    - content/abstract: 文章内容/摘要
    - source/author: 内容来源/作者
    - url: 文章链接
    - create_time/publish_time: 创建时间
    - read_count/like_count/comment_count/share_count: 互动数据
    - has_video/has_image: 是否有视频/图片
    - user: 作者信息 {user_id, nickname, avatar}
    - comments: 评论列表 {comment_id, content, like_count, user, sub_comments}
    """
    if not data:
        return []

    items = []
    for post in data:
        # 处理评论列表
        comment_list = []
        comments = post.get("comments") or []

        for comment in comments:
            # 处理子评论
            sub_comment_list = []
            sub_comments = comment.get("sub_comments") or []
            for sub_comment in sub_comments:
                # 获取子评论用户信息
                sub_user = sub_comment.get("user", {})
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    "create_time": sub_comment.get("create_time", 0),
                    "like_count": sub_comment.get("like_count", 0),
                    "sub_comment_nickname": sub_user.get("nickname", "")
                })

            # 获取评论用户信息
            comment_user = comment.get("user", {})
            comment_list.append({
                "comment_id": comment.get("comment_id", ""),
                "content": comment.get("content", ""),
                "create_time": comment.get("create_time", 0),
                "like_count": comment.get("like_count", 0),
                "is_pgc": 1 if comment.get("is_sub_comment") else 0,
                "comment_nickname": comment_user.get("nickname", ""),
                "sub_comment_count": len(sub_comment_list),
                "sub_comment_list": sub_comment_list
            })

        # 获取作者信息
        user_info = post.get("user", {})

        # 构建互动信息
        interact_info = {
            "read_count": post.get("read_count", 0),
            "like_count": post.get("like_count", 0),
            "comment_count": post.get("comment_count", 0),
            "share_count": post.get("share_count", 0)
        }

        items.append({
            "note_id": post.get("article_id", ""),
            "title": post.get("title", ""),
            "desc": post.get("content", ""),
            "abstract": post.get("abstract") or post.get("content", ""),
            "source": post.get("source") or post.get("author", ""),
            "share_url": post.get("url", ""),
            "create_time": post.get("publish_time") or post.get("create_time", 0),
            "nickname": user_info.get("nickname", ""),
            "avatar_url": user_info.get("avatar", ""),
            "interact_info": interact_info,
            "comments": comment_list
        })

    return items


# =========================
# 数据处理器分发器
# =========================

PLATFORM_PROCESSORS = {
    Platform.XHS.value: process_xhs_data,
    Platform.BILI.value: process_bili_data,
    Platform.DY.value: process_dy_data,
    Platform.WB.value: process_wb_data,
    Platform.ZHIHU.value: process_zhihu_data,
    Platform.TIEBA.value: process_tieba_data,
    Platform.KS.value: process_ks_data,
    Platform.TOUTIAO.value: process_toutiao_data,
}


def process_platform_data(platform: str, data: List[Dict]) -> List[Dict]:
    """
    根据平台类型处理数据

    Args:
        platform: 平台标识符 (xhs, bili, dy, wb, zhihu, tieba, ks)
        data: 原始爬取数据

    Returns:
        处理后的标准化数据列表
    """
    processor = PLATFORM_PROCESSORS.get(platform)
    if processor:
        return processor(data)
    return []


# =========================
# 输入验证器
# =========================

def validate_inputs(
    platform: str,
    crawler_type: str,
    keywords: str,
    max_count: int,
    max_comments_count: int
) -> tuple[bool, Optional[str]]:
    """
    验证输入参数

    Returns:
        (是否有效, 错误信息)
    """
    # 验证平台
    valid_platforms = [p.value for p in Platform]
    if platform not in valid_platforms:
        return False, f"无效的平台 '{platform}'，支持的平台: {', '.join(valid_platforms)}"

    # 验证爬取类型
    valid_types = [t.value for t in CrawlerType]
    if crawler_type not in valid_types:
        return False, f"无效的爬取类型 '{crawler_type}'，支持的类型: {', '.join(valid_types)}"

    # 验证关键词
    if not keywords or not keywords.strip():
        return False, "关键词不能为空"

    # 验证数量参数
    if max_count < 1 or max_count > 100:
        return False, "max_count 必须在 1-100 之间"

    if max_comments_count < 0 or max_comments_count > 50:
        return False, "max_comments_count 必须在 0-50 之间"

    return True, None


# =========================
# MCP 工具定义
# =========================

@mcp.tool()
async def crawl_media(
    platform: str,
    crawler_type: str,
    keywords: str,
    max_count: int = 20,
    is_get_comments: bool = False,
    is_get_sub_comments: bool = False,
    max_comments_count: int = 20,
    save_data_option: str = "",
    report_type: str = "sentiment",
    report_mode: str = "auto",
) -> str:
    """
    爬取社交媒体平台帖子、评论数据，并生成舆情分析报告

    **适用场景：适合单个平台深度分析。如需同时分析多个平台数据进行对比，建议使用 crawl_multi_platform 生成统一对比报告。**
    **报告输出：每个平台会生成独立的报告文件，多个平台将生成多个报告文件。**

    支持平台：
    - xhs: 小红书
    - dy: 抖音
    - ks: 快手
    - bili: B站 (哔哩哔哩)
    - wb: 微博
    - tieba: 百度贴吧
    - zhihu: 知乎
    - toutiao: 今日头条

    Args:
        platform: 平台名称，可选值: xhs, dy, ks, bili, wb, tieba, zhihu, toutiao
        crawler_type: 爬取类型，search(关键词搜索)
        keywords: 搜索关键词 (search类型) 或 内容ID (detail类型) 或 创作者ID (creator类型)
        max_count: 返回帖子数量，默认20，范围1-100
        is_get_comments: 是否爬取评论，默认False
        is_get_sub_comments: 是否爬取子评论，默认False
        max_comments_count: 主评论数量，以及每个主评论下子评论的数量，默认20，范围0-50（主评论和子评论数量分别控制）
        save_data_option: 数据存储方式，可选值: ""(不存储), "db"(存储到数据库)，默认""
        report_type: 报告类型，可选值: "sentiment"(情感分析), "trend"(热门趋势), "hot_topics"(热门话题), "keyword"(关键词分析), "volume"(声量分析), "viral_spread"(传播分析), "influencer"(影响力账号), "audience"(用户画像), "comparison"(竞品对比), "risk"(舆情风险)，默认"sentiment"

    Note:
        报告生成会自动检测LLM配置：如果配置了 ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY
        （或 OPENAI_BASE_URL + OPENAI_API_KEY），将使用AI大模型生成高质量报告；
        否则使用内置脚本生成标准报告。

    Returns:
        JSON格式的报告结果，包含报告文件路径和分析摘要

    Example:
        {
            "status": "success",
            "platform": "xhs",
            "keywords": "Python编程",
            "report_path": "reports/小红书_Python编程_舆情分析报告_20250330_143000.html",
            "summary": "...",
            "message": "舆情分析报告已生成"
        }
    """
    try:
        # 如果未指定输出路径，使用默认报告目录（项目根目录下的 reports）
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(DEFAULT_REPORTS_DIR)

        # 参数验证
        is_valid, error_msg = validate_inputs(
            platform, crawler_type, keywords, max_count, max_comments_count
        )
        if not is_valid:
            return json.dumps(
                {
                    "status": "error",
                    "platform": platform,
                    "crawler_type": crawler_type,
                    "keywords": keywords,
                    "message": error_msg,
                    "count": 0,
                    "items": []
                },
                ensure_ascii=False,
            )

        # 执行爬取
        raw_data = await asyncio.to_thread(
            run_crawl_sync,
            platform,
            crawler_type,
            keywords,
            max_count,
            is_get_comments,
            is_get_sub_comments,
            max_comments_count,
            save_data_option
        )

        # 数据为空检查
        if not raw_data:
            return json.dumps(
                {
                    "status": "success",
                    "platform": platform,
                    "crawler_type": crawler_type,
                    "keywords": keywords,
                    "is_get_comments": is_get_comments,
                    "is_get_sub_comments": is_get_sub_comments,
                    "max_comments_count": max_comments_count,
                    "save_data_option": save_data_option,
                    "report_path": None,
                    "summary": "未获取到任何数据",
                    "message": "未获取到任何数据"
                },
                ensure_ascii=False,
            )

        # 处理平台数据
        items = process_platform_data(platform, raw_data)

        # 保存处理后数据到JSON文件
        if items:
            try:
                raw_data_dir = PROJECT_ROOT / "original_data"
                raw_data_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                raw_data_file = raw_data_dir / f"{platform}_{keywords}_{timestamp}.json"
                with open(raw_data_file, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2, default=str)
                print(f"[DEBUG] 处理后数据已保存: {raw_data_file}")
            except Exception as e:
                print(f"[DEBUG] 保存数据失败: {e}")

        # 生成舆情分析报告
        try:
            platform_name = PLATFORM_NAMES.get(platform, platform)

  # 检查是否配置了 AI API
            ai_api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
            ai_base_url = os.getenv("ANTHROPIC_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            has_ai_config = bool(ai_api_key and ai_base_url)

            # 确定报告生成模式
            if report_mode == "script":
                use_ai = False
            elif report_mode == "ai":
                use_ai = has_ai_config
                if not has_ai_config:
                    print("警告: 未配置 LLM，回退到脚本模式。请配置 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL")
            else:
                # auto 模式：配置了就用AI，否则用脚本
                use_ai = has_ai_config

            # 根据配置选择生成方式
            if use_ai:
                # AI 增强报告生成
                from reporting.ai_report_generator import generate_ai_report_data
                from reporting.llm_report_generator import generate_report_with_llm

                # 1. 准备 AI 报告数据（传入 report_type 以生成对应类型的报告）
                ai_data = generate_ai_report_data(platform, keywords, items, report_type)

                # 2. 调用 LLM API 生成报告
                report_path, summary = await generate_report_with_llm(
                    platform=platform,
                    keywords=keywords,
                    ai_data=ai_data,
                    output_path=output_path,
                    report_type=report_type
                )

                abs_path = os.path.abspath(report_path)

                # 准备验证样本（前3条原始数据用于核对真实性）
                verification_samples = []
                for item in items[:3]:
                    sample = {
                        "title": (item.get('title') or item.get('desc', '') or item.get('caption', ''))[:100],
                        "author": item.get('nickname', item.get('author', '未知')),
                        "interact_info": item.get('interact_info', {}),
                        "comment_preview": []
                    }
                    # 添加前2条评论作为验证
                    comments = item.get('comments', [])
                    for c in comments[:2]:
                        if isinstance(c, dict):
                            sample["comment_preview"].append({
                                "user": c.get('comment_nickname', c.get('user_nickname', '匿名')),
                                "content": c.get('content', '')[:100] if c.get('content') else '',
                                "likes": c.get('like_count', 0)
                            })
                    verification_samples.append(sample)

                return json.dumps(
                    {
                        "status": "success",
                        "platform": platform,
                        "platform_name": platform_name,
                        "crawler_type": crawler_type,
                        "keywords": keywords,
                        "is_get_comments": is_get_comments,
                        "is_get_sub_comments": is_get_sub_comments,
                        "max_comments_count": max_comments_count,
                        "report_mode": "ai_enhanced",
                        "has_ai_config": True,
                        "report_path": abs_path,
                        "relative_path": report_path,
                        "summary": summary,
                        "verification_samples": verification_samples,  # 真实性验证样本
                        "message": f"AI 增强报告已生成: {abs_path}"
                    },
                    ensure_ascii=False,
                )
            else:
                # 脚本自动生成报告（标准模式）
                from reporting.report_generator import generate_report

                report_path, summary, html_content = generate_report(
                    platform=platform,
                    keywords=keywords,
                    data=items,
                    output_path=output_path,
                    report_type=report_type
                )

                # 转换为绝对路径，便于点击访问
                abs_path = os.path.abspath(report_path)

                # 准备验证样本（前3条原始数据用于核对真实性）
                verification_samples = []
                for item in items[:3]:
                    sample = {
                        "title": (item.get('title') or item.get('desc', '') or item.get('caption', ''))[:100],
                        "author": item.get('nickname', item.get('author', '未知')),
                        "interact_info": item.get('interact_info', {}),
                        "comment_preview": []
                    }
                    # 添加前2条评论作为验证
                    comments = item.get('comments', [])
                    for c in comments[:2]:
                        if isinstance(c, dict):
                            sample["comment_preview"].append({
                                "user": c.get('comment_nickname', c.get('user_nickname', '匿名')),
                                "content": c.get('content', '')[:100] if c.get('content') else '',
                                "likes": c.get('like_count', 0)
                            })
                    verification_samples.append(sample)

                # 返回报告信息
                return json.dumps(
                    {
                        "status": "success",
                        "platform": platform,
                        "platform_name": platform_name,
                        "crawler_type": crawler_type,
                        "keywords": keywords,
                        "report_mode": "script",
                        "has_ai_config": has_ai_config,
                        "is_get_comments": is_get_comments,
                        "is_get_sub_comments": is_get_sub_comments,
                        "max_comments_count": max_comments_count,
                        "report_path": abs_path,  # 绝对路径，可点击打开
                        "relative_path": report_path,
                        "summary": summary,
                        "verification_samples": verification_samples,  # 真实性验证样本
                        "message": f"舆情分析报告已生成: {abs_path}" +
                                   (" (未使用AI：请先配置 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL 环境变量)" if not has_ai_config else "")
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            # 如果生成报告失败，回退到返回原始数据（只返回3条样本）
            # 准备验证样本（前3条原始数据用于核对真实性）
            verification_samples = []
            for item in items[:3]:
                sample = {
                    "title": (item.get('title') or item.get('desc', '') or item.get('caption', ''))[:100],
                    "author": item.get('nickname', item.get('author', '未知')),
                    "interact_info": item.get('interact_info', {}),
                    "comment_preview": []
                }
                # 添加前2条评论作为验证
                comments = item.get('comments', [])
                for c in comments[:2]:
                    if isinstance(c, dict):
                        sample["comment_preview"].append({
                            "user": c.get('comment_nickname', c.get('user_nickname', '匿名')),
                            "content": c.get('content', '')[:100] if c.get('content') else '',
                            "likes": c.get('like_count', 0)
                        })
                verification_samples.append(sample)

            result = CrawlResult(
                platform=platform,
                crawler_type=crawler_type,
                keywords=keywords,
                is_get_comments=is_get_comments,
                is_get_sub_comments=is_get_sub_comments,
                max_comments_count=max_comments_count,
                save_data_option=save_data_option,
                count=len(items),
                items=items[:3],  # 只返回前3条
                status="success"
            )

            return json.dumps(
                {
                    "status": result.status,
                    "platform": result.platform,
                    "crawler_type": result.crawler_type,
                    "keywords": result.keywords,
                    "is_get_comments": result.is_get_comments,
                    "is_get_sub_comments": result.is_get_sub_comments,
                    "max_comments_count": result.max_comments_count,
                    "save_data_option": result.save_data_option,
                    "count": result.count,
                    "items": result.items,
                    "total_items": len(items),  # 返回实际总数
                    "verification_samples": verification_samples,
                    "report_error": str(e)
                },
                ensure_ascii=False,
            )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "platform": platform,
                "crawler_type": crawler_type,
                "keywords": keywords,
                "is_get_comments": is_get_comments,
                "is_get_sub_comments": is_get_sub_comments,
                "max_comments_count": max_comments_count,
                "save_data_option": save_data_option,
                "count": 0,
                "message": f"爬取失败: {str(e)}",
                "items": []
            },
            ensure_ascii=False,
        )


@mcp.tool()
async def get_platforms() -> str:
    """
    获取支持的平台列表

    Returns:
        JSON格式的平台列表，包含平台代码和描述
    """
    platforms = [
        {"code": Platform.XHS.value, "name": "小红书", "description": "生活方式分享平台"},
        {"code": Platform.DY.value, "name": "抖音", "description": "短视频平台"},
        {"code": Platform.KS.value, "name": "快手", "description": "短视频直播平台"},
        {"code": Platform.BILI.value, "name": "B站", "description": "哔哩哔哩视频平台"},
        {"code": Platform.WB.value, "name": "微博", "description": "社交媒体平台"},
        {"code": Platform.TIEBA.value, "name": "百度贴吧", "description": "兴趣社区论坛"},
        {"code": Platform.ZHIHU.value, "name": "知乎", "description": "问答知识社区"},
        {"code": Platform.TOUTIAO.value, "name": "今日头条", "description": "新闻资讯聚合平台"},
    ]

    return json.dumps(
        {
            "status": "success",
            "count": len(platforms),
            "platforms": platforms
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def get_crawler_types() -> str:
    """
    获取支持的爬取类型列表

    Returns:
        JSON格式的爬取类型列表
    """
    types = [
        {"code": CrawlerType.SEARCH.value, "name": "关键词搜索", "description": "根据关键词搜索帖子/视频内容"},
        {"code": CrawlerType.DETAIL.value, "name": "详情获取", "description": "根据ID获取指定帖子/视频的详细信息"},
        {"code": CrawlerType.CREATOR.value, "name": "创作者主页", "description": "获取指定创作者的主页内容"},
    ]

    return json.dumps(
        {
            "status": "success",
            "count": len(types),
            "types": types
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def crawl_multi_platform(
    platforms: List[str],
    crawler_type: str,
    keywords: str,
    max_count: int = 20,
    is_get_comments: bool = False,
    is_get_sub_comments: bool = False,
    max_comments_count: int = 20,
    save_data_option: str = "",
    report_type: str = "sentiment",
    report_mode: str = "auto",
) -> str:
    """
    爬取多个社交媒体平台的帖子、评论数据，并生成统一的舆情分析报告

    **适用场景：适合多平台对比分析，一次调用同时抓取多个平台并生成统一报告。如需为每个平台生成独立报告，请多次调用 crawl_media。**
    **报告输出：多个平台只生成一个合并的对比报告文件，便于跨平台数据分析。**

    支持平台：
    - xhs: 小红书
    - dy: 抖音
    - ks: 快手
    - bili: B站 (哔哩哔哩)
    - wb: 微博
    - tieba: 百度贴吧
    - zhihu: 知乎
    - toutiao: 今日头条

    Args:
        platforms: 平台名称列表，例如 ["xhs", "dy", "bili"]
        crawler_type: 爬取类型，可选值: search(关键词搜索), detail(指定ID详情), creator(创作者主页)
        keywords: 搜索关键词 (search类型) 或 内容ID (detail类型) 或 创作者ID (creator类型)
        max_count: 每个平台返回帖子数量，默认20，范围1-100
        is_get_comments: 是否爬取评论，默认False
        is_get_sub_comments: 是否爬取子评论，默认False
        max_comments_count: 主评论数量，以及每个主评论下子评论的数量，默认20，范围0-50（主评论和子评论数量分别控制）
        save_data_option: 数据存储方式，可选值: ""(不存储), "db"(存储到数据库)，默认""
        report_type: 报告类型，可选值: "sentiment"(情感分析), "trend"(热门趋势), "hot_topics"(热门话题), "keyword"(关键词分析), "volume"(声量分析), "viral_spread"(传播分析), "influencer"(影响力账号), "audience"(用户画像), "comparison"(竞品对比), "risk"(舆情风险)，默认"sentiment"

    Note:
        报告生成会自动检测LLM配置：如果配置了 ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY
        （或 OPENAI_BASE_URL + OPENAI_API_KEY），将使用AI大模型生成高质量报告；
        否则使用内置脚本生成标准报告。

    Returns:
        JSON格式的报告结果，包含报告文件路径和分析摘要

    Example:
        {
            "status": "success",
            "platforms": ["xhs", "dy", "bili"],
            "platform_names": ["小红书", "抖音", "B站"],
            "keywords": "宝宝巴士",
            "report_path": "reports/多平台_宝宝巴士_舆情分析报告_20250330_143000.html",
            "summary": "...",
            "message": "多平台舆情分析报告已生成"
        }
    """
    try:
        # 如果未指定输出路径，使用默认报告目录（项目根目录下的 reports）
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(DEFAULT_REPORTS_DIR)

        # 验证参数
        valid_platforms = [p.value for p in Platform]
        for platform in platforms:
            if platform not in valid_platforms:
                return json.dumps(
                    {
                        "status": "error",
                        "platforms": platforms,
                        "keywords": keywords,
                        "message": f"无效的平台 '{platform}'，支持的平台: {', '.join(valid_platforms)}",
                        "count": 0,
                    },
                    ensure_ascii=False,
                )

        valid_types = [t.value for t in CrawlerType]
        if crawler_type not in valid_types:
            return json.dumps(
                {
                    "status": "error",
                    "platforms": platforms,
                    "keywords": keywords,
                    "message": f"无效的爬取类型 '{crawler_type}'，支持的类型: {', '.join(valid_types)}",
                },
                ensure_ascii=False,
            )

        if not keywords or not keywords.strip():
            return json.dumps(
                {
                    "status": "error",
                    "platforms": platforms,
                    "keywords": keywords,
                    "message": "关键词不能为空",
                },
                ensure_ascii=False,
            )

        if max_count < 1 or max_count > 100:
            return json.dumps(
                {
                    "status": "error",
                    "platforms": platforms,
                    "keywords": keywords,
                    "message": "max_count 必须在 1-100 之间",
                },
                ensure_ascii=False,
            )

        if max_comments_count < 0 or max_comments_count > 50:
            return json.dumps(
                {
                    "status": "error",
                    "platforms": platforms,
                    "keywords": keywords,
                    "message": "max_comments_count 必须在 0-50 之间",
                },
                ensure_ascii=False,
            )

        # 依次爬取各个平台的数据
        all_platform_data = {}
        platform_names = []

        for platform in platforms:
            try:
                raw_data = await asyncio.to_thread(
                    run_crawl_sync,
                    platform,
                    crawler_type,
                    keywords,
                    max_count,
                    is_get_comments,
                    is_get_sub_comments,
                    max_comments_count,
                    save_data_option
                )

                if raw_data:
                    items = process_platform_data(platform, raw_data)
                    if items:
                        # 保存处理后数据到JSON文件
                        try:
                            raw_data_dir = PROJECT_ROOT / "original_data"
                            raw_data_dir.mkdir(exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            raw_data_file = raw_data_dir / f"multi_{platform}_{keywords}_{timestamp}.json"
                            with open(raw_data_file, "w", encoding="utf-8") as f:
                                json.dump(items, f, ensure_ascii=False, indent=2, default=str)
                            print(f"[DEBUG] 处理后数据已保存: {raw_data_file}")
                        except Exception as e:
                            print(f"[DEBUG] 保存数据失败: {e}")
                        all_platform_data[platform] = items
                        platform_names.append(PLATFORM_NAMES.get(platform, platform))
            except Exception as e:
                # 单个平台失败不影响其他平台
                print(f"平台 {platform} 爬取失败: {e}")
                continue

        # 数据为空检查
        if not all_platform_data:
            return json.dumps(
                {
                    "status": "success",
                    "platforms": platforms,
                    "keywords": keywords,
                    "is_get_comments": is_get_comments,
                    "is_get_sub_comments": is_get_sub_comments,
                    "max_comments_count": max_comments_count,
                    "report_path": None,
                    "summary": "未获取到任何数据",
                    "message": "未获取到任何数据"
                },
                ensure_ascii=False,
            )

        # 确定报告生成模式
        ai_api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        ai_base_url = os.getenv("ANTHROPIC_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        has_ai_config = bool(ai_api_key and ai_base_url)

        if report_mode == "script":
            use_ai = False
        elif report_mode == "ai":
            use_ai = has_ai_config
            if not has_ai_config:
                print("警告: 未配置 LLM，回退到脚本模式。请配置 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL")
        else:
            # auto 模式：配置了就用AI，否则用脚本
            use_ai = has_ai_config

        # 生成统一的舆情分析报告
        try:
            if use_ai:
                # AI 增强报告生成 - 多平台合并
                from reporting.ai_report_generator import generate_multi_platform_report_data
                from reporting.llm_report_generator import generate_multi_platform_report_with_llm

                # 1. 准备 AI 报告数据（多平台）
                ai_data = generate_multi_platform_report_data(
                    platform_data=all_platform_data,
                    keywords=keywords,
                    report_type=report_type
                )

                # 2. 调用 LLM API 生成多平台报告
                report_path, summary = await generate_multi_platform_report_with_llm(
                    platform_data=all_platform_data,
                    keywords=keywords,
                    ai_data=ai_data,
                    output_path=output_path,
                    report_type=report_type
                )

                abs_path = os.path.abspath(report_path)

                return json.dumps(
                    {
                        "status": "success",
                        "platforms": list(all_platform_data.keys()),
                        "platform_names": platform_names,
                        "crawler_type": crawler_type,
                        "keywords": keywords,
                        "is_get_comments": is_get_comments,
                        "is_get_sub_comments": is_get_sub_comments,
                        "max_comments_count": max_comments_count,
                        "report_mode": "ai_enhanced",
                        "has_ai_config": True,
                        "report_path": abs_path,
                        "relative_path": report_path,
                        "summary": summary,
                        "total_items": sum(len(items) for items in all_platform_data.values()),
                        "platform_breakdown": {p: len(items) for p, items in all_platform_data.items()},
                        "message": f"多平台舆情分析报告已生成: {abs_path}"
                    },
                    ensure_ascii=False,
                )
            else:
                # 脚本自动生成报告（多平台合并）
                from reporting.report_generator import generate_multi_platform_report

                report_path, summary, html_content = generate_multi_platform_report(
                    platform_data=all_platform_data,
                    keywords=keywords,
                    output_path=output_path,
                    report_type=report_type
                )

                # 转换为绝对路径，便于点击访问
                abs_path = os.path.abspath(report_path)

                return json.dumps(
                    {
                        "status": "success",
                        "platforms": list(all_platform_data.keys()),
                        "platform_names": platform_names,
                        "crawler_type": crawler_type,
                        "keywords": keywords,
                        "report_mode": "script",
                        "has_ai_config": has_ai_config,
                        "is_get_comments": is_get_comments,
                        "is_get_sub_comments": is_get_sub_comments,
                        "max_comments_count": max_comments_count,
                        "report_path": abs_path,
                        "relative_path": report_path,
                        "summary": summary,
                        "total_items": sum(len(items) for items in all_platform_data.values()),
                        "platform_breakdown": {p: len(items) for p, items in all_platform_data.items()},
                        "message": f"多平台舆情分析报告已生成: {abs_path}" +
                                   (" (未使用AI：请先配置 ANTHROPIC_API_KEY 和 ANTHROPIC_BASE_URL 环境变量)" if not has_ai_config else "")
                    },
                    ensure_ascii=False,
                )

        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "platforms": platforms,
                    "keywords": keywords,
                    "is_get_comments": is_get_comments,
                    "max_comments_count": max_comments_count,
                    "message": f"生成报告失败: {str(e)}",
                },
                ensure_ascii=False,
            )

    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "platforms": platforms,
                "crawler_type": crawler_type,
                "keywords": keywords,
                "is_get_comments": is_get_comments,
                "max_comments_count": max_comments_count,
                "message": f"爬取失败: {str(e)}",
            },
            ensure_ascii=False,
        )


# =========================
# 服务器入口
# =========================

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.run(transport="sse", host=os.getenv("MCP_HOST", "0.0.0.0"), port=int(os.getenv("MCP_PORT", "8000")))
    elif transport == "streamable-http":
        mcp.run(transport="streamable-http", host=os.getenv("MCP_HOST", "0.0.0.0"), port=int(os.getenv("MCP_PORT", "8000")))
    else:
        mcp.run()

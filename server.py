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
import asyncio
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from mcp.server.fastmcp import FastMCP
from mcp_adapter import run_crawl_sync


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


class CrawlerType(str, Enum):
    """爬取类型枚举"""
    SEARCH = "search"     # 关键词搜索
    DETAIL = "detail"     # 指定ID详情
    CREATOR = "creator"   # 创作者主页


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
                content_obj = sub_comment.get("content", {})
                sub_comment_list.append({
                    "content": content_obj.get("message", ""),
                    "create_time": sub_comment.get("ctime", ""),
                    "like_count": sub_comment.get("like_count", 0),
                    "sub_comment_nickname": sub_comment.get("member", {}).get("uname", "")
                })

            comment_content = comment.get("content", {})
            comment_list.append({
                "content": comment_content.get("message", ""),
                "sub_comment_count": len(sub_comment_list),
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
                    "like_count": sub_comment.get("like_count", 0),
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
                "like_count": comment.get("like_count", 0),
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
                    "content": sub_comment.get("text", ""),
                    "create_time": sub_comment.get("created_at", ""),
                    "sub_comment_nickname": sub_comment.get("user", {}).get("nickname", "")
                })

            comment_list.append({
                "created_at": comment.get("created_at", ""),
                "content": comment.get("text", ""),
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
            "desc": mblog.get("text", ""),
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
            comment_list.append({
                "comment_id": comment.get("comment_id", ""),
                "parent_comment_id": comment.get("parent_comment_id", ""),
                "content": comment.get("content", ""),
                "sub_comment_count": comment.get("sub_comment_count", 0),
                "like_count": comment.get("like_count", 0),
                "user_nickname": comment.get("user_nickname", "")
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
            comment_list.append({
                "content": comment.get("content", ""),
                "parent_comment_id": comment.get("parent_comment_id", ""),
                "comment_id": comment.get("comment_id", ""),
                "sub_comment_count": comment.get("sub_comment_count", 0),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user_nickname", ""),
                "ip_location": comment.get("ip_location", "")
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
    - photo: 视频信息
    - author: 作者信息
    - comments: 评论列表
    """
    if not data:
        return []

    items = []
    for post in data:
        photo = post.get("photo", {})
        comments = post.get("comments") or []

        interact_info = {
            "likeCount": photo.get("likeCount", 0),
            "viewCount": photo.get("viewCount", 0),
            "duration": photo.get("duration", 0),
            "commentCount": photo.get("commentCount", 0),
            "realLikeCount": photo.get("realLikeCount", 0)
        }

        items.append({
            "note_id": photo.get("id", ""),
            "caption": photo.get("caption", ""),
            "originCaption": photo.get("originCaption", ""),
            "nickname": photo.get("author", {}).get("name", ""),
            "interact_info": interact_info,
            "comments": comments
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
    max_count: int = 10,
    is_get_comments: bool = False,
    is_get_sub_comments: bool = False,
    max_comments_count: int = 5,
    save_data_option: str = "",
) -> str:
    """
    爬取社交媒体平台帖子、评论数据

    支持平台：
    - xhs: 小红书
    - dy: 抖音
    - ks: 快手
    - bili: B站 (哔哩哔哩)
    - wb: 微博
    - tieba: 百度贴吧
    - zhihu: 知乎

    Args:
        platform: 平台名称，可选值: xhs, dy, ks, bili, wb, tieba, zhihu
        crawler_type: 爬取类型，可选值: search(关键词搜索), detail(指定ID详情), creator(创作者主页)
        keywords: 搜索关键词 (search类型) 或 内容ID (detail类型) 或 创作者ID (creator类型)
        max_count: 返回帖子数量，默认10，范围1-100
        is_get_comments: 是否爬取评论，默认False
        is_get_sub_comments: 是否爬取子评论，默认False
        max_comments_count: 返回帖子下评论数量以及每个评论的子评论的数量，默认5，范围0-50
        save_data_option: 数据存储方式，可选值: ""(不存储), "db"(存储到数据库)，默认""

    Returns:
        JSON格式的爬取结果，包含平台信息、爬取参数、数据条数和数据列表

    Example:
        {
            "platform": "xhs",
            "crawler_type": "search",
            "keywords": "Python编程",
            "is_get_comments": true,
            "is_get_sub_comments": false,
            "max_comments_count": 5,
            "save_data_option": "",
            "count": 10,
            "status": "success",
            "items": [
                {
                    "note_id": "123456",
                    "title": "标题",
                    "nickname": "作者昵称",
                    "interact_info": {...},
                    "desc": "正文描述",
                    "comments": [...]
                }
            ]
        }
    """
    try:
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
                    "count": 0,
                    "message": "未获取到任何数据",
                    "items": []
                },
                ensure_ascii=False,
            )

        # 处理平台数据
        items = process_platform_data(platform, raw_data)

        # 构建返回结果
        result = CrawlResult(
            platform=platform,
            crawler_type=crawler_type,
            keywords=keywords,
            is_get_comments=is_get_comments,
            is_get_sub_comments=is_get_sub_comments,
            max_comments_count=max_comments_count,
            save_data_option=save_data_option,
            count=len(items),
            items=items,
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
                "items": result.items
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


# =========================
# 服务器入口
# =========================

if __name__ == "__main__":
    mcp.run()

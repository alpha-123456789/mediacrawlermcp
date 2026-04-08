# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条数据存储模块
"""

import json
from typing import Dict, List

import config
from var import source_keyword_var
from tools import utils

from ._store_impl import *


class ToutiaoStoreFactory:
    """今日头条存储工厂"""

    STORES = {
        "csv": ToutiaoCsvStoreImplement,
        "db": ToutiaoDbStoreImplement,
        "postgres": ToutiaoDbStoreImplement,
        "json": ToutiaoJsonStoreImplement,
        "jsonl": ToutiaoJsonlStoreImplement,
        "sqlite": ToutiaoSqliteStoreImplement,
        "mongodb": ToutiaoMongoStoreImplement,
        "excel": ToutiaoExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        """创建存储实例"""
        store_class = ToutiaoStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError("[ToutiaoStoreFactory.create_store] 不支持的存储类型")
        return store_class()


async def update_toutiao_article(article_item: Dict):
    """
    更新今日头条文章
    Args:
        article_item: 文章数据
    """
    article_id = article_item.get("article_id", "")

    # 处理用户数据
    user = article_item.get("user", {})
    user_dict = {}
    if isinstance(user, dict):
        user_dict = user

    # 处理媒体信息
    media_info = article_item.get("media_info", {})
    media_dict = {}
    if isinstance(media_info, dict):
        media_dict = media_info

    # 获取发布者名称：优先从user.name获取，其次是author/source
    author_name = user_dict.get("name", "") if isinstance(user_dict, dict) else ""
    if not author_name:
        author_name = article_item.get("author", article_item.get("source", ""))

    local_db_item = {
        "article_id": article_id,
        "title": article_item.get("title", ""),
        "abstract": article_item.get("abstract", ""),
        "content": article_item.get("content", ""),
        "source": article_item.get("source", ""),
        "publish_time": article_item.get("publish_time", 0),
        "publish_time_text": article_item.get("publish_time_text", ""),
        "create_time": article_item.get("create_time", ""),
        "url": article_item.get("url", f"https://www.toutiao.com/article/{article_id}/"),
        "read_count": article_item.get("read_count", 0),
        "like_count": article_item.get("like_count", 0),
        "digg_count": article_item.get("digg_count", 0),
        "bury_count": article_item.get("bury_count", 0),
        "repin_count": article_item.get("repin_count", 0),
        "comment_count": article_item.get("comment_count", 0),
        "share_count": article_item.get("share_count", 0),
        "has_video": article_item.get("has_video", False),
        "has_image": article_item.get("has_image", False),
        "video_duration": article_item.get("video_duration", 0),
        "image_list": json.dumps(article_item.get("image_list", [])),
        "large_image": article_item.get("large_image", ""),
        "media_id": media_dict.get("media_id", "") if isinstance(media_dict, dict) else "",
        "media_name": media_dict.get("name", "") if isinstance(media_dict, dict) else article_item.get("media_name", ""),
        "user_id": user_dict.get("user_id", "") if isinstance(user_dict, dict) else "",
        "nickname": author_name,
        "avatar_url": user_dict.get("avatar_url", "") if isinstance(user_dict, dict) else "",
        "detail_fetched": article_item.get("detail_fetched", False),
        "source_keyword": source_keyword_var.get(),
        "last_modify_ts": utils.get_current_timestamp(),
        "raw_data": json.dumps(article_item.get("raw_data", {}), ensure_ascii=False),
    }

    utils.logger.info(f"[store.toutiao.update_toutiao_article] 文章: {article_id}, 标题: {article_item.get('title', '')[:30]}...")
    await ToutiaoStoreFactory.create_store().store_content(local_db_item)


async def batch_update_toutiao_articles(article_list: List[Dict]):
    """
    批量更新文章
    Args:
        article_list: 文章列表
    """
    if not article_list:
        return
    for article in article_list:
        await update_toutiao_article(article)


async def update_toutiao_comment(comment_item: Dict):
    """
    更新评论（兼容一级评论和子评论）
    Args:
        comment_item: 评论数据
    """
    comment_id = comment_item.get("comment_id", "")
    user_info = comment_item.get("user", {})

    # 提取回复目标用户信息（优先使用平铺字段，兼容嵌套对象）
    reply_to_user_id = comment_item.get("reply_to_user_id", "")
    reply_to_nickname = comment_item.get("reply_to_nickname", "")

    # 如果平铺字段为空，尝试从嵌套对象获取
    if not reply_to_user_id:
        reply_to_user = comment_item.get("reply_to_user", {})
        if isinstance(reply_to_user, dict):
            reply_to_user_id = reply_to_user.get("user_id", "")
            reply_to_nickname = reply_to_nickname or reply_to_user.get("nickname", "")

    # 判断是否是子评论
    is_sub = comment_item.get("is_sub_comment", False)
    parent_id = comment_item.get("parent_id") or comment_item.get("parent_comment_id", "")
    if not is_sub and parent_id:
        is_sub = True

    local_db_item = {
        "comment_id": comment_id,
        "article_id": comment_item.get("article_id", ""),
        "content": comment_item.get("content", ""),
        "create_time": comment_item.get("create_time", 0),
        "like_count": comment_item.get("like_count", 0),
        "reply_count": comment_item.get("reply_count", 0),
        "is_sub_comment": 1 if is_sub else 0,
        "user_id": user_info.get("user_id", ""),
        "nickname": user_info.get("nickname", ""),
        "avatar": user_info.get("avatar", ""),
        "parent_comment_id": parent_id,
        "reply_to_user_id": reply_to_user_id,
        "reply_to_nickname": reply_to_nickname,
        "last_modify_ts": utils.get_current_timestamp(),
        "raw_data": json.dumps(comment_item.get("raw_data", {}), ensure_ascii=False),
    }

    utils.logger.info(f"[store.toutiao.update_toutiao_comment] {comment_item.get('is_sub_comment', False) and '子评论' or '评论'}: {comment_id}")
    await ToutiaoStoreFactory.create_store().store_comment(local_db_item)


async def batch_update_toutiao_comments(article_id: str, comment_list: List[Dict]):
    """
    批量更新评论
    Args:
        article_id: 文章ID
        comment_list: 评论列表
    """
    if not comment_list:
        return
    for comment in comment_list:
        comment["article_id"] = article_id
        await update_toutiao_comment(comment)


async def update_toutiao_subcomment(subcomment_item: Dict):
    """
    更新子评论（评论的回复）
    复用 update_toutiao_comment 逻辑
    Args:
        subcomment_item: 子评论数据
    """
    # 确保 is_sub_comment 标记为 True
    subcomment_item["is_sub_comment"] = True
    # 子评论的 parent_id 已经是正确的
    await update_toutiao_comment(subcomment_item)


async def batch_update_toutiao_subcomments(article_id: str, parent_comment_id: str, subcomment_list: List[Dict]):
    """
    批量更新子评论
    Args:
        article_id: 文章ID
        parent_comment_id: 父评论ID
        subcomment_list: 子评论列表
    """
    if not subcomment_list:
        return
    for subcomment in subcomment_list:
        subcomment["article_id"] = article_id
        subcomment["parent_id"] = parent_comment_id
        await update_toutiao_subcomment(subcomment)


async def update_toutiao_creator(creator_item: Dict):
    """
    更新创作者信息
    Args:
        creator_item: 创作者数据
    """
    creator_id = creator_item.get("creator_id", "")

    local_db_item = {
        "creator_id": creator_id,
        "nickname": creator_item.get("nickname", ""),
        "avatar": creator_item.get("avatar", ""),
        "description": creator_item.get("description", ""),
        "follow_count": creator_item.get("follow_count", 0),
        "fans_count": creator_item.get("fans_count", 0),
        "last_modify_ts": utils.get_current_timestamp(),
        "raw_data": json.dumps(creator_item.get("raw_data", {}), ensure_ascii=False),
    }

    utils.logger.info(f"[store.toutiao.update_toutiao_creator] 创作者: {creator_id}")
    await ToutiaoStoreFactory.create_store().store_creator(local_db_item)


async def save_creator(user_id: str, user_info: Dict):
    """
    保存创作者信息 (兼容接口)
    Args:
        user_id: 用户ID
        user_info: 用户信息
    """
    creator_data = {
        "creator_id": user_id,
        "nickname": user_info.get("name", user_info.get("nickname", "")),
        "avatar": user_info.get("avatar", user_info.get("avatar_url", "")),
        "description": user_info.get("description", user_info.get("sign", "")),
        "follow_count": user_info.get("follow_count", 0),
        "fans_count": user_info.get("fans_count", user_info.get("followers_count", 0)),
        "raw_data": user_info,
    }
    await update_toutiao_creator(creator_data)

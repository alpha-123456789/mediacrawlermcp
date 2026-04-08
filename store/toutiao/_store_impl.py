# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条存储实现类
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import ToutiaoArticle, ToutiaoComment, ToutiaoCreator
from tools.async_file_writer import AsyncFileWriter
from tools.time_util import get_current_timestamp
from var import crawler_type_var
from tools import utils
from store.excel_store_base import ExcelStoreBase


class ToutiaoCsvStoreImplement(AbstractStore):
    """CSV存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="toutiao", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        """存储文章内容到CSV"""
        await self.writer.write_to_csv(item_type="contents", item=content_item)

    async def store_comment(self, comment_item: Dict):
        """存储评论到CSV"""
        await self.writer.write_to_csv(item_type="comments", item=comment_item)

    async def store_creator(self, creator_item: Dict):
        """存储创作者信息到CSV"""
        await self.writer.write_to_csv(item_type="creators", item=creator_item)

    def flush(self):
        pass


class ToutiaoJsonStoreImplement(AbstractStore):
    """JSON存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="toutiao", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        """存储文章内容到JSON"""
        await self.writer.write_single_item_to_json(item_type="contents", item=content_item)

    async def store_comment(self, comment_item: Dict):
        """存储评论到JSON"""
        await self.writer.write_single_item_to_json(item_type="comments", item=comment_item)

    async def store_creator(self, creator_item: Dict):
        """存储创作者信息到JSON"""
        await self.writer.write_single_item_to_json(item_type="creators", item=creator_item)

    def flush(self):
        pass


class ToutiaoJsonlStoreImplement(AbstractStore):
    """JSONL存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="toutiao", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        """存储文章内容到JSONL"""
        await self.writer.write_to_jsonl(item_type="contents", item=content_item)

    async def store_comment(self, comment_item: Dict):
        """存储评论到JSONL"""
        await self.writer.write_to_jsonl(item_type="comments", item=comment_item)

    async def store_creator(self, creator_item: Dict):
        """存储创作者信息到JSONL"""
        await self.writer.write_to_jsonl(item_type="creators", item=creator_item)

    def flush(self):
        pass


class ToutiaoDbStoreImplement(AbstractStore):
    """数据库存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def store_content(self, content_item: Dict):
        """存储文章内容到数据库"""
        article_id = content_item.get("article_id")
        if not article_id:
            return
        async with get_session() as session:
            if await self.content_is_exist(session, article_id):
                await self.update_content(session, content_item)
            else:
                await self.add_content(session, content_item)

    async def add_content(self, session: AsyncSession, content_item: Dict):
        add_ts = int(get_current_timestamp())
        last_modify_ts = int(get_current_timestamp())
        article = ToutiaoArticle(
            article_id=content_item.get("article_id"),
            title=content_item.get("title", ""),
            content=content_item.get("content", ""),
            abstract=content_item.get("abstract", ""),
            source=content_item.get("source", ""),
            url=content_item.get("url", ""),
            user_id=content_item.get("user_id", ""),
            nickname=content_item.get("nickname", ""),
            avatar_url=content_item.get("avatar_url", ""),
            has_video=1 if content_item.get("has_video") else 0,
            has_image=1 if content_item.get("has_image") else 0,
            image_list=content_item.get("image_list", "[]"),
            video_duration=content_item.get("video_duration", 0),
            read_count=content_item.get("read_count", 0),
            like_count=content_item.get("like_count", 0),
            digg_count=content_item.get("digg_count", 0),
            bury_count=content_item.get("bury_count", 0),
            repin_count=content_item.get("repin_count", 0),
            comment_count=content_item.get("comment_count", 0),
            share_count=content_item.get("share_count", 0),
            ip_location=content_item.get("ip_location", ""),
            publish_time=content_item.get("publish_time", 0),
            create_time=content_item.get("create_time", ""),
            media_id=content_item.get("media_id", ""),
            media_name=content_item.get("media_name", ""),
            source_keyword=content_item.get("source_keyword", ""),
            detail_fetched=1 if content_item.get("detail_fetched") else 0,
            add_ts=add_ts,
            last_modify_ts=last_modify_ts,
        )
        session.add(article)

    async def update_content(self, session: AsyncSession, content_item: Dict):
        article_id = content_item.get("article_id")
        last_modify_ts = int(get_current_timestamp())
        update_data = {
            "last_modify_ts": last_modify_ts,
            "title": content_item.get("title", ""),
            "content": content_item.get("content", ""),
            "abstract": content_item.get("abstract", ""),
            "nickname": content_item.get("nickname", ""),
            "read_count": content_item.get("read_count", 0),
            "like_count": content_item.get("like_count", 0),
            "digg_count": content_item.get("digg_count", 0),
            "comment_count": content_item.get("comment_count", 0),
            "share_count": content_item.get("share_count", 0),
            "publish_time": content_item.get("publish_time", 0),
            "create_time": content_item.get("create_time", ""),
            "image_list": content_item.get("image_list", "[]"),
        }
        stmt = update(ToutiaoArticle).where(ToutiaoArticle.article_id == article_id).values(**update_data)
        await session.execute(stmt)

    async def content_is_exist(self, session: AsyncSession, article_id: str) -> bool:
        stmt = select(ToutiaoArticle).where(ToutiaoArticle.article_id == article_id)
        result = await session.execute(stmt)
        return result.first() is not None

    async def store_comment(self, comment_item: Dict):
        """存储评论到数据库"""
        if not comment_item:
            return
        async with get_session() as session:
            comment_id = comment_item.get("comment_id")
            if not comment_id:
                return
            if await self.comment_is_exist(session, comment_id):
                await self.update_comment(session, comment_item)
            else:
                await self.add_comment(session, comment_item)

    async def add_comment(self, session: AsyncSession, comment_item: Dict):
        add_ts = int(get_current_timestamp())
        last_modify_ts = int(get_current_timestamp())

        # is_sub_comment 已经在上层转换为 0/1
        is_sub = comment_item.get("is_sub_comment", 0)
        parent_id = comment_item.get("parent_comment_id", "")

        comment = ToutiaoComment(
            comment_id=comment_item.get("comment_id"),
            article_id=comment_item.get("article_id", ""),
            content=comment_item.get("content", ""),
            create_time=comment_item.get("create_time", 0),
            like_count=comment_item.get("like_count", 0),
            reply_count=comment_item.get("reply_count", 0),
            is_sub_comment=is_sub,
            user_id=comment_item.get("user_id", ""),
            nickname=comment_item.get("nickname", ""),
            avatar=comment_item.get("avatar", ""),
            parent_comment_id=parent_id,
            reply_to_user_id=comment_item.get("reply_to_user_id", ""),
            reply_to_nickname=comment_item.get("reply_to_nickname", ""),
            add_ts=add_ts,
            last_modify_ts=last_modify_ts,
        )
        session.add(comment)

    async def update_comment(self, session: AsyncSession, comment_item: Dict):
        comment_id = comment_item.get("comment_id")
        last_modify_ts = int(get_current_timestamp())
        update_data = {
            "last_modify_ts": last_modify_ts,
            "content": comment_item.get("content", ""),
            "like_count": comment_item.get("like_count", 0),
            "reply_count": comment_item.get("reply_count", 0),
        }
        stmt = update(ToutiaoComment).where(ToutiaoComment.comment_id == comment_id).values(**update_data)
        await session.execute(stmt)

    async def comment_is_exist(self, session: AsyncSession, comment_id: str) -> bool:
        stmt = select(ToutiaoComment).where(ToutiaoComment.comment_id == comment_id)
        result = await session.execute(stmt)
        return result.first() is not None

    async def store_creator(self, creator_item: Dict):
        """存储创作者信息到数据库"""
        creator_id = creator_item.get("creator_id")
        if not creator_id:
            return
        async with get_session() as session:
            if await self.creator_is_exist(session, creator_id):
                await self.update_creator(session, creator_item)
            else:
                await self.add_creator(session, creator_item)

    async def add_creator(self, session: AsyncSession, creator_item: Dict):
        add_ts = int(get_current_timestamp())
        last_modify_ts = int(get_current_timestamp())
        creator = ToutiaoCreator(
            creator_id=creator_item.get("creator_id"),
            nickname=creator_item.get("nickname", ""),
            avatar=creator_item.get("avatar", ""),
            description=creator_item.get("description", ""),
            follow_count=creator_item.get("follow_count", 0),
            fans_count=creator_item.get("fans_count", 0),
            add_ts=add_ts,
            last_modify_ts=last_modify_ts,
        )
        session.add(creator)

    async def update_creator(self, session: AsyncSession, creator_item: Dict):
        creator_id = creator_item.get("creator_id")
        last_modify_ts = int(get_current_timestamp())
        update_data = {
            "last_modify_ts": last_modify_ts,
            "nickname": creator_item.get("nickname", ""),
            "avatar": creator_item.get("avatar", ""),
            "description": creator_item.get("description", ""),
            "follow_count": creator_item.get("follow_count", 0),
            "fans_count": creator_item.get("fans_count", 0),
        }
        stmt = update(ToutiaoCreator).where(ToutiaoCreator.creator_id == creator_id).values(**update_data)
        await session.execute(stmt)

    async def creator_is_exist(self, session: AsyncSession, creator_id: str) -> bool:
        stmt = select(ToutiaoCreator).where(ToutiaoCreator.creator_id == creator_id)
        result = await session.execute(stmt)
        return result.first() is not None

    def flush(self):
        pass


class ToutiaoSqliteStoreImplement(ToutiaoDbStoreImplement):
    """SQLite存储实现"""
    pass


class ToutiaoMongoStoreImplement(AbstractStore):
    """MongoDB存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def store_content(self, content_item: Dict):
        """存储文章内容到MongoDB"""
        article_id = content_item.get("article_id")
        if not article_id:
            return
        utils.logger.info(f"[ToutiaoMongoStoreImplement.store_content] 存储文章到MongoDB: {article_id}")
        # TODO: 实现MongoDB存储

    async def store_comment(self, comment_item: Dict):
        """存储评论到MongoDB"""
        comment_id = comment_item.get("comment_id")
        if not comment_id:
            return
        utils.logger.info(f"[ToutiaoMongoStoreImplement.store_comment] 存储评论到MongoDB: {comment_id}")
        # TODO: 实现MongoDB存储

    async def store_creator(self, creator_item: Dict):
        """存储创作者信息到MongoDB"""
        creator_id = creator_item.get("creator_id")
        if not creator_id:
            return
        utils.logger.info(f"[ToutiaoMongoStoreImplement.store_creator] 存储创作者到MongoDB: {creator_id}")
        # TODO: 实现MongoDB存储

    def flush(self):
        pass


class ToutiaoExcelStoreImplement:
    """Excel存储实现 - 全局单例"""

    def __new__(cls, *args, **kwargs):
        return ExcelStoreBase.get_instance(
            platform="toutiao",
            crawler_type=crawler_type_var.get()
        )

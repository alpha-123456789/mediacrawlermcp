# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/tieba/client.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当目的。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import re
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote

import httpx
from aiotieba.helper.crypto import sign as aiotieba_sign
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

import config
from base.base_crawler import AbstractApiClient
from model.m_baidu_tieba import TiebaComment, TiebaNote
from proxy.proxy_ip_pool import ProxyIpPool
from tools import utils

from .field import SearchNoteType, SearchSortType


class BaiduTieBaClient(AbstractApiClient):

    def __init__(
        self,
        timeout=10,
        ip_pool=None,
        default_ip_proxy=None,
        headers: Dict[str, str] = None,
        playwright_page=None,  # kept for interface compat, no longer used
    ):
        self.ip_pool: Optional[ProxyIpPool] = ip_pool
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": utils.get_user_agent(),
        }
        self._host = "https://tieba.baidu.com"
        self.default_ip_proxy = default_ip_proxy
        self.playwright_page = playwright_page

    # ------------------------------------------------------------------
    #  Search API  /mo/q/search/thread  (no auth needed)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def get_notes_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        sort: SearchSortType = SearchSortType.TIME_DESC,
        note_type: SearchNoteType = SearchNoteType.FIXED_THREAD,
    ) -> List[TiebaNote]:
        """
        Search Tieba posts by keyword using /mo/q/search/thread API.
        No login or sign required.
        """
        params = {
            "rn": str(page_size),
            "st": sort.value,
            "word": keyword,
            "pn": str(page),
        }
        url = f"{self._host}/mo/q/search/thread?{urlencode(params)}"
        utils.logger.info(f"[BaiduTieBaClient.get_notes_by_keyword] API request: {url}")

        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.default_ip_proxy) as client:
            resp = await client.get(url, headers=self.headers)

        if resp.status_code != 200:
            raise Exception(f"Search API returned status {resp.status_code}")

        data = resp.json()
        if data.get("no") != 0:
            raise Exception(f"Search API error: {data.get('error', 'unknown')}")

        post_list = data.get("data", {}).get("post_list", [])
        # API may return more items than requested rn; truncate
        if len(post_list) > page_size:
            post_list = post_list[:page_size]

        notes: List[TiebaNote] = []

        for post in post_list:
            tid = str(post.get("tid", ""))
            title = post.get("title", "")
            content = post.get("content", "")
            post_num = post.get("post_num", 0)
            like_num = post.get("like_num", 0)
            create_time = post.get("create_time", 0)
            forum_name = post.get("forum_name", "")
            forum_id = post.get("forum_id", 0)
            pb_url = post.get("pb_url", "")

            user_info = post.get("user", {})
            user_nickname = user_info.get("show_nickname", user_info.get("user_name", ""))
            user_id = user_info.get("user_id", "")
            portrait = user_info.get("portrait", "")
            user_avatar = f"https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/{portrait}" if portrait else ""

            publish_time = ""
            if create_time:
                try:
                    publish_time = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    publish_time = str(create_time)

            tieba_link = f"{self._host}/f?kw={quote(forum_name)}" if forum_name else ""
            note_url = pb_url or f"{self._host}/p/{tid}"

            notes.append(TiebaNote(
                note_id=tid,
                title=title,
                desc=content[:500] if content else "",
                note_url=note_url,
                publish_time=publish_time,
                user_link=f"{self._host}/home/main?id={portrait}" if portrait else "",
                user_nickname=user_nickname,
                user_avatar=user_avatar,
                tieba_name=forum_name,
                tieba_link=tieba_link,
                total_replay_num=post_num,
                total_replay_page=(post_num + 9) // 10 if post_num else 0,
                like_count=like_num,
                ip_location="",
            ))

        utils.logger.info(f"[BaiduTieBaClient.get_notes_by_keyword] Got {len(notes)} posts")
        return notes

    # ------------------------------------------------------------------
    #  Detail + Comments API  /c/f/pb/page  (aiotieba sign, no login)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def get_note_by_id(self, note_id: str) -> TiebaNote:
        """
        Get post detail using /c/f/pb/page API with aiotieba sign.
        Also fetches first-page comments with embedded sub-comments.
        """
        page_data, user_map = await self._fetch_page(note_id, pn=1, rn=30)

        thread = page_data.get("thread", {})
        forum = page_data.get("forum", {})
        first_floor = page_data.get("first_floor", {})
        post_list = page_data.get("post_list", [])

        # Thread info
        title = thread.get("title", "") or first_floor.get("title", "")
        reply_num = thread.get("reply_num", 0)
        agree_num = thread.get("agree_num", 0)
        collect_num = thread.get("collect_num", 0)
        create_time = thread.get("create_time", 0)

        # First floor (OP) content — may be in first_floor or in post_list[0]
        ff_content_items = first_floor.get("content", [])
        if not ff_content_items and post_list:
            ff_content_items = post_list[0].get("content", [])
        desc = self._extract_text(ff_content_items)

        # OP author — try thread.author first, then first_floor, then post_list[0]
        author_info = thread.get("author") or first_floor.get("author")
        if not author_info and post_list:
            author_info = post_list[0].get("author")
        ff_author_id = first_floor.get("author_id")
        if not author_info and ff_author_id:
            author_info = user_map.get(ff_author_id, {})

        user_nickname = self._get_author_name(author_info)
        portrait = (author_info or {}).get("portrait", "")
        user_avatar = f"https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/{portrait}" if portrait else ""
        ip_location = (author_info or {}).get("ip_address", "") or ""

        publish_time = ""
        if create_time:
            try:
                publish_time = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                publish_time = str(create_time)

        forum_name = forum.get("name", "")
        forum_id = forum.get("id", 0)
        tieba_link = f"{self._host}/f?kw={quote(forum_name)}" if forum_name else ""

        return TiebaNote(
            note_id=str(note_id),
            title=title,
            desc=desc,
            note_url=f"{self._host}/p/{note_id}",
            publish_time=publish_time,
            user_link=f"{self._host}/home/main?id={portrait}" if portrait else "",
            user_nickname=user_nickname,
            user_avatar=user_avatar,
            tieba_name=forum_name,
            tieba_link=tieba_link,
            total_replay_num=reply_num,
            total_replay_page=page_data.get("page", {}).get("total_page", 0),
            like_count=agree_num,
            collect_count=collect_num,
            ip_location=ip_location,
        )

    async def get_note_all_comments(
        self,
        note_detail: TiebaNote,
        crawl_interval: float = 1.0,
        callback=None,
        max_count: int = 10,
        max_sub_comments_count: Optional[int] = None,
    ) -> List[TiebaComment]:
        """
        Get comments using /c/f/pb/page API with aiotieba sign.
        Paginates through comment pages. Each page returns comments
        with a few embedded sub-comments (with_floor=1).
        """
        result: List[TiebaComment] = []
        total_pages = note_detail.total_replay_page
        if total_pages == 0 and note_detail.total_replay_num > 0:
            total_pages = (note_detail.total_replay_num + 29) // 30

        current_page = 1
        while current_page <= total_pages and len(result) < max_count:
            try:
                page_data, user_map = await self._fetch_page(
                    note_detail.note_id, pn=current_page, rn=30
                )
                post_list = page_data.get("post_list", [])

                if not post_list:
                    break

                comments = self._parse_comments(
                    post_list, user_map, note_detail
                )

                # Limit
                remaining = max_count - len(result)
                comments = comments[:remaining]

                if callback:
                    await callback(note_detail.note_id, comments)

                result.extend(comments)
                current_page += 1

                import asyncio
                await asyncio.sleep(crawl_interval)

            except Exception as e:
                utils.logger.error(
                    f"[BaiduTieBaClient.get_note_all_comments] Page {current_page} failed: {e}"
                )
                break

        utils.logger.info(
            f"[BaiduTieBaClient.get_note_all_comments] Got {len(result)} comments for note {note_detail.note_id}"
        )
        return result

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_page(
        self, kz: str, pn: int = 1, rn: int = 30
    ) -> tuple:
        """
        Fetch a page from /c/f/pb/page with aiotieba sign.
        Returns (cleaned_json_dict, user_map).
        """
        data = [
            ("kz", str(kz)),
            ("pn", str(pn)),
            ("rn", str(rn)),
            ("with_floor", "1"),
        ]
        signed_data = aiotieba_sign(data)
        form_data = {k: v for k, v in signed_data}

        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.default_ip_proxy) as client:
            resp = await client.post(
                f"{self._host}/c/f/pb/page",
                data=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "User-Agent": self.headers.get("User-Agent", "aiotieba/4.6.4"),
                },
            )

        if resp.status_code != 200:
            raise Exception(f"Page API returned status {resp.status_code}")

        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", resp.text)
        d = __import__("json").loads(cleaned)

        error_code = d.get("error_code")
        if error_code and error_code != 0:
            raise Exception(f"Page API error_code={error_code}, msg={d.get('error_msg', '')}")

        user_list = d.get("user_list", [])
        user_map = {u.get("id"): u for u in user_list}

        return d, user_map

    def _parse_comments(
        self,
        post_list: list,
        user_map: dict,
        note_detail: TiebaNote,
    ) -> List[TiebaComment]:
        """Parse post_list from /c/f/pb/page into TiebaComment objects."""
        comments: List[TiebaComment] = []

        for post in post_list:
            pid = str(post.get("id", ""))
            author_id = post.get("author_id")
            content_items = post.get("content", [])
            text = self._extract_text(content_items)
            timestamp = post.get("time", 0)
            agree = post.get("agree", {})
            agree_num = agree.get("agree_num", 0) if isinstance(agree, dict) else 0
            sub_post_number = post.get("sub_post_number", 0)

            # Author info — prefer inline author, fallback to user_map
            author = post.get("author") or user_map.get(author_id, {})
            user_nickname = self._get_author_name(author)
            portrait = (author or {}).get("portrait", "")
            user_avatar = f"https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/{portrait}" if portrait else ""
            ip_location = (author or {}).get("ip_address", "") or ""

            publish_time = ""
            if timestamp:
                try:
                    publish_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    publish_time = str(timestamp)

            # Parse embedded sub-comments
            sub_comments: List[TiebaComment] = []
            sub_post_data = post.get("sub_post_list")
            if isinstance(sub_post_data, dict):
                for sp in sub_post_data.get("sub_post_list", []):
                    sp_id = str(sp.get("id", ""))
                    sp_author = sp.get("author") or {}
                    sp_nickname = self._get_author_name(sp_author)
                    sp_portrait = sp_author.get("portrait", "")
                    sp_avatar = f"https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/{sp_portrait}" if sp_portrait else ""
                    sp_ip = sp_author.get("ip_address", "") or ""
                    sp_text = self._extract_text(sp.get("content", []))
                    sp_time = sp.get("time", 0)
                    sp_time_str = ""
                    if sp_time:
                        try:
                            sp_time_str = datetime.fromtimestamp(sp_time).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            sp_time_str = str(sp_time)
                    sp_agree = sp.get("agree", {})
                    sp_agree_num = sp_agree.get("agree_num", 0) if isinstance(sp_agree, dict) else 0

                    sub_comments.append(TiebaComment(
                        comment_id=sp_id,
                        content=sp_text,
                        user_nickname=sp_nickname,
                        user_avatar=sp_avatar,
                        publish_time=sp_time_str,
                        ip_location=sp_ip,
                        like_count=sp_agree_num,
                        note_id=note_detail.note_id,
                        note_url=note_detail.note_url,
                        tieba_id=str(note_detail.tieba_link.split("kw=")[-1]) if "kw=" in note_detail.tieba_link else "",
                        tieba_name=note_detail.tieba_name,
                        tieba_link=note_detail.tieba_link,
                    ))

            comments.append(TiebaComment(
                comment_id=pid,
                content=text,
                user_nickname=user_nickname,
                user_avatar=user_avatar,
                publish_time=publish_time,
                ip_location=ip_location,
                sub_comment_count=sub_post_number,
                sub_comment_list=sub_comments,
                like_count=agree_num,
                note_id=note_detail.note_id,
                note_url=note_detail.note_url,
                tieba_id=str(note_detail.tieba_link.split("kw=")[-1]) if "kw=" in note_detail.tieba_link else "",
                tieba_name=note_detail.tieba_name,
                tieba_link=note_detail.tieba_link,
            ))

        return comments

    @staticmethod
    def _extract_text(content_items: list) -> str:
        """Extract plain text from content item list."""
        parts = []
        for item in content_items:
            if isinstance(item, dict) and item.get("type") == 0:
                parts.append(item.get("text", ""))
        return "\n".join(parts) if parts else ""

    @staticmethod
    def _get_author_name(author_info: Optional[dict]) -> str:
        """Extract display name from author info dict."""
        if not author_info:
            return ""
        return author_info.get("name_show") or author_info.get("name", "")

    # ------------------------------------------------------------------
    #  Legacy methods kept for interface compatibility (creator mode, etc.)
    # ------------------------------------------------------------------

    async def pong(self, browser_context=None) -> bool:
        """API mode does not require login, always returns True."""
        return True

    async def request(self, method, url, **kwargs):
        """Generic HTTP request method (required by AbstractApiClient)."""
        async with httpx.AsyncClient(timeout=self.timeout, proxy=self.default_ip_proxy) as client:
            resp = await client.request(method, url, headers=self.headers, **kwargs)
        if resp.status_code != 200:
            raise Exception(f"Request failed: {method} {url} -> {resp.status_code}")
        return resp.json()

    async def update_cookies(self, browser_context=None):
        """No-op in API mode."""
        pass

    async def get_comments_all_sub_comments(
        self,
        comments: List[TiebaComment],
        crawl_interval: float = 1.0,
        callback=None,
        max_count: int = None,
    ) -> Dict[str, List[TiebaComment]]:
        """
        Sub-comments are already embedded via with_floor=1.
        No additional fetching needed.
        """
        return {}

    async def get_notes_by_tieba_name(self, tieba_name: str, page_num: int) -> List[TiebaNote]:
        """Not yet implemented for API mode."""
        raise NotImplementedError("get_notes_by_tieba_name not yet implemented for API mode")

    async def get_creator_info_by_url(self, creator_url: str) -> str:
        """Not yet implemented for API mode."""
        raise NotImplementedError("get_creator_info_by_url not yet implemented for API mode")

    async def get_notes_by_creator(self, user_name: str, page_number: int) -> Dict:
        """Not yet implemented for API mode."""
        raise NotImplementedError("get_notes_by_creator not yet implemented for API mode")

    async def get_all_notes_by_creator_user_name(self, *args, **kwargs):
        """Not yet implemented for API mode."""
        raise NotImplementedError("get_all_notes_by_creator_user_name not yet implemented for API mode")

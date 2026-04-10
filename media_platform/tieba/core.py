# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/tieba/core.py
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


import asyncio
from typing import Dict, List, Optional

import config
from base.base_crawler import AbstractCrawler
from model.m_baidu_tieba import TiebaNote
from tools import utils
from var import crawler_type_var, source_keyword_var

from .client import BaiduTieBaClient
from .field import SearchNoteType, SearchSortType


class TieBaCrawler(AbstractCrawler):
    tieba_client: BaiduTieBaClient

    def __init__(self) -> None:
        self.user_agent = utils.get_user_agent()
        self.results = {"notes": [], "comments": {}}

    async def start(self) -> list[dict]:
        """
        Start the crawler.
        Search and detail modes now use pure HTTP APIs — no Playwright needed.
        """
        # Create client directly (no browser needed for API mode)
        httpx_proxy = None
        ip_proxy_pool = None
        if config.ENABLE_IP_PROXY:
            from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
            from tools import utils as u
            utils.logger.info("[TieBaCrawler.start] Creating IP proxy pool...")
            ip_proxy_pool = await create_ip_pool(
                config.IP_PROXY_POOL_COUNT, enable_validate_ip=True
            )
            ip_proxy_info: IpInfoModel = await ip_proxy_pool.get_proxy()
            _, httpx_proxy = u.format_proxy_info(ip_proxy_info)

        self.tieba_client = BaiduTieBaClient(
            timeout=10,
            ip_pool=ip_proxy_pool,
            default_ip_proxy=httpx_proxy,
            headers={"User-Agent": self.user_agent},
        )

        crawler_type_var.set(config.CRAWLER_TYPE)

        if config.CRAWLER_TYPE == "search":
            await self.search()
        elif config.CRAWLER_TYPE == "detail":
            await self.get_specified_notes()
        elif config.CRAWLER_TYPE == "creator":
            raise NotImplementedError(
                "Creator mode is not yet supported in API mode. "
                "Use search or detail mode instead."
            )
        else:
            pass

        utils.logger.info("[TieBaCrawler.start] Tieba Crawler finished")

        for note in self.results["notes"]:
            note_id = note.get("note_id")
            note["comments"] = self.results["comments"].get(note_id, [])
        return self.results["notes"]

    async def search(self) -> None:
        """
        Search for notes using /mo/q/search/thread API.
        Then fetch details + comments via /c/f/pb/page API.
        """
        utils.logger.info("[TieBaCrawler.search] Begin search baidu tieba keywords")
        start_page = config.START_PAGE

        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[TieBaCrawler.search] Keyword: {keyword}")

            page = 1
            while (page - start_page) * 20 < config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    page += 1
                    continue
                try:
                    utils.logger.info(
                        f"[TieBaCrawler.search] keyword={keyword}, page={page}"
                    )
                    notes_list: List[TiebaNote] = (
                        await self.tieba_client.get_notes_by_keyword(
                            keyword=keyword,
                            page=page,
                            page_size=20,
                            sort=SearchSortType.TIME_DESC,
                        )
                    )
                    if not notes_list:
                        utils.logger.info("[TieBaCrawler.search] No results, stopping")
                        break

                    utils.logger.info(
                        f"[TieBaCrawler.search] Got {len(notes_list)} posts"
                    )
                    await self.get_specified_notes(
                        note_id_list=[n.note_id for n in notes_list]
                    )

                    if len(self.results["notes"]) >= config.CRAWLER_MAX_NOTES_COUNT:
                        break

                    page += 1
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

                except Exception as ex:
                    utils.logger.error(
                        f"[TieBaCrawler.search] Error on page {page}, keyword {keyword}: {ex}"
                    )
                    break

    async def launch_browser(self, chromium=None, playwright_proxy=None, user_agent=None, headless=True):
        """Not needed in API mode. Kept for AbstractCrawler compatibility."""
        raise NotImplementedError("Browser not needed in API mode")

    async def get_specified_notes(
        self, note_id_list: List[str] = config.TIEBA_SPECIFIED_ID_LIST
    ):
        """
        Fetch detail + comments for specified note IDs.
        """
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self._get_note_detail_task(note_id=note_id, semaphore=semaphore)
            for note_id in note_id_list
        ]
        note_details = await asyncio.gather(*task_list)
        note_details_valid: List[TiebaNote] = []

        for note_detail in note_details:
            if note_detail is None:
                continue
            if len(self.results["notes"]) >= config.CRAWLER_MAX_NOTES_COUNT:
                break
            note_details_valid.append(note_detail)
            self.results["notes"].append(
                note_detail.model_dump() if hasattr(note_detail, "model_dump") else note_detail.dict()
            )
            try:
                from store import tieba as tieba_store
                await tieba_store.update_tieba_note(note_detail)
            except Exception as db_err:
                utils.logger.warning(f"[TieBaCrawler] DB save failed: {db_err}")

        await self._batch_get_note_comments(note_details_valid)

    async def _get_note_detail_task(
        self, note_id: str, semaphore: asyncio.Semaphore
    ) -> Optional[TiebaNote]:
        async with semaphore:
            try:
                utils.logger.info(f"[TieBaCrawler] Fetching detail: {note_id}")
                note_detail = await self.tieba_client.get_note_by_id(note_id)
                if not note_detail:
                    utils.logger.error(f"[TieBaCrawler] No detail for {note_id}")
                    return None
                return note_detail
            except Exception as ex:
                utils.logger.error(f"[TieBaCrawler] Detail error for {note_id}: {ex}")
                return None

    async def _batch_get_note_comments(self, note_detail_list: List[TiebaNote]):
        """
        Fetch comments for all notes concurrently.
        """
        if not config.ENABLE_GET_COMMENTS:
            return

        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = [
            self._get_comments_task(note_detail, semaphore)
            for note_detail in note_detail_list
        ]
        await asyncio.gather(*task_list)

    async def _get_comments_task(
        self, note_detail: TiebaNote, semaphore: asyncio.Semaphore
    ):
        async with semaphore:
            utils.logger.info(
                f"[TieBaCrawler] Fetching comments for {note_detail.note_id}"
            )
            try:
                comments = await self.tieba_client.get_note_all_comments(
                    note_detail=note_detail,
                    crawl_interval=config.CRAWLER_MAX_SLEEP_SEC,
                    max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                    max_sub_comments_count=config.CRAWLER_MAX_SUB_COMMENTS_COUNT_SINGLENOTES,
                )
                self.results["comments"][note_detail.note_id] = [
                    c.model_dump() if hasattr(c, "model_dump") else c.dict()
                    for c in comments
                ] if comments else []
            except Exception as ex:
                utils.logger.error(
                    f"[TieBaCrawler] Comments error for {note_detail.note_id}: {ex}"
                )

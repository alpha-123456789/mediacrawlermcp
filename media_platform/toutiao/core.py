# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条爬虫主逻辑
"""

import asyncio
import os
import random
from asyncio import Task
from typing import Dict, List, Optional, Tuple

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import toutiao as toutiao_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import ToutiaoClient
from .exception import DataFetchError
from .field import SearchOrderType
from .help import parse_article_id_from_url, parse_creator_id_from_url, clean_html_content, extract_content_text_from_html, extract_create_time_from_html
from .login import ToutiaoLogin


class ToutiaoCrawler(AbstractCrawler):
    """今日头条爬虫"""

    context_page: Page
    tt_client: ToutiaoClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]

    def __init__(self):
        self.index_url = "https://www.toutiao.com"
        self.user_agent = utils.get_user_agent()
        self.cdp_manager = None
        self.ip_proxy_pool = None
        self.results = {"notes": [], "comments": {}}

    def _filter_note(self, note: Dict) -> Dict:
        """过滤文章数据，只保留必要字段"""
        if not note:
            return {}

        user_data = note.get("user", {})
        filtered = {
            # 文章基本信息
            "article_id": note.get("article_id", ""),
            "title": note.get("title", ""),
            "content": note.get("content", ""),
            "abstract": note.get("abstract", ""),
            "source": note.get("source", ""),
            "author": note.get("author", ""),
            "url": note.get("url", ""),
            # 时间
            "create_time": note.get("create_time", ""),
            "publish_time": note.get("publish_time", 0),
            "publish_time_text": note.get("publish_time_text", ""),
            # 互动数据
            "read_count": note.get("read_count", 0),
            "like_count": note.get("like_count", 0),
            "comment_count": note.get("comment_count", 0),
            "share_count": note.get("share_count", 0),
            # 媒体信息
            "has_video": note.get("has_video", False),
            "has_image": note.get("has_image", False),
            "video_duration": note.get("video_duration", 0),
            "ip_location": note.get("ip_location", ""),
            "source_keyword": note.get("source_keyword", ""),
            # 用户信息（多渠道获取）
            "user": {
                "user_id": user_data.get("user_id") or note.get("user_id", ""),
                "nickname": user_data.get("name") or note.get("nickname") or note.get("author", ""),
                "avatar": user_data.get("avatar_url") or note.get("avatar", ""),
            },
            # 评论（过滤后）
            "comments": [self._filter_comment(c) for c in note.get("comments", [])],
        }
        return filtered

    def _filter_comment(self, comment: Dict) -> Dict:
        """过滤评论数据，只保留必要字段"""
        if not comment:
            return {}

        user_data = comment.get("user", {})
        filtered = {
            "comment_id": comment.get("comment_id", ""),
            "content": comment.get("content", ""),
            "create_time": comment.get("create_time", 0),
            "like_count": comment.get("like_count", 0),
            "reply_count": comment.get("reply_count", 0),
            "ip_location": comment.get("ip_location", ""),
            "is_sub_comment": comment.get("is_sub_comment", False),
            "parent_id": comment.get("parent_id"),
            # 用户信息
            "user": {
                "user_id": user_data.get("user_id", ""),
                "nickname": user_data.get("nickname", ""),
                "avatar": user_data.get("avatar", ""),
            },
        }

        # 处理子评论
        sub_comments = comment.get("sub_comments", [])
        if sub_comments:
            filtered["sub_comments"] = [self._filter_sub_comment(c) for c in sub_comments]

        return filtered

    def _filter_sub_comment(self, sub_comment: Dict) -> Dict:
        """过滤子评论数据"""
        if not sub_comment:
            return {}

        user_data = sub_comment.get("user", {})
        return {
            "comment_id": sub_comment.get("comment_id", ""),
            "content": sub_comment.get("content", ""),
            "create_time": sub_comment.get("create_time", 0),
            "like_count": sub_comment.get("like_count", 0),
            "reply_to_user_id": sub_comment.get("reply_to_user_id", ""),
            # 用户信息
            "user": {
                "user_id": user_data.get("user_id", ""),
                "nickname": user_data.get("nickname", ""),
                "avatar": user_data.get("avatar", ""),
            },
        }

    def _extract_text_from_html(self, html: str) -> str:
        """从HTML内容中提取纯文本"""
        if not html:
            return ""
        return clean_html_content(html)

    async def start(self) -> list[dict]:
        """爬虫入口"""
        # 保存当前任务以便检查取消状态
        self._main_task = asyncio.current_task()
        playwright_proxy_format, httpx_proxy_format = None, None

        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)

        async with async_playwright() as playwright:
            # 选择启动模式
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[ToutiaoCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[ToutiaoCrawler] 使用标准模式启动浏览器")
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(chromium, None, self.user_agent, headless=config.HEADLESS)
                await self.browser_context.add_init_script(path="libs/stealth.min.js")

            self.context_page = await self.browser_context.new_page()

            # 注入额外的反检测脚本（针对头条的检测）
            await self.context_page.add_init_script("""
                // 隐藏 webdriver 属性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                // 隐藏 automation 属性
                Object.defineProperty(navigator, 'automation', {
                    get: () => undefined
                });
                // 模拟真实 chrome
                window.chrome = {
                    runtime: {}
                };
                // 覆盖 permissions API
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                // 阻止页面缩放检测
                Object.defineProperty(window, 'devicePixelRatio', {
                    get: () => 1
                });
                // 固定视口大小，防止被检测为移动端
                Object.defineProperty(window, 'innerWidth', {
                    get: () => 1920
                });
                Object.defineProperty(window, 'innerHeight', {
                    get: () => 1080
                });
                Object.defineProperty(screen, 'width', {
                    get: () => 1920
                });
                Object.defineProperty(screen, 'height', {
                    get: () => 1080
                });
            """)

            # 绕过自动化检测后，等待一下再访问
            await asyncio.sleep(1)

            # 重试机制：网络连接可能被防火墙重置
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    await self.context_page.goto(
                        self.index_url,
                        timeout=60000,
                        wait_until="domcontentloaded"
                    )
                    break
                except Exception as e:
                    if "ERR_CONNECTION_RESET" in str(e) and attempt < max_retries - 1:
                        utils.logger.warning(f"[ToutiaoCrawler] 连接被重置，第 {attempt + 1} 次重试...")
                        await asyncio.sleep(2)
                    else:
                        raise

            # 创建API客户端
            self.tt_client = await self.create_toutiao_client(httpx_proxy_format)
            if not await self.tt_client.pong():
                login_obj = ToutiaoLogin(
                    login_type=config.LOGIN_TYPE,
                    login_phone="",
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                await self.tt_client.update_cookies(browser_context=self.browser_context)

            # 根据爬取类型执行不同逻辑
            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                await self.get_specified_articles(config.TOUTIAO_SPECIFIED_ID_LIST)
            elif config.CRAWLER_TYPE == "creator":
                await self.get_creators_and_articles()
            else:
                pass

            utils.logger.info("[ToutiaoCrawler.start] 今日头条爬虫执行完成")

            # 合并评论数据到文章
            for note in self.results["notes"]:
                article_id = note.get("article_id")
                note["comments"] = self.results["comments"].get(article_id, [])

            # 过滤返回数据，只保留必要字段
            filtered_notes = [self._filter_note(note) for note in self.results["notes"]]

            # 关闭浏览器
            await self.close()

            return filtered_notes

    async def search(self):
        """关键词搜索"""
        utils.logger.info("[ToutiaoCrawler.search] 开始搜索关键词")

        tt_limit_count = 20  # 每页固定数量
        start_page = config.START_PAGE

        for keyword in config.KEYWORDS.split(","):
            source_keyword_var.set(keyword)
            utils.logger.info(f"[ToutiaoCrawler.search] 当前搜索关键词: {keyword}")
            page = 1

            while (page - start_page) * tt_limit_count < config.CRAWLER_MAX_NOTES_COUNT:
                if page < start_page:
                    utils.logger.info(f"[ToutiaoCrawler.search] 跳过第 {page} 页")
                    page += 1
                    continue

                utils.logger.info(f"[ToutiaoCrawler.search] 搜索关键词: {keyword}, 页码: {page}")

                max_search_retries = 5
                search_attempt = 0
                search_success = False

                while search_attempt < max_search_retries and not search_success:
                    try:
                        search_res = await self.tt_client.search_article_by_keyword(
                            keyword=keyword,
                            page=page,
                            page_size=tt_limit_count,
                            order=SearchOrderType.DEFAULT,
                        )
                        # 解析搜索结果
                        article_list = self.tt_client.parse_search_results(search_res)

                        # 如果返回空数据，不重试，直接继续（或结束）
                        if not article_list:
                            utils.logger.info(f"[ToutiaoCrawler.search] 关键词 '{keyword}' 没有更多结果")
                            search_success = True  # 正常获取，不重试
                            break

                        article_id_list: List[str] = []

                        # 提前限制文章数量，避免获取多余详情
                        remaining_slots = config.CRAWLER_MAX_NOTES_COUNT - len(self.results["notes"])
                        if remaining_slots <= 0:
                            break
                        if len(article_list) > remaining_slots:
                            article_list = article_list[:remaining_slots]

                        if config.ENABLE_FETCH_ARTICLE_DETAIL:
                            utils.logger.info(f"[ToutiaoCrawler.search] 获取到 {len(article_list)} 篇文章，开始获取详情...")

                            # 限制并发数获取文章详情
                            semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)

                            async def get_article_with_detail(article: Dict) -> Optional[Dict]:
                                """获取文章详情并合并数据"""
                                article_id = article.get("article_id")
                                if not article_id:
                                    return article

                                async with semaphore:
                                    try:
                                        utils.logger.info(f"[ToutiaoCrawler.search] 获取文章详情: {article_id}")
                                        # 添加35秒超时，防止单个详情卡住整个流程
                                        detail_res = await asyncio.wait_for(
                                            self.tt_client.get_article_detail(article_id),
                                            timeout=35
                                        )
                                        detail_data = detail_res.get("data", {})

                                        # 合并详情数据
                                        # 优先从详情获取 comment_count，如果没有则尝试使用搜索结果的
                                        comment_count = detail_data.get("comment_count", 0)
                                        if not comment_count and detail_data.get("total_number"):
                                            comment_count = detail_data.get("total_number")

                                        # 从 HTML 内容中提取纯文本和创建时间
                                        raw_content = detail_data.get("content", "")
                                        extracted_content = extract_content_text_from_html(raw_content)
                                        create_time = extract_create_time_from_html(raw_content)

                                        article.update({
                                            "title": detail_data.get("title") or article.get("title", ""),
                                            "content": extracted_content,
                                            "create_time": create_time,
                                            "abstract": detail_data.get("abstract") or article.get("abstract", ""),
                                            "source": detail_data.get("source") or detail_data.get("media_name") or article.get("source", ""),
                                            "author": detail_data.get("user", {}).get("name") or detail_data.get("author") or article.get("source", ""),
                                            "publish_time": detail_data.get("publish_time") or detail_data.get("behot_time") or 0,
                                            "read_count": detail_data.get("read_count", 0),
                                            "like_count": detail_data.get("digg_count") or detail_data.get("like_count", 0),
                                            "comment_count": comment_count,
                                            "share_count": detail_data.get("share_count", 0),
                                            "has_video": detail_data.get("has_video", False),
                                            "has_image": detail_data.get("has_image", False),
                                            "image_list": detail_data.get("image_list", []),
                                            "video_duration": detail_data.get("video_duration", 0),
                                            "user": detail_data.get("user", {}),
                                            "media_info": detail_data.get("media_info", {}),
                                            "detail_fetched": True,
                                        })

                                        await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                                    except asyncio.TimeoutError:
                                        utils.logger.warning(f"[ToutiaoCrawler.search] 获取详情超时: {article_id}")
                                        article["detail_fetched"] = False
                                    except Exception as e:
                                        utils.logger.warning(f"[ToutiaoCrawler.search] 获取详情失败: {article_id}, {e}")
                                        article["detail_fetched"] = False

                                return article

                            # 并发获取所有文章详情
                            detail_tasks = [get_article_with_detail(article) for article in article_list]
                            articles_with_detail = await asyncio.gather(*detail_tasks)
                        else:
                            utils.logger.info(f"[ToutiaoCrawler.search] 获取到 {len(article_list)} 篇文章（不获取详情，仅基础信息）")
                            articles_with_detail = article_list

                        for article in articles_with_detail:
                            if len(self.results["notes"]) >= config.CRAWLER_MAX_NOTES_COUNT:
                                break

                            if not article:
                                continue

                            self.results["notes"].append(article)
                            article_id = article.get("article_id")
                            if article_id:
                                article_id_list.append(article_id)

                            # 保存文章数据（包含详情）
                            await toutiao_store.update_toutiao_article(article)

                        page += 1
                        await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

                        # 批量获取评论
                        await self.batch_get_article_comments(article_id_list)

                        if len(self.results["notes"]) >= config.CRAWLER_MAX_NOTES_COUNT:
                            break

                        search_success = True  # 成功获取，不重试

                    except DataFetchError as e:
                        search_attempt += 1
                        if search_attempt < max_search_retries:
                            delay = 2 * (2 ** search_attempt) + random.uniform(0, 1)
                            utils.logger.warning(f"[ToutiaoCrawler.search] 错误重试 {search_attempt}/{max_search_retries}, 等待{delay:.2f}s... 错误: {e}")
                            await asyncio.sleep(delay)
                        else:
                            utils.logger.error(f"[ToutiaoCrawler.search] 搜索出错: {e}")
                            break
                    except Exception as e:
                        search_attempt += 1
                        if search_attempt < max_search_retries:
                            delay = 2 * (2 ** search_attempt) + random.uniform(0, 1)
                            utils.logger.warning(f"[ToutiaoCrawler.search] 异常重试 {search_attempt}/{max_search_retries}, 等待{delay:.2f}s... 异常: {e}")
                            await asyncio.sleep(delay)
                        else:
                            utils.logger.error(f"[ToutiaoCrawler.search] 未知错误: {e}")
                            break

    async def get_specified_articles(self, article_id_list: List[str]):
        """获取指定文章详情"""
        utils.logger.info("[ToutiaoCrawler.get_specified_articles] 获取指定文章详情")

        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list = []

        for article_id in article_id_list:
            task = self.get_article_info_task(article_id, semaphore)
            task_list.append(task)

        article_details = await asyncio.gather(*task_list)

        valid_article_ids = []
        for article in article_details:
            if article:
                self.results["notes"].append(article)
                article_id = article.get("article_id")
                if article_id:
                    valid_article_ids.append(article_id)
                await toutiao_store.update_toutiao_article(article)

        await self.batch_get_article_comments(valid_article_ids)

    async def get_article_info_task(self, article_id: str, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """获取文章详情任务"""
        async with semaphore:
            max_retries = 5
            attempt = 0

            while attempt < max_retries:
                try:
                    result = await self.tt_client.get_article_detail(article_id)

                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                    utils.logger.info(f"[ToutiaoCrawler.get_article_info_task] 获取文章详情: {article_id}")

                    # 解析返回的数据
                    data = result.get("data", {})

                    # 如果返回空数据，不重试直接返回
                    if not data or not isinstance(data, dict):
                        utils.logger.warning(f"[ToutiaoCrawler.get_article_info_task] 返回空数据: {article_id}")
                        return None

                    if isinstance(data, dict):
                        raw_content = data.get("content", "")
                        extracted_content = extract_content_text_from_html(raw_content)
                        create_time = extract_create_time_from_html(raw_content)

                        article = {
                            "article_id": article_id,
                            "title": data.get("title", ""),
                            "content": extracted_content,
                            "create_time": create_time,
                            "author": data.get("author", data.get("media_name", "")),
                            "publish_time": data.get("publish_time", 0),
                            "read_count": data.get("read_count", 0),
                            "like_count": data.get("like_count", 0),
                            "comment_count": data.get("comment_count", 0),
                            "url": f"https://www.toutiao.com/article/{article_id}/",
                            "raw_data": data,
                        }
                        return article

                    return result

                except DataFetchError as ex:
                    attempt += 1
                    if attempt < max_retries:
                        delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                        utils.logger.warning(f"[ToutiaoCrawler.get_article_info_task] 错误重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 文章: {article_id}, 错误: {ex}")
                        await asyncio.sleep(delay)
                    else:
                        utils.logger.error(f"[ToutiaoCrawler.get_article_info_task] 获取文章详情失败: {ex}")
                        return None
                except Exception as e:
                    attempt += 1
                    if attempt < max_retries:
                        delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                        utils.logger.warning(f"[ToutiaoCrawler.get_article_info_task] 异常重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 文章: {article_id}, 异常: {e}")
                        await asyncio.sleep(delay)
                    else:
                        utils.logger.error(f"[ToutiaoCrawler.get_article_info_task] 未知错误: {e}")
                        return None

    async def batch_get_article_comments(self, article_id_list: List[str]):
        """批量获取文章评论"""
        if not config.ENABLE_GET_COMMENTS:
            utils.logger.info("[ToutiaoCrawler.batch_get_article_comments] 评论获取未启用")
            return

        utils.logger.info(f"[ToutiaoCrawler.batch_get_article_comments] 获取评论, 文章数: {len(article_id_list)}")

        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        task_list: List[Task] = []

        for article_id in article_id_list:
            task = asyncio.create_task(self.get_comments(article_id, semaphore), name=article_id)
            task_list.append(task)

        await asyncio.gather(*task_list)

    async def get_comments(self, article_id: str, semaphore: asyncio.Semaphore):
        """获取文章评论"""
        async with semaphore:
            try:
                utils.logger.info(f"[ToutiaoCrawler.get_comments] 开始获取评论: {article_id}")

                await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

                # 添加60秒超时，防止评论获取卡住
                comments = await asyncio.wait_for(
                    self.tt_client.get_article_all_comments(
                        article_id=article_id,
                        is_fetch_sub_comments=config.ENABLE_GET_SUB_COMMENTS,
                        callback=toutiao_store.batch_update_toutiao_comments,
                        sub_comments_callback=toutiao_store.batch_update_toutiao_subcomments,
                        max_count=config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES,
                        max_sub_comments_count=config.CRAWLER_MAX_SUB_COMMENTS_COUNT_SINGLENOTES,
                    ),
                    timeout=60
                )

                self.results["comments"][article_id] = comments
                # 统计子评论数量
                total_subcomments = sum(len(c.get("sub_comments", [])) for c in comments)
                utils.logger.info(f"[ToutiaoCrawler.get_comments] 获取评论完成: {article_id}, 共 {len(comments)} 条评论, {total_subcomments} 条子评论")

            except asyncio.TimeoutError:
                utils.logger.warning(f"[ToutiaoCrawler.get_comments] 获取评论超时: {article_id}")
                self.results["comments"][article_id] = []
            except DataFetchError as ex:
                utils.logger.error(f"[ToutiaoCrawler.get_comments] 获取评论失败: {article_id}, 错误: {ex}")
                self.results["comments"][article_id] = []
            except Exception as e:
                utils.logger.error(f"[ToutiaoCrawler.get_comments] 未知错误: {article_id}, 错误: {e}")
                self.results["comments"][article_id] = []

    async def get_creators_and_articles(self):
        """获取创作者及其文章"""
        utils.logger.info("[ToutiaoCrawler.get_creators_and_articles] 获取创作者信息")

        for creator_id in config.TOUTIAO_CREATOR_ID_LIST:
            try:
                # 获取创作者信息
                creator_info = await self.tt_client.get_creator_info(creator_id)
                utils.logger.info(f"[ToutiaoCrawler.get_creators_and_articles] 创作者: {creator_id}")

                if creator_info:
                    await toutiao_store.update_toutiao_creator(creator_info)

                # 获取创作者文章列表
                offset = 0
                count = 20
                article_id_list = []

                while len(article_id_list) < config.CRAWLER_MAX_NOTES_COUNT:
                    articles_res = await self.tt_client.get_creator_articles(
                        creator_id=creator_id,
                        offset=offset,
                        count=count,
                    )

                    articles = self.tt_client.parse_search_results(articles_res)
                    if not articles:
                        break

                    for article in articles:
                        if len(article_id_list) >= config.CRAWLER_MAX_NOTES_COUNT:
                            break

                        article_id = article.get("article_id")
                        if article_id:
                            article_id_list.append(article_id)
                            self.results["notes"].append(article)
                            await toutiao_store.update_toutiao_article(article)

                    offset += len(articles)
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)

                # 批量获取评论
                await self.batch_get_article_comments(article_id_list)

            except Exception as e:
                utils.logger.error(f"[ToutiaoCrawler.get_creators_and_articles] 获取创作者失败: {creator_id}, {e}")

    async def create_toutiao_client(self, httpx_proxy: Optional[str]) -> ToutiaoClient:
        """创建今日头条API客户端"""
        utils.logger.info("[ToutiaoCrawler.create_toutiao_client] 创建API客户端...")

        cookie_str, cookie_dict = utils.convert_cookies(await self.browser_context.cookies())

        client = ToutiaoClient(
            proxy=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Origin": "https://www.toutiao.com",
                "Referer": "https://www.toutiao.com/",
                "Content-Type": "application/json;charset=UTF-8",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
            proxy_ip_pool=self.ip_proxy_pool,
        )
        return client

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """启动浏览器"""
        utils.logger.info("[ToutiaoCrawler.launch_browser] 创建浏览器上下文...")

        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(os.getcwd(), "browser_data", config.USER_DATA_DIR % config.PLATFORM)
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,  # 禁用 Windows DPI 缩放
                user_agent=user_agent,
                channel="chrome",
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy, channel="chrome")
            browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,  # 禁用 Windows DPI 缩放
                user_agent=user_agent,
            )
            return browser_context

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """使用CDP模式启动浏览器"""
        try:
            self.cdp_manager = CDPBrowserManager()
            browser_context = await self.cdp_manager.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )

            browser_info = await self.cdp_manager.get_browser_info()
            utils.logger.info(f"[ToutiaoCrawler] CDP浏览器信息: {browser_info}")

            # 添加反检测脚本
            await browser_context.add_init_script(path="libs/stealth.min.js")

            # 添加额外的反检测脚本（针对头条）
            await browser_context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'automation', {
                    get: () => undefined
                });
                window.chrome = {
                    runtime: {}
                };
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            return browser_context

        except Exception as e:
            utils.logger.error(f"[ToutiaoCrawler] CDP模式启动失败，回退到标准模式: {e}")
            chromium = playwright.chromium
            return await self.launch_browser(chromium, playwright_proxy, user_agent, headless)

    async def close(self):
        """关闭浏览器"""
        try:
            # 先关闭页面再关闭上下文
            if hasattr(self, 'context_page') and self.context_page:
                try:
                    await self.context_page.close()
                    utils.logger.info("[ToutiaoCrawler.close] 页面已关闭")
                except Exception as e:
                    utils.logger.warning(f"[ToutiaoCrawler.close] 关闭页面时出错: {e}")

            if self.cdp_manager:
                try:
                    await self.cdp_manager.cleanup()
                    utils.logger.info("[ToutiaoCrawler.close] CDP管理器已清理")
                except Exception as e:
                    utils.logger.warning(f"[ToutiaoCrawler.close] 清理CDP管理器时出错: {e}")
                finally:
                    self.cdp_manager = None

            if self.browser_context:
                try:
                    await self.browser_context.close()
                    utils.logger.info("[ToutiaoCrawler.close] 浏览器上下文已关闭")
                except Exception as e:
                    utils.logger.warning(f"[ToutiaoCrawler.close] 关闭浏览器上下文时出错: {e}")
                finally:
                    self.browser_context = None

            utils.logger.info("[ToutiaoCrawler.close] 浏览器已关闭")
        except Exception as e:
            utils.logger.error(f"[ToutiaoCrawler.close] 关闭浏览器出错: {e}")

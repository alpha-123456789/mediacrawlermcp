# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条API客户端
"""

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractApiClient
from proxy.proxy_mixin import ProxyRefreshMixin
from tools import utils

if TYPE_CHECKING:
    from proxy.proxy_ip_pool import ProxyIpPool

from .exception import DataFetchError
from .field import CommentOrderType, SearchOrderType
from .help import clean_html_content, format_timestamp


class ToutiaoClient(AbstractApiClient, ProxyRefreshMixin):
    """今日头条API客户端"""

    def __init__(
        self,
        timeout=30,
        proxy=None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy_ip_pool: Optional["ProxyIpPool"] = None,
    ):
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://www.toutiao.com"
        self._search_host = "https://so.toutiao.com"
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self.init_proxy_pool(proxy_ip_pool)

    async def request(self, method, url, **kwargs) -> Any:
        """HTTP请求封装"""
        await self._refresh_proxy_if_expired()

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        try:
            data: Dict = response.json()
        except json.JSONDecodeError:
            utils.logger.error(f"[ToutiaoClient.request] JSON解析失败: {response.text[:200]}")
            raise DataFetchError(f"JSON解析失败: {response.text[:200]}")

        return data

    async def update_cookies(self, browser_context: BrowserContext):
        """更新cookies"""
        cookie_str, cookie_dict = utils.convert_cookies(await browser_context.cookies())
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict

    async def pong(self) -> bool:
        """检查登录状态"""
        utils.logger.info("[ToutiaoClient.pong] 检查登录状态...")
        try:
            # 首先检查是否有登录 Cookie (sessionid 是登录凭证)
            cookies = self.headers.get("Cookie", "")
            if "sessionid" not in cookies:
                utils.logger.info("[ToutiaoClient.pong] 未找到 sessionid Cookie，需要登录")
                return False
            return True
        except Exception as e:
            utils.logger.warning(f"[ToutiaoClient.pong] 登录状态检查失败: {e}")
        return False

    async def search_article_by_keyword(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        order: SearchOrderType = SearchOrderType.DEFAULT,
    ) -> Dict:
        """
        搜索文章/视频
        URL: https://so.toutiao.com/search
        注意：头条搜索返回的是 HTML 页面，需要用 Playwright 抓取
        :param keyword: 搜索关键词
        :param page: 页码
        :param page_size: 每页数量
        :param order: 排序方式
        :return: 搜索结果
        """
        # 搜索参数
        params = {
            "keyword": keyword,
            "pd": "synthesis",  # 综合搜索
            "dvpf": "pc",
            "action_type": "pagination",
            "source": "pagination",
            "from": "search_tab",
            "cur_tab_title": "search_tab",
            "offset": (page - 1) * page_size,
            "count": page_size,
            "filter_vendor":"site",
            "index_resource":"site",
            "filter_period":"all",
            "page_num":page - 1
        }

        # 添加排序参数
        if order == SearchOrderType.NEWEST:
            params["sort_by"] = "time"
        elif order == SearchOrderType.HOT:
            params["sort_by"] = "hot"

        url = f"{self._search_host}/search?{urlencode(params)}"
        utils.logger.info(f"[ToutiaoClient.search_article_by_keyword] 搜索url: {url}")

        try:
            # 使用 Playwright 页面访问（返回 HTML 而非 JSON）
            response = await self.playwright_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.playwright_page.wait_for_timeout(1000)  # 等待1秒确保内容加载
        except Exception as e:
            utils.logger.warning(f"[ToutiaoClient.search_article_by_keyword] 搜索页面加载超时或失败: {e}")
            return {"data": [], "has_more": False}

        # 等待页面内容加载
        # 从页面中提取搜索数据 - 只获取 s-result-list 下 data-test-card-id="undefined-default" 的文章
        try:
            search_data = await self.playwright_page.evaluate("""() => {
                const debug = {
                    hasResultList: false,
                    allCardsCount: 0,
                    undefinedDefaultCards: 0,
                    cardsWithTitle: 0,
                    errors: []
                };
                const result = {
                    data: [],
                    has_more: false,
                    debug: debug
                };

                try {
                    // 从 s-result-list 容器获取
                    const resultList = document.querySelector('.s-result-list');
                    debug.hasResultList = !!resultList;

                    if (resultList) {
                        // 获取所有卡片（用于调试）
                        const allCards = resultList.querySelectorAll('[data-test-card-id]');
                        debug.allCardsCount = allCards.length;

                        // 调试：获取所有 data-test-card-id 的值
                        const allCardTypes = [];
                        allCards.forEach((card, i) => {
                            allCardTypes.push(card.getAttribute('data-test-card-id'));
                        });
                        debug.allCardTypes = allCardTypes;

                        // 只获取 data-test-card-id="undefined-default" 的文章卡片
                        const cards = resultList.querySelectorAll('[data-test-card-id="undefined-default"]');
                        debug.undefinedDefaultCards = cards.length;

                        cards.forEach((card, index) => {
                            try {
                                // 1. 标题：从 cs-header 下的 a 标签获取
                                const linkEl = card.querySelector('[class*="cs-header"] a, a');
                                // 2. 摘要：从 cs-header 后面的兄弟节点中的 span 获取
                                // 结构: <div class="cs-header">...标题...</div><div>...<span>摘要</span>...</div>
                                const headerEl = card.querySelector('[class*="cs-header"]');
                                let abstractEl = null;
                                if (headerEl && headerEl.nextElementSibling) {
                                    abstractEl = headerEl.nextElementSibling.querySelector('span[class*="text-underline-hover"]');
                                }
                                // 3. 来源：从 cs-source-content 下的第一个 span 获取
                                const sourceEl = card.querySelector('[class*="cs-source-content"] span');
                                // 4. 发布时间：cs-source-content 下的第二个 span
                                const timeEl = card.querySelector('[class*="cs-source-content"] span:nth-child(2)');

                                if (linkEl) {
                                    debug.cardsWithTitle++;
                                    const url = linkEl.href;
                                    let article_id = '';
                                    let real_url = url;

                                    try {
                                        // 检查是否是跳转链接
                                        if (url.includes('/search/jump?')) {
                                            // 提取嵌套的URL参数
                                            const urlMatch = url.match(/[?&]url=([^&]+)/);
                                            if (urlMatch) {
                                                // URL 被双重编码，解码两次
                                                const decodedUrl = decodeURIComponent(decodeURIComponent(urlMatch[1]));
                                                real_url = decodedUrl;
                                            }
                                        }
                                        // 从真实URL提取文章ID (匹配 /a[数字]、/a/[数字]、/article/[数字]、/group/[数字])
                                        const idMatch = real_url.match(/\/(a|article|group)\/?(\d+)/);
                                        article_id = idMatch ? idMatch[2] : '';
                                    } catch (e) {
                                        debug.errors.push(`URL decode error: ${e.message}`);
                                    }

                                    result.data.push({
                                        article_id: article_id,
                                        title: linkEl.textContent?.trim() || linkEl.getAttribute('title'),
                                        url: real_url,  // 使用解码后的真实URL
                                        abstract: abstractEl?.textContent?.trim(),
                                        source: sourceEl?.textContent?.trim(),
                                        publish_time_text: timeEl?.textContent?.trim()
                                    });
                                } else {
                                    // 记录没找到的卡片HTML用于调试
                                    debug.missingTitleCards = debug.missingTitleCards || [];
                                    debug.missingTitleCards.push(card.outerHTML?.substring(0, 200));
                                }
                            } catch (e) {
                                debug.errors.push(`Card ${index}: ${e.message}`);
                            }
                        });
                    } else {
                        // 如果没找到 s-result-list，尝试直接在整个页面查找
                        const directCards = document.querySelectorAll('[data-test-card-id="undefined-default"]');
                        debug.directCardsCount = directCards.length;
                    }
                } catch (e) {
                    debug.errors.push(`Global: ${e.message}`);
                }

                // 判断是否还有更多
                const moreBtn = document.querySelector('.load-more, .more-btn, [class*="more"], .pagination');
                result.has_more = !!moreBtn || result.data.length >= 10;

                return result;
            }""")

            data_count = len(search_data.get("data", [])) if isinstance(search_data, dict) else 0
            debug_info = search_data.get("debug", {}) if isinstance(search_data, dict) else {}
            utils.logger.info(f"[ToutiaoClient.search_article_by_keyword] 搜索结果统计: {data_count} 条")
            utils.logger.info(f"[ToutiaoClient.search_article_by_keyword] 调试信息: {debug_info}")
            # 打印第一条数据查看实际内容
            if search_data.get("data"):
                utils.logger.info(f"[ToutiaoClient.search_article_by_keyword] 第一条数据: {search_data['data'][0]}")
            return search_data

        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.search_article_by_keyword] 提取搜索数据失败: {e}")
            return {"data": [], "has_more": False, "error": str(e)}

    async def get_article_detail(self, article_id: str) -> Dict:
        """
        获取文章详情
        接口: https://www.toutiao.com/article/{article_id}/
        :param article_id: 文章ID
        :return: 文章详情（包含全文内容、互动数据等）
        """
        url = f"{self._host}/article/{article_id}/"

        try:
            # 使用playwright页面获取详情
            response = await self.playwright_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.playwright_page.wait_for_timeout(1000)  # 减少等待时间到1秒

            # 从页面中提取文章数据
            article_data = await self.playwright_page.evaluate("""() => {
                const result = {
                    fromScript: false,
                    fromDom: false,
                    data: {}
                };

                // 方法1: 从页面脚本中提取初始数据 (SSR_HYDRATED_DATA)
                const scripts = document.querySelectorAll('script');
                for (let script of scripts) {
                    const text = script.textContent;
                    if (text.includes('SSR_HYDRATED_DATA') || text.includes('articleInfo')) {
                        try {
                            // 尝试匹配 window._SSR_HYDRATED_DATA
                            const ssrMatch = text.match(/window\._SSR_HYDRATED_DATA\s*=\s*({.+?});/);
                            if (ssrMatch) {
                                const ssrData = JSON.parse(ssrMatch[1]);
                                result.fromScript = true;
                                result.data.ssr = ssrData;

                                // 提取文章详情
                                if (ssrData && ssrData.initialState) {
                                    const feed = ssrData.initialState.feed;
                                    if (feed) {
                                        for (let key in feed) {
                                            if (feed[key] && feed[key].raw_data) {
                                                const raw = feed[key].raw_data;
                                                result.data.title = raw.title;
                                                result.data.content = raw.content;
                                                result.data.abstract = raw.abstract;
                                                result.data.source = raw.source;
                                                result.data.publish_time = raw.publish_time || raw.create_time;
                                                result.data.behot_time = raw.behot_time;

                                                // 互动数据
                                                if (raw.action_list) {
                                                    raw.action_list.forEach(action => {
                                                        if (action.action === 1) result.data.like_count = action.count;
                                                        if (action.action === 2) result.data.comment_count = action.count;
                                                        if (action.action === 3) result.data.share_count = action.count;
                                                    });
                                                }
                                                result.data.read_count = raw.read_count || raw.go_detail_count;
                                                result.data.digg_count = raw.digg_count;
                                                result.data.bury_count = raw.bury_count;
                                                result.data.repin_count = raw.repin_count;

                                                // 其他数据
                                                result.data.user = raw.user;
                                                result.data.has_video = raw.has_video;
                                                result.data.has_image = raw.has_image;
                                                result.data.image_list = raw.image_list;
                                                result.data.large_image = raw.large_image;
                                                result.data.video_duration = raw.video_duration;
                                                result.data.media_name = raw.media_name;
                                                result.data.media_info = raw.media_info;

                                                break;
                                            }
                                        }
                                    }
                                }
                                return result;
                            }

                            // 尝试匹配 articleInfo
                            const articleMatch = text.match(/articleInfo\s*=\s*({.+?});/);
                            if (articleMatch) {
                                result.fromScript = true;
                                result.data.articleInfo = JSON.parse(articleMatch[1]);
                                return result;
                            }
                        } catch(e) {}
                    }
                }

                // 方法2: 从DOM中提取（降级方案）
                result.fromDom = true;

                // 标题
                const titleSelectors = [
                    'h1.title',
                    'h1.article-title',
                    '[class*="title"] h1',
                    'h1'
                ];
                for (let sel of titleSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        result.data.title = el.textContent.trim();
                        break;
                    }
                }

                // 内容
                const contentSelectors = [
                    '.article-content',
                    '.tt-article-content',
                    '[class*="article-content"]',
                    '.content',
                    'article'
                ];
                for (let sel of contentSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerHTML) {
                        result.data.content = el.innerHTML;
                        result.data.content_text = el.textContent.trim();
                        break;
                    }
                }

                // 作者
                const authorSelectors = [
                    '.author-name',
                    '[class*="author-name"]',
                    '.media-info [class*="name"]',
                    '[class*="author"] [class*="name"]'
                ];
                for (let sel of authorSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        result.data.author = el.textContent.trim();
                        result.data.media_name = el.textContent.trim();
                        break;
                    }
                }

                // 互动数据（点赞、评论、分享）
                const extractNumber = (selectors, fromAriaLabel = false) => {
                    for (let sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            // 优先从 aria-label 属性提取数字
                            if (fromAriaLabel && el.getAttribute('aria-label')) {
                                const label = el.getAttribute('aria-label');
                                const match = label.match(/(\d+)/);
                                if (match) return parseInt(match[1]);
                            }
                            // 从 textContent 提取
                            if (el.textContent) {
                                const num = parseInt(el.textContent.replace(/[^0-9]/g, ''));
                                if (!isNaN(num)) return num;
                            }
                        }
                    }
                    return 0;
                };

                result.data.digg_count = extractNumber([
                    '[class*="digg"]',
                    '[class*="like"] span',
                    '.like-count',
                    '[data-action="like"] .count'
                ]);

                // 评论数：优先从 aria-label 提取
                const commentEl = document.querySelector('[class*="detail-interaction-comment"]');
                if (commentEl && commentEl.getAttribute('aria-label')) {
                    const commentMatch = commentEl.getAttribute('aria-label').match(/(\d+)/);
                    if (commentMatch) {
                        result.data.comment_count = parseInt(commentMatch[1]);
                    }
                } else {
                    result.data.comment_count = extractNumber([
                        '[class*="detail-interaction-comment"]',
                        '[class*="comment"] .count',
                        '.comment-count',
                        '[data-action="comment"] span'
                    ], true);
                }

                result.data.share_count = extractNumber([
                    '[class*="share"] span',
                    '.share-count',
                    '[data-action="share"] span'
                ]);

                // 发布时间
                const timeSelectors = [
                    '[class*="publish-time"]',
                    '[class*="time"]',
                    '.date'
                ];
                for (let sel of timeSelectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent.trim()) {
                        result.data.publish_time_text = el.textContent.trim();
                        break;
                    }
                }

                return result;
            }""")

            return {
                "article_id": article_id,
                "data": article_data.get("data", {}),
                "url": url
            }
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.get_article_detail] 获取文章详情失败: {e}")
            return {"article_id": article_id, "data": {}, "url": url, "error": str(e)}

    async def get_article_comments(
        self,
        article_id: str,
        offset: int = 0,
        count: int = 20,
        order_mode: CommentOrderType = CommentOrderType.DEFAULT,
    ) -> Dict:
        """
        获取文章评论
        接口: https://www.toutiao.com/article/v4/tab_comments/
        :param article_id: 文章ID (group_id)
        :param offset: 偏移量
        :param count: 数量
        :param order_mode: 排序方式
        :return: 评论数据
        """
        url = "https://www.toutiao.com/article/v4/tab_comments/"
        params = {
            "aid": "24",
            "app_name": "toutiao_web",
            "offset": offset,
            "count": count,
            "group_id": article_id,
            "item_id": article_id,
        }

        try:
            # 评论接口响应快，使用较短的超时时间（5秒）
            async with httpx.AsyncClient(proxy=self.proxy) as client:
                response = await client.request("GET", f"{url}?{urlencode(params)}", headers=self.headers, timeout=5)
            return response.json()
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.get_article_comments] 获取评论失败: {e}")
            raise DataFetchError(f"获取评论失败: {e}")

    async def get_comment_replies(
        self,
        comment_id: str,
        offset: int = 0,
        count: int = 20,
    ) -> Dict:
        """
        获取评论的子评论（回复列表）
        接口: https://www.toutiao.com/2/comment/v4/reply_list/
        :param comment_id: 评论ID
        :param offset: 偏移量
        :param count: 数量
        :return: 子评论数据
        """
        url = "https://www.toutiao.com/2/comment/v4/reply_list/"
        params = {
            "aid": "24",
            "app_name": "toutiao_web",
            "id": comment_id,
            "offset": offset,
            "count": count,
            "repost": "0",
        }

        try:
            # 子评论接口响应快，使用较短的超时时间（5秒）
            async with httpx.AsyncClient(proxy=self.proxy) as client:
                response = await client.request("GET", f"{url}?{urlencode(params)}", headers=self.headers, timeout=5)
            return response.json()
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.get_comment_replies] 获取子评论失败: {e}")
            raise DataFetchError(f"获取子评论失败: {e}")

    async def get_comment_all_replies(
        self,
        comment_id: str,
        max_count: int = 100,
    ) -> List[Dict]:
        """
        获取评论的所有子评论（只获取一遍）
        :param comment_id: 评论ID
        :param max_count: 最大子评论数
        :return: 子评论列表
        """
        result = []
        offset = 0
        max_retries = 2

        attempt = 0
        success = False

        while attempt < max_retries and not success:
            try:
                replies_res = await self.get_comment_replies(
                    comment_id=comment_id,
                    offset=offset,
                    count=max_count,
                )

                # 解析响应
                if isinstance(replies_res, dict):
                    data = replies_res.get("data", replies_res)
                else:
                    data = replies_res

                # 提取回复列表
                if isinstance(data, dict):
                    reply_list = data.get("data", [])
                elif isinstance(data, list):
                    reply_list = data
                else:
                    reply_list = []

                # 如果返回空数据，直接结束
                if not reply_list:
                    utils.logger.info(f"[ToutiaoClient.get_comment_all_replies] 返回空数据, comment_id: {comment_id}")
                    return []

                # 格式化子评论数据
                # 注意：子评论接口没有返回回复目标用户ID，使用空字符串
                formatted_replies = self._format_sub_comments(
                    reply_list,
                    parent_id=comment_id,
                    reply_to_user_id="",
                )

                # 限制数量
                if len(formatted_replies) > max_count:
                    formatted_replies = formatted_replies[:max_count]

                result.extend(formatted_replies)
                success = True  # 成功获取，不重试

            except DataFetchError as e:
                attempt += 1
                if attempt < max_retries:
                    delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                    utils.logger.warning(f"[ToutiaoClient.get_comment_all_replies] 错误重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 错误: {e}")
                    await asyncio.sleep(delay)
                else:
                    utils.logger.error(f"[ToutiaoClient.get_comment_all_replies] 达到最大重试次数: {e}")
                    break
            except Exception as e:
                attempt += 1
                if attempt < max_retries:
                    delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                    utils.logger.warning(f"[ToutiaoClient.get_comment_all_replies] 异常重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 异常: {e}")
                    await asyncio.sleep(delay)
                else:
                    utils.logger.error(f"[ToutiaoClient.get_comment_all_replies] 达到最大重试次数: {e}")
                    break

        return result

    async def get_article_all_comments(
        self,
        article_id: str,
        is_fetch_sub_comments: bool = False,
        callback: Optional[Callable] = None,
        sub_comments_callback: Optional[Callable] = None,
        max_count: int = 100,
        max_sub_comments_count: int = 50,
    ) -> List[Dict]:
        """
        获取文章所有评论（只获取一遍）
        :param article_id: 文章ID
        :param is_fetch_sub_comments: 是否获取子评论
        :param callback: 评论回调函数
        :param sub_comments_callback: 子评论回调函数
        :param max_count: 最大主评论数
        :param max_sub_comments_count: 每条主评论下最多获取的子评论数量
        :return: 评论列表
        """
        result = []
        offset = 0
        max_retries = 2

        utils.logger.info(f"[ToutiaoClient.get_article_all_comments] 开始获取评论, article_id: {article_id}, 是否获取子评论: {is_fetch_sub_comments}")

        attempt = 0
        success = False

        while attempt < max_retries and not success:
            try:
                comments_res = await self.get_article_comments(
                    article_id=article_id,
                    offset=offset,
                    count=max_count,
                )

                # 解析响应
                if isinstance(comments_res, dict):
                    data = comments_res.get("data", comments_res)
                else:
                    data = comments_res

                # 提取评论列表
                if isinstance(data, dict):
                    comment_list = data.get("comments", data.get("data", []))
                elif isinstance(data, list):
                    comment_list = data
                else:
                    comment_list = []

                # 如果返回空数据，直接结束
                if not comment_list:
                    utils.logger.info(f"[ToutiaoClient.get_article_all_comments] 返回空数据, article_id: {article_id}")
                    return []

                # 格式化评论数据
                formatted_comments = self._format_comments(comment_list)

                # 限制数量
                if len(formatted_comments) > max_count:
                    formatted_comments = formatted_comments[:max_count]

                if callback:
                    await callback(article_id, formatted_comments)

                result.extend(formatted_comments)

                # 获取子评论（如果启用），每个主评论下最多获取 max_sub_comments_count 条子评论
                if is_fetch_sub_comments:
                    await self._fetch_sub_comments_for_list(
                        article_id=article_id,
                        comments=result,
                        max_sub_comments=max_sub_comments_count,
                        sub_comments_callback=sub_comments_callback,
                    )
                success = True  # 成功获取，不重试

            except DataFetchError as e:
                attempt += 1
                if attempt < max_retries:
                    delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                    utils.logger.warning(f"[ToutiaoClient.get_article_all_comments] 错误重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 错误: {e}")
                    await asyncio.sleep(delay)
                else:
                    utils.logger.error(f"[ToutiaoClient.get_article_all_comments] 达到最大重试次数: {e}")
                    break
            except Exception as e:
                attempt += 1
                if attempt < max_retries:
                    delay = 2 * (2 ** attempt) + random.uniform(0, 1)
                    utils.logger.warning(f"[ToutiaoClient.get_article_all_comments] 异常重试 {attempt}/{max_retries}, 等待{delay:.2f}s... 异常: {e}")
                    await asyncio.sleep(delay)
                else:
                    utils.logger.error(f"[ToutiaoClient.get_article_all_comments] 达到最大重试次数: {e}")
                    break

        utils.logger.info(f"[ToutiaoClient.get_article_all_comments] 评论获取完成, article_id: {article_id}, 共 {len(result)} 条评论")
        return result

    def _format_comments(self, comment_list: List[Dict], parent_id: str = None, reply_to_user_id: str = "") -> List[Dict]:
        """格式化评论数据为统一格式"""
        formatted = []
        for comment in comment_list:
            if isinstance(comment, dict):
                # 检查是否是主评论接口返回的格式（包含嵌套的comment字段）
                if "comment" in comment:
                    comment_data = comment.get("comment", {})
                else:
                    comment_data = comment

                # 提取评论内容
                content = comment_data.get("text", comment_data.get("content", ""))
                if isinstance(content, str):
                    content = clean_html_content(content)

                # 提取用户数据
                user_data = comment_data.get("user", {})
                user_id = str(comment_data.get("user_id", user_data.get("user_id", "")))
                user_name = comment_data.get("user_name", user_data.get("name", user_data.get("screen_name", "")))
                avatar_url = comment_data.get("user_profile_image_url", user_data.get("avatar_url", ""))

                formatted_comment = {
                    "comment_id": str(comment_data.get("id", comment_data.get("id_str", ""))),
                    "content": content,
                    "create_time": comment_data.get("create_time", 0),
                    "like_count": comment_data.get("digg_count", 0),
                    "reply_count": comment_data.get("reply_count", 0),
                    "ip_location": comment_data.get("publish_loc_info", ""),
                    "parent_id": parent_id,
                    "is_sub_comment": parent_id is not None,
                    "user": {
                        "user_id": user_id,
                        "nickname": user_name,
                        "avatar": avatar_url,
                    },
                    "raw_data": comment,
                }

                # 如果是子评论，添加回复目标用户ID（父评论ID）
                if parent_id and reply_to_user_id:
                    formatted_comment["reply_to_user_id"] = reply_to_user_id

                formatted.append(formatted_comment)
        return formatted

    def _format_sub_comments(self, comment_list: List[Dict], parent_id: str, reply_to_user_id: str) -> List[Dict]:
        """格式化子评论数据（回复列表专用）
        :param comment_list: 子评论列表
        :param parent_id: 父评论ID
        :param reply_to_user_id: 回复目标用户ID（即父评论作者ID，从API响应的data.id获取）
        """
        return self._format_comments(comment_list, parent_id=parent_id, reply_to_user_id=reply_to_user_id)

    async def _fetch_sub_comments_for_list(
        self,
        article_id: str,
        comments: List[Dict],
        max_sub_comments: int,
        sub_comments_callback: Optional[Callable] = None,
    ) -> None:
        """
        为评论列表获取子评论，每个主评论下最多获取 max_sub_comments 条子评论
        :param article_id: 文章ID
        :param comments: 评论列表
        :param max_sub_comments: 每个主评论下最大子评论数
        :param sub_comments_callback: 子评论回调函数
        """
        # 收集需要获取子评论的评论ID
        comments_with_replies = []
        for comment in comments:
            if comment.get("reply_count", 0) > 0 and not comment.get("sub_comments"):
                comments_with_replies.append(comment)
            else:
                comment["sub_comments"] = comment.get("sub_comments", [])
                comment["sub_comments_count"] = len(comment["sub_comments"])

        if not comments_with_replies:
            return

        utils.logger.info(f"[ToutiaoClient._fetch_sub_comments_for_list] 并行获取 {len(comments_with_replies)} 条评论的子评论（最多5并发），每个主评论下最多: {max_sub_comments} 条子评论")

        semaphore = asyncio.Semaphore(5)

        async def fetch_replies_per_comment(comment: Dict) -> tuple:
            async with semaphore:
                comment_id = comment.get("comment_id")
                try:
                    # 每个主评论下最多获取 max_sub_comments 条子评论
                    sub_comments = await self.get_comment_all_replies(
                        comment_id=comment_id,
                        max_count=max_sub_comments,
                    )
                    if sub_comments_callback and sub_comments:
                        await sub_comments_callback(article_id, comment_id, sub_comments)
                    return (comment, sub_comments, None)
                except Exception as e:
                    utils.logger.warning(f"[ToutiaoClient._fetch_sub_comments_for_list] 获取子评论失败: {comment_id}, {e}")
                    return (comment, [], e)

        # 并发执行所有子评论获取
        results = await asyncio.gather(
            *[fetch_replies_per_comment(c) for c in comments_with_replies],
            return_exceptions=True
        )

        # 处理结果
        for comment, sub_comments, error in results:
            comment["sub_comments"] = sub_comments
            comment["sub_comments_count"] = len(sub_comments)

    async def get_creator_info(self, creator_id: str) -> Dict:
        """
        获取创作者信息
        :param creator_id: 创作者ID
        :return: 创作者信息
        """
        url = f"{self._host}/c/user/{creator_id}/"

        try:
            response = await self.request("GET", url, headers=self.headers)
            return response
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.get_creator_info] 获取创作者信息失败: {e}")
            raise DataFetchError(f"获取创作者信息失败: {e}")

    async def get_creator_articles(
        self,
        creator_id: str,
        offset: int = 0,
        count: int = 20,
    ) -> Dict:
        """
        获取创作者文章列表
        :param creator_id: 创作者ID
        :param offset: 偏移量
        :param count: 数量
        :return: 文章列表
        """
        # 创作者文章列表API（可能需要根据实际接口调整）
        url = f"{self._host}/api/pc/feed/"
        params = {
            "category": "profile_all",
            "visit_user_id": creator_id,
            "max_behot_time": offset,
            "count": count,
        }

        try:
            response = await self.request("GET", f"{url}?{urlencode(params)}", headers=self.headers)
            return response
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.get_creator_articles] 获取创作者文章失败: {e}")
            raise DataFetchError(f"获取创作者文章失败: {e}")

    def parse_search_results(self, response: Dict) -> List[Dict]:
        """
        解析搜索结果
        :param response: API响应
        :return: 解析后的文章列表
        """
        articles = []

        if not isinstance(response, dict):
            return articles

        # 尝试不同的数据结构
        data = response.get("data", response)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items", data.get("list", data.get("data", [])))
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue

            # Playwright 抓取返回的字段名
            # article_id, title, url, abstract, source, publish_time_text
            article_id = item.get("article_id", "")
            title = item.get("title", "")
            url = item.get("url", "")
            abstract = item.get("abstract", "")
            source = item.get("source", "")
            publish_time_text = item.get("publish_time_text", "")

            # 提取文章基本信息（兼容两种数据源：Playwright抓取 和 API返回）
            article = {
                "article_id": article_id or str(item.get("id", item.get("group_id", item.get("item_id", "")))),
                "title": title or item.get("title", ""),
                "abstract": abstract or item.get("abstract", item.get("summary", "")),
                "content": "",  # 初始为空，等待详情抓取时填充
                "create_time": "",  # 从内容中提取的创建时间
                "source": source or item.get("source", item.get("media_name", "")),
                "author": source or item.get("source", item.get("media_name", "")),
                "publish_time": item.get("publish_time", item.get("behot_time", 0)),
                "publish_time_text": publish_time_text,
                "url": url or item.get("url", item.get("display_url", "")),
                "read_count": item.get("read_count", item.get("go_detail_count", 0)),
                "like_count": item.get("like_count", item.get("digg_count", 0)),
                "comment_count": item.get("comment_count", 0),
                "share_count": item.get("share_count", 0),
                "has_video": item.get("has_video", False),
                "has_image": item.get("has_image", False),
                "image_list": item.get("image_list", []),
                "raw_data": item,
            }

            articles.append(article)

        return articles

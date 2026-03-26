# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/tieba/help.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


# -*- coding: utf-8 -*-
import html
import json
import re
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, unquote

from parsel import Selector

from constant import baidu_tieba as const
from model.m_baidu_tieba import TiebaComment, TiebaCreator, TiebaNote
from tools import utils

GENDER_MALE = "sex_male"
GENDER_FEMALE = "sex_female"


class TieBaExtractor:
    def __init__(self):
        pass

    @staticmethod
    def extract_search_note_list(page_content: str) -> List[TiebaNote]:
        """
        Extract Tieba post list from keyword search result pages
        Args:
            page_content: HTML string of page content

        Returns:
            List of Tieba post objects
        """
        content_selector = Selector(text=page_content)

        # First try new virtual list structure
        # Get all virtual-list-item that have actual content (non-empty data-key)
        xpath_selector = "//div[@class='thread-list-container']/div[@class='virtual-list-item'][@data-key]"
        post_list = content_selector.xpath(xpath_selector)

        result: List[TiebaNote] = []
        for post_item in post_list:
            # Check if this item has actual content (thread card)
            thread_card = post_item.xpath(".//div[contains(@class, 'threadcardclass')]")
            if not thread_card:
                continue  # Skip empty placeholder items

            # Extract note_id from data-key attribute
            note_id = post_item.xpath("./@data-key").get(default='').strip()
            if not note_id:
                continue

            # Extract title from title-wrap - handle both with and without highlight font tag
            title_parts = thread_card.xpath(".//div[@class='title-wrap']//text()").getall()
            title = ''.join(t.strip() for t in title_parts if t.strip())

            # Extract description from abstract-wrap - get all text including highlighted parts
            desc_parts = thread_card.xpath(".//div[@class='abstract-wrap']//text()").getall()
            desc = ''.join(d.strip() for d in desc_parts if d.strip())

            # Extract user nickname from forum-attention (clean whitespace)
            user_nickname = thread_card.xpath(".//span[@class='forum-attention user']/text()").get(default='').strip()
            # Clean up any special unicode characters
            user_nickname = ' '.join(user_nickname.split())

            # Extract publish time - look for text containing "发布于"
            publish_time = ''
            top_title_texts = thread_card.xpath(".//div[@class='top-title']//text()").getall()
            for text in top_title_texts:
                if '发布于' in text:
                    publish_time = text.replace('发布于', '').strip()
                    break

            # Extract tieba name from forum-name-text
            tieba_name = thread_card.xpath(".//span[@class='forum-name-text']/text()").get(default='').strip()

            # Extract like count and comment count from action-bar
            # Share, Comment, Like - indices 0, 1, 2
            action_items = thread_card.xpath(".//div[@class='action-bar-warp']//span[@class='action-number']/text()").getall()
            like_count = 0
            comment_count = 0
            if len(action_items) >= 3:
                # Format: [share_text/num, comment_num, like_num]
                try:
                    comment_text = action_items[1].strip()
                    if comment_text.isdigit():
                        comment_count = int(comment_text)
                except (ValueError, IndexError):
                    pass
                try:
                    like_text = action_items[2].strip()
                    if like_text.isdigit():
                        like_count = int(like_text)
                except (ValueError, IndexError):
                    pass

            tieba_note = TiebaNote(
                note_id=note_id,
                title=title,
                desc=desc,
                note_url=const.TIEBA_URL + f"/p/{note_id}" if note_id else '',
                user_nickname=user_nickname,
                user_link='',  # New structure doesn't show user link directly in search results
                tieba_name=tieba_name,
                tieba_link=f"{const.TIEBA_URL}/f?kw={tieba_name}" if tieba_name else '',
                publish_time=publish_time,
                like_count=like_count,
                total_replay_num=comment_count,
            )
            result.append(tieba_note)

        # Fallback to old structure if no results found
        if not result:
            return TieBaExtractor._extract_search_note_list_old(page_content)

        return result

    @staticmethod
    def _extract_search_note_list_old(page_content: str) -> List[TiebaNote]:
        """
        Fallback method for old page structure
        """
        xpath_selector = "//div[@class='s_post']"
        post_list = Selector(text=page_content).xpath(xpath_selector)
        result: List[TiebaNote] = []
        for post in post_list:
            tieba_note = TiebaNote(note_id=post.xpath(".//span[@class='p_title']/a/@data-tid").get(default='').strip(),
                                   title=post.xpath(".//span[@class='p_title']/a/text()").get(default='').strip(),
                                   desc=post.xpath(".//div[@class='p_content']/text()").get(default='').strip(),
                                   note_url=const.TIEBA_URL + post.xpath(".//span[@class='p_title']/a/@href").get(
                                       default=''),
                                   user_nickname=post.xpath(".//a[starts-with(@href, '/home/main')]/font/text()").get(
                                       default='').strip(), user_link=const.TIEBA_URL + post.xpath(
                    ".//a[starts-with(@href, '/home/main')]/@href").get(default=''),
                                   tieba_name=post.xpath(".//a[@class='p_forum']/font/text()").get(default='').strip(),
                                   tieba_link=const.TIEBA_URL + post.xpath(".//a[@class='p_forum']/@href").get(
                                       default=''),
                                   publish_time=post.xpath(".//font[@class='p_green p_date']/text()").get(
                                       default='').strip(), )
            result.append(tieba_note)
        return result

    def extract_tieba_note_list(self, page_content: str) -> List[TiebaNote]:
        """
        Extract Tieba post list from Tieba page
        Args:
            page_content: HTML string of page content

        Returns:
            List of Tieba post objects
        """
        page_content = page_content.replace('<!--', "")
        content_selector = Selector(text=page_content)
        xpath_selector = "//ul[@id='thread_list']/li"
        post_list = content_selector.xpath(xpath_selector)
        result: List[TiebaNote] = []
        for post_selector in post_list:
            post_field_value: Dict = self.extract_data_field_value(post_selector)
            if not post_field_value:
                continue
            note_id = str(post_field_value.get("id"))
            tieba_note = TiebaNote(note_id=note_id,
                                   title=post_selector.xpath(".//a[@class='j_th_tit ']/text()").get(default='').strip(),
                                   desc=post_selector.xpath(
                                       ".//div[@class='threadlist_abs threadlist_abs_onlyline ']/text()").get(
                                       default='').strip(), note_url=const.TIEBA_URL + f"/p/{note_id}",
                                   user_link=const.TIEBA_URL + post_selector.xpath(
                                       ".//a[@class='frs-author-name j_user_card ']/@href").get(default='').strip(),
                                   user_nickname=post_field_value.get("authoer_nickname") or post_field_value.get(
                                       "author_name"),
                                   tieba_name=content_selector.xpath("//a[@class='card_title_fname']/text()").get(
                                       default='').strip(), tieba_link=const.TIEBA_URL + content_selector.xpath(
                    "//a[@class='card_title_fname']/@href").get(default=''),
                                   total_replay_num=post_field_value.get("reply_num", 0))
            result.append(tieba_note)
        return result

    def extract_note_detail(self, page_content: str) -> TiebaNote:
        """
        Extract Tieba post details from post detail page
        Supports both new Vue-based structure and old structure
        Args:
            page_content: HTML string of page content

        Returns:
            Tieba post detail object
        """
        content_selector = Selector(text=page_content)

        # Try new structure first (Vue-based)
        # Check if it's new structure by looking for new class names
        # New structure has multiple indicators: pb-title-wrap, pb-content-wrap, image-text
        new_structure = (
            content_selector.xpath("//div[@class='pb-title-wrap']").get() or
            content_selector.xpath("//div[@class='image-text']").get() or
            content_selector.xpath("//div[@class='head-info']").get()
        )

        if new_structure:
            return self._extract_note_detail_new(content_selector, page_content)
        else:
            return self._extract_note_detail_old(content_selector)

    def _extract_note_detail_new(self, content_selector: Selector, page_content: str) -> TiebaNote:
        """
        Extract note detail from new Vue-based page structure
        """
        # Extract note_id from tid attribute in the page
        note_id = ""
        tid_match = re.search(r'tid=["\']?(\d+)["\']?', page_content)
        if tid_match:
            note_id = tid_match.group(1)
        else:
            url_match = re.search(r'/p/(\d+)', page_content)
            if url_match:
                note_id = url_match.group(1)

        # Extract title - try multiple selectors
        title = content_selector.xpath("//span[@class='pb-title']/text()").get(default='').strip()
        if not title:
            title = content_selector.xpath("//div[@class='pb-title-wrap']//text()").get(default='').strip()
        if not title:
            # Try meta title
            title = content_selector.xpath("//title/text()").get(default='').strip()

        # Initialize image_text first (we'll need it for both user info and content)
        image_text = content_selector.xpath("//div[contains(@class, 'image-text')]")

        # Extract description/content
        # Content is in pb-content-wrap, text is in span elements with data-v- attributes
        content_wrap = None
        if image_text:
            content_wrap = image_text.xpath(".//div[contains(@class, 'pb-content-wrap')]")
        else:
            content_wrap = content_selector.xpath("//div[contains(@class, 'pb-content-wrap')]")
        desc = ''
        if content_wrap:
            # Try to get all text from content wrap
            desc_parts = content_wrap.xpath(".//span//text()").getall()
            desc = ''.join(d.strip() for d in desc_parts if d.strip())

        if not desc:
            # Fallback: get from meta description
            desc = content_selector.xpath("//meta[@name='description']/@content").get(default='').strip()

        # Extract user info - first image-text block contains author info
        # User info is in the first head-line inside image-text
        image_text = content_selector.xpath("//div[contains(@class, 'image-text')]")
        user_nickname = ''
        user_avatar = ''
        user_link = ''
        first_head_line = None

        if image_text:
            # First head-line contains author info
            first_head_line = image_text.xpath(".//div[contains(@class, 'head-line')][1]")
            if first_head_line:
                # Get nickname from head-name
                user_nickname = first_head_line.xpath(".//*[contains(@class, 'head-name')]/text()").get(default='').strip()
                # Get avatar from first avatar-img
                user_avatar = first_head_line.xpath(".//img[contains(@class, 'avatar-img')]/@src").get(default='').strip()

        # Fallback if not found in image-text
        if not user_nickname:
            user_nickname = content_selector.xpath("//*[contains(@class, 'head-name')]/text()").get(default='').strip()
        if not user_avatar:
            user_avatar = content_selector.xpath("//img[contains(@class, 'avatar-img')]/@src").get(default='').strip()

        # Extract user link - try to get from popover or user card
        # In new structure, user link may be in aria-describedby popover or data attribute
        if first_head_line:
            # Try to find user ID from popover reference
            popover_ref = first_head_line.xpath(".//*[contains(@class, 'popover__reference')]/@aria-describedby").get(default='')
            if popover_ref:
                # Extract user ID from popover ID and construct URL
                # Popover format: popover-{user_id}
                user_id_match = re.search(r'popover-(\d+)', popover_ref)
                if user_id_match:
                    user_link = f"{const.TIEBA_URL}/home/main?id={user_id_match.group(1)}"
            # Try to get from any link in head-line
            if not user_link:
                user_link = first_head_line.xpath(".//a/@href").get(default='')
                if user_link and not user_link.startswith('http'):
                    user_link = const.TIEBA_URL + (user_link if not user_link.startswith('/') else user_link[1:])

        # Extract publish time and IP from main post's desc-info (first image-text block)
        # Use . to limit search to the first image-text to avoid matching comment elements
        first_image_text = content_selector.xpath("//div[contains(@class, 'image-text')][1]")
        if first_image_text:
            publish_time = first_image_text.xpath(".//span[@class='post-num']/text()").get(default='').strip()
            ip_location = first_image_text.xpath(".//span[@class='ip-address']/text()").get(default='').strip()
        else:
            publish_time = ""
            ip_location = ""

        # Extract like count and comment count from action bar
        # Action bar has: 转发, 评论数, 点赞数, 收藏
        action_bar = content_selector.xpath("(//div[@class='action-bar-container' and contains(@class, 'action-bar')])[1]")
        like_count = 0
        total_replay_num = 0

        if action_bar:
            # Get all action numbers: [转发, 评论数, 点赞数, 收藏]
            action_numbers = action_bar.xpath(".//span[@class='action-number']/text()").getall()
            if len(action_numbers) >= 3:
                # Index 1 is comment count, index 2 is like count
                try:
                    comment_text = action_numbers[1].strip()
                    if comment_text.isdigit():
                        total_replay_num = int(comment_text)
                except (ValueError, IndexError):
                    pass
                try:
                    like_text = action_numbers[2].strip()
                    if like_text.isdigit():
                        like_count = int(like_text)
                except (ValueError, IndexError):
                    pass

        # Fallback: Try to extract from "全部回复(X)" tab
        if total_replay_num == 0:
            reply_tab_text = content_selector.xpath("//div[contains(@class, 'tab-item') and contains(text(), '全部回复')]//text()").get(default='')
            if reply_tab_text:
                reply_match = re.search(r'\((\d+)\)', reply_tab_text)
                if reply_match:
                    total_replay_num = int(reply_match.group(1))

        # Calculate total replay pages (10 comments per page)
        total_replay_page = 0
        if total_replay_num:
            try:
                total_replay_page = (int(total_replay_num) + 9) // 10  # Round up division
            except (ValueError, TypeError):
                total_replay_page = 0

        # Extract tieba name - may be in meta or page title
        tieba_name = ""
        tieba_link = ""

        note = TiebaNote(
            note_id=note_id,
            title=title,
            desc=desc,
            note_url=const.TIEBA_URL + f"/p/{note_id}" if note_id else '',
            user_link=user_link,
            user_nickname=user_nickname,
            user_avatar=user_avatar,
            tieba_name=tieba_name,
            tieba_link=tieba_link,
            ip_location=ip_location,
            publish_time=publish_time,
            like_count=str(like_count),
            total_replay_num=str(total_replay_num),
            total_replay_page=total_replay_page,
        )
        return note

    def _extract_note_detail_old(self, content_selector: Selector) -> TiebaNote:
        """
        Extract note detail from old page structure
        """
        first_floor_selector = content_selector.xpath("//div[@class='p_postlist'][1]")
        only_view_author_link = content_selector.xpath("//*[@id='lzonly_cntn']/@href").get(default='').strip()
        note_id = only_view_author_link.split("?")[0].split("/")[-1] if only_view_author_link else ""
        # Post reply count and reply page count
        thread_num_infos = content_selector.xpath(
            "//div[@id='thread_theme_5']//li[@class='l_reply_num']//span[@class='red']")
        # IP location and publish time
        other_info_content = content_selector.xpath(".//div[@class='post-tail-wrap']").get(default="").strip()
        ip_location, publish_time = self.extract_ip_and_pub_time(other_info_content)

        # Safe extraction of thread nums
        total_replay_num = ""
        total_replay_page = ""
        if len(thread_num_infos) >= 2:
            total_replay_num = thread_num_infos[0].xpath("./text()").get(default='').strip()
            total_replay_page = thread_num_infos[1].xpath("./text()").get(default='').strip()

        tieba_name = content_selector.xpath("//a[@class='card_title_fname']/text()").get(default='').strip()

        note = TiebaNote(
            note_id=note_id,
            title=content_selector.xpath("//title/text()").get(default='').strip(),
            desc=content_selector.xpath("//meta[@name='description']/@content").get(default='').strip(),
            note_url=const.TIEBA_URL + f"/p/{note_id}" if note_id else '',
            user_link=const.TIEBA_URL + first_floor_selector.xpath(
                ".//a[@class='p_author_face ']/@href").get(default='').strip(),
            user_nickname=first_floor_selector.xpath(
                ".//a[@class='p_author_name j_user_card']/text()").get(default='').strip(),
            user_avatar=first_floor_selector.xpath(".//a[@class='p_author_face ']/img/@src").get(
                default='').strip(),
            tieba_name=tieba_name,
            tieba_link=const.TIEBA_URL + content_selector.xpath(
                "//a[@class='card_title_fname']/@href").get(default=''),
            ip_location=ip_location,
            publish_time=publish_time,
            total_replay_num=total_replay_num,
            total_replay_page=total_replay_page,
        )
        note.title = note.title.replace(f"【{note.tieba_name}】_Baidu Tieba", "")
        return note

    def extract_tieba_note_parment_comments(self, page_content: str, note_id: str) -> List[TiebaComment]:
        """
        Extract Tieba post first-level comments from comment page
        Supports both new Vue-based structure and old structure
        Args:
            page_content: HTML string of page content
            note_id: Post ID

        Returns:
            List of first-level comment objects
        """
        content_selector = Selector(text=page_content)

        # Try new Vue-based structure first
        # pb-comment-item may have Vue data attributes like data-v-4572a90b
        new_comment_list = content_selector.xpath("//div[contains(@class, 'pb-comment-item')]")

        if new_comment_list and len(new_comment_list) > 0:
            return self._extract_comments_new(new_comment_list, note_id, content_selector)
        else:
            return self._extract_comments_old(content_selector, note_id)

    def _extract_comments_new(self, comment_list: List[Selector], note_id: str, content_selector: Selector) -> List[TiebaComment]:
        """
        Extract comments from new Vue-based page structure
        """
        result: List[TiebaComment] = []

        for comment_selector in comment_list:
            # Get parent virtual-list-item for data-key (this is the comment ID)
            virtual_item = comment_selector.xpath("ancestor::div[contains(@class, 'virtual-list-item')]")
            comment_id = virtual_item.xpath("./@data-key").get(default='').strip()

            # Extract user info from head-line inside comment
            head_line = comment_selector.xpath(".//div[contains(@class, 'head-line')]")
            user_nickname = ''
            user_avatar = ''
            if head_line:
                user_nickname = head_line.xpath(".//*[contains(@class, 'head-name')]/text()").get(default='').strip()
                user_avatar = head_line.xpath(".//img[contains(@class, 'avatar-img')]/@src").get(default='').strip()

            # Fallback: try broader selectors
            if not user_nickname:
                user_nickname = comment_selector.xpath(".//*[contains(@class, 'head-name')]/text()").get(default='').strip()
            if not user_avatar:
                user_avatar = comment_selector.xpath(".//img[contains(@class, 'avatar-img')]/@src").get(default='').strip()

            # Extract comment content - try multiple selectors
            content_parts = comment_selector.xpath(".//div[contains(@class, 'comment-content')]//span//text()").getall()
            if not content_parts:
                content_parts = comment_selector.xpath(".//div[contains(@class, 'pb-rich-text')]//span//text()").getall()
            if not content_parts:
                # Try any span text inside the comment
                content_parts = comment_selector.xpath(".//span//text()").getall()
            content = ''.join(c.strip() for c in content_parts if c.strip())

            # Extract publish time and IP from comment-desc
            # Structure: <div class="comment-desc-left"><span>03-22</span><span> 河北</span></div>
            desc_left = comment_selector.xpath(".//div[contains(@class, 'comment-desc-left')]")
            publish_time = ''
            ip_location = ''
            if desc_left:
                time_spans = desc_left.xpath(".//span/text()").getall()
                # Parse spans: ["第X楼 ", "MM-DD", " 地点"] or ["MM-DD", " 地点"]
                for span_text in time_spans:
                    text = span_text.strip()
                    # Match time pattern like "03-07"
                    if re.match(r'^\d{2}-\d{2}$', text):
                        publish_time = text
                    # Match location (2-4 Chinese characters, not containing "楼")
                    elif text and '楼' not in text and len(text) <= 4:
                        ip_location = text
            else:
                # Fallback: look for any spans with date/location patterns
                all_spans = comment_selector.xpath(".//span/text()").getall()

                for span_text in all_spans:
                    span_text = span_text.strip()

                    # Match time pattern like "03-22" or location pattern like " 河北"
                    if re.match(r'^\d{2}-\d{2}$', span_text) and not publish_time:
                        publish_time = span_text
                    elif span_text.startswith(' ') and len(span_text.strip()) <= 4 and not ip_location:
                        ip_location = span_text.strip()

            # Sub-comment count (not directly available in new structure, loaded dynamically)
            sub_comment_count = 0

            tieba_comment = TiebaComment(
                comment_id=comment_id,
                sub_comment_count=sub_comment_count,
                content=content,
                note_url=const.TIEBA_URL + f"/p/{note_id}",
                user_link='',
                user_nickname=user_nickname,
                user_avatar=user_avatar,
                tieba_id='',
                tieba_name='',
                tieba_link='',
                ip_location=ip_location,
                publish_time=publish_time,
                note_id=note_id,
            )
            result.append(tieba_comment)

        return result

    def _extract_comments_old(self, content_selector: Selector, note_id: str) -> List[TiebaComment]:
        """
        Extract comments from old page structure
        """
        xpath_selector = "//div[@class='l_post l_post_bright j_l_post clearfix  ']"
        comment_list = content_selector.xpath(xpath_selector)
        result: List[TiebaComment] = []
        for comment_selector in comment_list:
            comment_field_value: Dict = self.extract_data_field_value(comment_selector)
            if not comment_field_value:
                continue
            tieba_name = comment_selector.xpath("//a[@class='card_title_fname']/text()").get(default='').strip()
            other_info_content = comment_selector.xpath(".//div[@class='post-tail-wrap']").get(default="").strip()
            ip_location, publish_time = self.extract_ip_and_pub_time(other_info_content)
            tieba_comment = TiebaComment(comment_id=str(comment_field_value.get("content").get("post_id")),
                                         sub_comment_count=comment_field_value.get("content").get("comment_num"),
                                         content=utils.extract_text_from_html(
                                             comment_field_value.get("content").get("content")),
                                         note_url=const.TIEBA_URL + f"/p/{note_id}",
                                         user_link=const.TIEBA_URL + comment_selector.xpath(
                                             ".//a[@class='p_author_face ']/@href").get(default='').strip(),
                                         user_nickname=comment_selector.xpath(
                                             ".//a[@class='p_author_name j_user_card']/text()").get(default='').strip(),
                                         user_avatar=comment_selector.xpath(
                                             ".//a[@class='p_author_face ']/img/@src").get(default='').strip(),
                                         tieba_id=str(comment_field_value.get("content").get("forum_id", "")),
                                         tieba_name=tieba_name, tieba_link=f"https://tieba.baidu.com/f?kw={tieba_name}",
                                         ip_location=ip_location, publish_time=publish_time, note_id=note_id, )
            result.append(tieba_comment)
        return result

    def extract_tieba_note_sub_comments(self, page_content: str, parent_comment: TiebaComment) -> List[TiebaComment]:
        """
        Extract Tieba post second-level comments from sub-comment page
        Supports both new Vue-based structure and old structure
        Args:
            page_content: HTML string of page content
            parent_comment: Parent comment object

        Returns:
            List of second-level comment objects
        """
        selector = Selector(page_content)
        comments = []

        # Try new Vue-based structure first
        new_comment_ele_list = selector.xpath("//div[@class='sub-comment-item']")

        if new_comment_ele_list:
            # New structure
            for comment_ele in new_comment_ele_list:
                comment_id = comment_ele.xpath("./@data-id").get(default='').strip()
                user_nickname = comment_ele.xpath(".//span[@class='user-name']/text()").get(default='').strip()
                user_avatar = comment_ele.xpath(".//img[@class='avatar-img']/@src").get(default='').strip()

                content_parts = comment_ele.xpath(".//div[@class='comment-content']//text()").getall()
                content = ''.join(c.strip() for c in content_parts if c.strip())

                publish_time = comment_ele.xpath(".//span[@class='time']/text()").get(default='').strip()

                comment = TiebaComment(
                    comment_id=comment_id if comment_id else str(hash(content + user_nickname)),
                    content=content,
                    user_link='',
                    user_nickname=user_nickname,
                    user_avatar=user_avatar,
                    publish_time=publish_time,
                    parent_comment_id=parent_comment.comment_id,
                    note_id=parent_comment.note_id,
                    note_url=parent_comment.note_url,
                    tieba_id=parent_comment.tieba_id,
                    tieba_name=parent_comment.tieba_name,
                    tieba_link=parent_comment.tieba_link
                )
                comments.append(comment)
        else:
            # Old structure
            comment_ele_list = selector.xpath("//li[@class='lzl_single_post j_lzl_s_p first_no_border']")
            comment_ele_list.extend(selector.xpath("//li[@class='lzl_single_post j_lzl_s_p ']"))
            for comment_ele in comment_ele_list:
                comment_value = self.extract_data_field_value(comment_ele)
                if not comment_value:
                    continue
                comment_user_a_selector = comment_ele.xpath("./a[@class='j_user_card lzl_p_p']")[0]
                content = utils.extract_text_from_html(
                    comment_ele.xpath(".//span[@class='lzl_content_main']").get(default=""))
                comment = TiebaComment(
                    comment_id=str(comment_value.get("spid")), content=content,
                    user_link=comment_user_a_selector.xpath("./@href").get(default=""),
                    user_nickname=comment_value.get("showname"),
                    user_avatar=comment_user_a_selector.xpath("./img/@src").get(default=""),
                    publish_time=comment_ele.xpath(".//span[@class='lzl_time']/text()").get(default="").strip(),
                    parent_comment_id=parent_comment.comment_id,
                    note_id=parent_comment.note_id, note_url=parent_comment.note_url,
                    tieba_id=parent_comment.tieba_id, tieba_name=parent_comment.tieba_name,
                    tieba_link=parent_comment.tieba_link)
                comments.append(comment)

        return comments

    def extract_creator_info(self, html_content: str) -> TiebaCreator:
        """
        Extract Tieba creator information from creator homepage
        Args:
            html_content: HTML string of creator homepage

        Returns:
            Tieba creator object
        """
        selector = Selector(text=html_content)
        user_link_selector = selector.xpath("//p[@class='space']/a")
        user_link: str = user_link_selector.xpath("./@href").get(default='')
        user_link_params: Dict = parse_qs(unquote(user_link.split("?")[-1]))
        user_name = user_link_params.get("un")[0] if user_link_params.get("un") else ""
        user_id = user_link_params.get("id")[0] if user_link_params.get("id") else ""
        userinfo_userdata_selector = selector.xpath("//div[@class='userinfo_userdata']")
        follow_fans_selector = selector.xpath("//span[@class='concern_num']")
        follows, fans = 0, 0
        if len(follow_fans_selector) == 2:
            follows, fans = self.extract_follow_and_fans(follow_fans_selector)
        user_content = userinfo_userdata_selector.get(default='')
        return TiebaCreator(user_id=user_id, user_name=user_name,
                            nickname=selector.xpath(".//span[@class='userinfo_username ']/text()").get(
                                default='').strip(),
                            avatar=selector.xpath(".//div[@class='userinfo_left_head']//img/@src").get(
                                default='').strip(),
                            gender=self.extract_gender(user_content),
                            ip_location=self.extract_ip(user_content),
                            follows=follows,
                            fans=fans,
                            registration_duration=self.extract_registration_duration(user_content)
                            )

    @staticmethod
    def extract_tieba_thread_id_list_from_creator_page(
        html_content: str
    ) -> List[str]:
        """
        Extract post ID list from Tieba creator's homepage
        Args:
            html_content: HTML string of creator homepage

        Returns:
            List of post IDs
        """
        selector = Selector(text=html_content)
        thread_id_list = []
        xpath_selector = (
            "//ul[@class='new_list clearfix']//div[@class='thread_name']/a[1]/@href"
        )
        thread_url_list = selector.xpath(xpath_selector).getall()
        for thread_url in thread_url_list:
            thread_id = thread_url.split("?")[0].split("/")[-1]
            thread_id_list.append(thread_id)
        return thread_id_list

    def extract_ip_and_pub_time(self, html_content: str) -> Tuple[str, str]:
        """
        Extract IP location and publish time from HTML content
        Args:
            html_content: HTML string

        Returns:
            Tuple of (IP location, publish time)
        """
        pattern_pub_time = re.compile(r'<span class="tail-info">(\d{4}-\d{2}-\d{2} \d{2}:\d{2})</span>')
        time_match = pattern_pub_time.search(html_content)
        pub_time = time_match.group(1) if time_match else ""
        return self.extract_ip(html_content), pub_time

    @staticmethod
    def extract_ip(html_content: str) -> str:
        """
        Extract IP location from HTML content
        Args:
            html_content: HTML string

        Returns:
            IP location string
        """
        pattern_ip = re.compile(r'IP属地:(\S+)</span>')
        ip_match = pattern_ip.search(html_content)
        ip = ip_match.group(1) if ip_match else ""
        return ip

    @staticmethod
    def extract_gender(html_content: str) -> str:
        """
        Extract gender from HTML content
        Args:
            html_content: HTML string

        Returns:
            Gender string ('Male', 'Female', or 'Unknown')
        """
        if GENDER_MALE in html_content:
            return 'Male'
        elif GENDER_FEMALE in html_content:
            return 'Female'
        return 'Unknown'

    @staticmethod
    def extract_follow_and_fans(selectors: List[Selector]) -> Tuple[str, str]:
        """
        Extract follow count and fan count from selectors
        Args:
            selectors: List of selector objects

        Returns:
            Tuple of (follow count, fan count)
        """
        pattern = re.compile(r'<span class="concern_num">\(<a[^>]*>(\d+)</a>\)</span>')
        follow_match = pattern.findall(selectors[0].get())
        fans_match = pattern.findall(selectors[1].get())
        follows = follow_match[0] if follow_match else 0
        fans = fans_match[0] if fans_match else 0
        return follows, fans

    @staticmethod
    def extract_registration_duration(html_content: str) -> str:
        """
        Extract Tieba age from HTML content
        Example: "<span>吧龄:1.9年</span>"
        Returns: "1.9年"

        Args:
            html_content: HTML string

        Returns:
            Tieba age string
        """
        pattern = re.compile(r'<span>吧龄:(\S+)</span>')
        match = pattern.search(html_content)
        return match.group(1) if match else ""

    @staticmethod
    def extract_data_field_value(selector: Selector) -> Dict:
        """
        Extract data-field value from selector
        Args:
            selector: Selector object

        Returns:
            Dictionary containing data-field value
        """
        data_field_value = selector.xpath("./@data-field").get(default='').strip()
        if not data_field_value or data_field_value == "{}":
            return {}
        try:
            # First use html.unescape to handle escape characters, then json.loads to convert JSON string to Python dictionary
            unescaped_json_str = html.unescape(data_field_value)
            data_field_dict_value = json.loads(unescaped_json_str)
        except Exception as ex:
            print(f"extract_data_field_value, error: {ex}, trying alternative parsing method")
            data_field_dict_value = {}
        return data_field_dict_value


def test_extract_search_note_list():
    with open("test_data/search_keyword_notes.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        result = extractor.extract_search_note_list(content)
        print(result)


def test_extract_note_detail():
    with open("test_data/note_detail.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        result = extractor.extract_note_detail(content)
        print(result.model_dump())


def test_extract_tieba_note_parment_comments():
    with open("test_data/note_comments.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        result = extractor.extract_tieba_note_parment_comments(content, "123456")
        print(result)


def test_extract_tieba_note_sub_comments():
    with open("test_data/note_sub_comments.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        fake_parment_comment = TiebaComment(comment_id="123456", content="content", user_link="user_link",
                                            user_nickname="user_nickname", user_avatar="user_avatar",
                                            publish_time="publish_time", parent_comment_id="parent_comment_id",
                                            note_id="note_id", note_url="note_url", tieba_id="tieba_id",
                                            tieba_name="tieba_name", )
        result = extractor.extract_tieba_note_sub_comments(content, fake_parment_comment)
        print(result)


def test_extract_tieba_note_list():
    with open("test_data/tieba_note_list.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        result = extractor.extract_tieba_note_list(content)
        print(result)
    pass


def test_extract_creator_info():
    with open("test_data/creator_info.html", "r", encoding="utf-8") as f:
        content = f.read()
        extractor = TieBaExtractor()
        result = extractor.extract_creator_info(content)
        print(result.model_dump_json())


if __name__ == '__main__':
    # test_extract_search_note_list()
    # test_extract_note_detail()
    # test_extract_tieba_note_parment_comments()
    # test_extract_tieba_note_list()
    test_extract_creator_info()

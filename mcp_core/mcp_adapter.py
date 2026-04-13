# mcp_adapter.py
import asyncio
from typing import Any, Dict, List, Optional

import config
from main import main as crawl_main


async def run_crawl(
    platform: str,
    crawler_type: str,
    keywords: Optional[str] = None,
    max_count: Optional[int] = None,
    is_get_comments: Optional[bool] = False,
    is_get_sub_comments: Optional[bool] = False,
    max_comments_count: Optional[int] = None,
    save_data_option: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    供 MCP 调用的协程入口：
    - 根据传入参数动态设置 config
    - 调用 main.main()
    - 返回本次爬取到的结构化数据
    """
    # 简单做法：直接改全局 config
    config.PLATFORM = platform
    config.CRAWLER_TYPE = crawler_type

    if keywords is not None:
        # 不同平台的含义略有不同，这里假设你已经在 config 里用 KEYWORDS 做统一入口
        config.KEYWORDS = keywords

    if max_count is not None:
        config.CRAWLER_MAX_NOTES_COUNT = max_count

    config.ENABLE_GET_COMMENTS = is_get_comments

    config.ENABLE_GET_SUB_COMMENTS = is_get_sub_comments

    if max_comments_count is not None:
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = max_comments_count

    if save_data_option is not None:
        config.SAVE_DATA_OPTION = save_data_option

    result = await crawl_main()

    # 统一为 list[dict]，防止 None
    if result is None:
        return []
    if isinstance(result, list):
        return result
    # 如果你某个平台返回的是 dict 或其它类型，这里做一个兜底包一层
    return [result]  # type: ignore[return-value]


def run_crawl_sync(
    platform: str,
    crawler_type: str,
    keywords: Optional[str] = None,
    max_count: Optional[int] = None,
    is_get_comments: Optional[bool] = False,
    is_get_sub_comments: Optional[bool] = False,
    max_comments_count: Optional[int] = None,
    save_data_option: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    同步封装，给 MCP 的普通函数工具用。
    """
    return asyncio.run(
        run_crawl(
            platform=platform,
            crawler_type=crawler_type,
            keywords=keywords,
            max_count=max_count,
            is_get_comments=is_get_comments,
            is_get_sub_comments=is_get_sub_comments,
            max_comments_count=max_comments_count,
            save_data_option=save_data_option
        )
    )
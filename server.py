import json
import asyncio
from mcp.server.fastmcp import FastMCP

from mcp_adapter import run_crawl_sync

mcp = FastMCP("mediacrawlermcp")

# =========================
# Tool 1 搜索帖子
# =========================
@mcp.tool()
async def crawl_media(
    platform: str,
    crawler_type: str,
    keywords: str,
    max_count: int = 10,
    is_get_comments = False,
    is_get_sub_comments = False,
    max_comments_count: int = 5,
    save_data_option: str = "",
):
    """
    搜索自媒体平台帖子、评论

    参数：
    - platform: xhs(小红书) / dy(抖音) / wb(微博) / bili(B站) / zhihu(知乎) / tieba(百度贴吧) / ks(快手)
    - crawler_type: search
    - keywords: 搜索关键词
    - max_count: 返回帖子数量
    - is_get_comments: 是否爬取评论，默认不开启，如果值为False，就不展示评论
    - is_get_sub_comments: 是否爬取子评论，默认不开启，如果值为False，就不展示子评论
    - max_comments_count: 返回帖子下评论数量以及每个评论的子评论的数量
    - save_data_option: 数据存储方式，存在情况："" / "db"，默认为空，不存储，如果需要存储数据，默认存在mysql，即值为："db"
    """

    data = await asyncio.to_thread(
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

    items = []
    if 'items' in data:
        data = data['items']
    if 'notes' in data:
        data = data['notes']
    if platform == "xhs":
        items = xhs_data(data)
    elif platform == "bili":
        items = bili_data(data)

    return json.dumps(
        {
            "platform": platform,
            "is_get_comments":is_get_comments,
            "is_get_sub_comments": is_get_sub_comments,
            "max_comments_count": max_comments_count,
            "save_data_option": save_data_option,
            "count": len(items),
            "items": items
        },
        ensure_ascii=False,
    )

def xhs_data(data):
    if not data:
        return []
    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []
        for comment in comments:
            sub_comment_list = []
            sub_comments = comment.get("sub_comments") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("content", ""),
                    "create_time": sub_comment.get("create_time", ""),
                    "like_count": sub_comment.get("like_count", ""),
                    "sub_comment_nickname": sub_comment.get("user_info", {}).get("nickname", "")
                })

            comment_list.append({
                "content": comment.get("content", ""),
                "sub_comment_count": comment.get("sub_comment_count", ""),
                "like_count": comment.get("like_count", ""),
                "comment_nickname": comment.get("user_info", {}).get("nickname", ""),
                "sub_comment_list": sub_comment_list
            })

        items.append({
            "note_id": post.get("note_id", ""),
            "title": post.get("title", ""),
            "nickname": post.get("author", {}).get("nickname") or post.get("user", {}).get("nickname", ""),
            "interact_info": post.get("interact_info", ""),
            "desc": post.get("desc", ""),
            "comments": comment_list
        })

    return items

def bili_data(data):
    if not data:
        return []
    items = []
    for post in data:
        comment_list = []
        view = post.get("View", {})
        name = post.get("Card", {}).get("card", {}).get("name", "")
        comments = post.get("comments") or []
        for comment in comments:
            sub_comment_list = []
            replies = comment.get("replies") or []
            for sub_comment in replies:
                sub_comment_list.append({
                    "content": sub_comment.get("content", "").get("message", ""),
                    "create_time": sub_comment.get("ctime", ""),
                    "like_count": sub_comment.get("like_count", ""),
                    "sub_comment_nickname": sub_comment.get("member", {}).get("uname", "")
                })

            comment_list.append({
                "content": comment.get("content", {}).get("message", ""),
                "sub_comment_count": len(sub_comment_list),
                "like_count": comment.get("like", 0),
                "comment_nickname": comment.get("member", {}).get("uname", ""),
                "sub_comment_list": sub_comment_list
            })

        items.append({
            "aid": view.get("aid", ""),
            "title": view.get("title", ""),
            "nickname": view.get("owner", {}).get("name") or name,
            "interact_info": view.get("stat", ""),
            "desc": view.get("desc", ""),
            "comments": comment_list
        })

    return items

if __name__ == "__main__":
    mcp.run()
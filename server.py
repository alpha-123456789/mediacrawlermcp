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
    # if 'items' in data:
    #     data = data['items']
    # if 'notes' in data:
    #     data = data['notes']
    if platform == "xhs":
        items = xhs_data(data)
    elif platform == "bili":
        items = bili_data(data)
    elif platform == "dy":
        items = dy_data(data)
    elif platform == "wb":
        items = wb_data(data)
    elif platform == "zhihu":
        items = zhihu_data(data)
    elif platform == "tieba":
        items = tieba_data(data)
    elif platform == "ks":
        items = ks_data(data)

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

def dy_data(data):
    """处理抖音数据"""
    if not data:
        return []
    items = []
    for post in data:
        comment_list = []
        comments = post.get("comments") or []
        for comment in comments:
            sub_comment_list = []
            sub_comments = comment.get("reply_comment") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("text", ""),
                    "create_time": sub_comment.get("create_time", ""),
                    "like_count": sub_comment.get("like_count", 0),
                    "sub_comment_nickname": sub_comment.get("user", {}).get("nickname", ""),
                    "reply_comment": sub_comment.get("reply_comment",0),
                    "digg_count": sub_comment.get("digg_count",0),
                    "user_digged": sub_comment.get("user_digged", 0),
                    "is_note_comment": sub_comment.get("is_note_comment",0)
                })

            comment_list.append({
                "content": comment.get("text", ""),
                "create_time": comment.get("create_time", ""),
                "item_comment_total": comment.get("item_comment_total", 0),
                "reply_comment_total": comment.get("reply_comment_total", 0),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user", {}).get("nickname", ""),
                "digg_count": comment.get("digg_count",0),
                "user_digged": comment.get("user_digged",0),
                "is_note_comment": comment.get("is_note_comment", 0),
                "sub_comment_list": sub_comment_list
            })

        items.append({
            "create_time":post.get("create_time",""),
            "aweme_id": post.get("aweme_id", ""),
            "nickname": post.get("author", {}).get("nickname", ""),
            "interact_info": post.get("statistics", ""),
            "desc": post.get("desc", ""),
            "comments": comment_list
        })

    return items

def wb_data(data):
    """处理微博数据"""
    if not data:
        return []
    items = []
    for post in data:
        comment_list = []
        mblog = post.get("mblog", {})
        comments = post.get("comments") or []
        for comment in comments:
            sub_comment_list = []
            sub_comments = comment.get("comments") or []
            for sub_comment in sub_comments:
                sub_comment_list.append({
                    "content": sub_comment.get("text", ""),
                    "create_time": sub_comment.get("created_at", ""),
                    # "like_count": sub_comment.get("like_count", ""),
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

        items.append({
            "created_at": mblog.get("created_at", ""),
            "note_id": mblog.get("id", ""),
            "nickname": mblog.get("user", {}).get("screen_name", ""),
            "interact_info": {"reposts_count": mblog.get("reposts_count", 0), "comments_count": mblog.get("comments_count", 0), "attitudes_count": mblog.get("attitudes_count", 0), "fans": mblog.get("fans", 0)},
            "desc": mblog.get("text", ""),
            # "pics":mblog.get("pics", ""),
            "comments": comment_list
        })

    return items

def zhihu_data(data):
    """处理知乎数据"""
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
                "sub_comment_count": comment.get("sub_comment_count", ""),
                "like_count": comment.get("like_count", 0),
                "user_nickname": comment.get("user_nickname", 0),
            })

        items.append({
            "note_id": post.get("content_id", ""),
            "title": post.get("title", ""),
            "nickname": post.get("user_nickname", ""),
            "interact_info": {"voteup_count": post.get("voteup_count", 0), "comment_count": post.get("comment_count", 0)},
            "desc": post.get("desc", ""),
            "content_text": post.get("content_text", ""),
            "comments": comment_list
        })


    return items

def tieba_data(data):
    """处理百度贴吧数据"""
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
                "sub_comment_count": comment.get("sub_comment_count", ""),
                "like_count": comment.get("like_count", 0),
                "comment_nickname": comment.get("user_nickname", ""),
                "ip_location": comment.get("ip_location", "")
            })

        items.append({
            "note_id": post.get("note_id", ""),
            "title": post.get("title", ""),
            "nickname": post.get("user_nickname", ""),
            "interact_info": {
                "total_replay_num": post.get("total_replay_num", 0),
                "like_count": post.get("like_count", 0),
                "collect_count": post.get("collect_count", 0),
                "total_replay_page": post.get("total_replay_page", 0),
                "ip_location": post.get("ip_location", "")
            },

            "desc": post.get("desc", ""),
            "comments": comment_list
        })


    return items

def ks_data(data):
    """处理快手数据"""
    if not data:
        return []
    items = []
    for post in data:
        photo = post.get("photo", {})
        comments = post.get("comments") or []

        items.append({
            "note_id": photo.get("id", ""),
            "caption": photo.get("caption", ""),
            "originCaption": photo.get("originCaption", ""),
            "nickname": photo.get("author", {}).get("name", ""),
            "interact_info": {
                "likeCount": photo.get("likeCount", 0),
                "viewCount": photo.get("viewCount", 0),
                "duration": photo.get("duration", 0),
                "commentCount": photo.get("commentCount", 0),
                "realLikeCount": photo.get("realLikeCount", 0),

            },
            "comments": comments
        })

    return items

if __name__ == "__main__":
    mcp.run()
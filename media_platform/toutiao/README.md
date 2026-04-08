# 今日头条爬虫框架

## 框架结构

```
media_platform/toutiao/
├── __init__.py      # 导出核心类
├── core.py          # 爬虫主逻辑 (ToutiaoCrawler)
├── client.py        # API客户端 (ToutiaoClient)
├── login.py         # 登录模块 (ToutiaoLogin)
├── field.py         # 枚举定义 (SearchOrderType, CommentOrderType)
├── exception.py     # 自定义异常 (DataFetchError, IPBlockError, LoginError)
├── help.py          # 工具函数
└── README.md        # 本文档
```

## 已集成的组件

### 1. 主程序集成 (main.py)
- 在 `CrawlerFactory.CRAWLERS` 中注册 `"toutiao": ToutiaoCrawler`

### 2. MCP服务器集成 (mcp_server.py)
- `Platform` 枚举添加 `TOUTIAO = "toutiao"`
- `PLATFORM_NAMES` 添加 `'toutiao': '今日头条'`

### 3. 配置集成 (config/)
- `toutiao_config.py`: 今日头条专属配置
- `base_config.py`: 平台列表添加 `toutiao`

### 4. 存储集成 (store/toutiao/)
- `_store_impl.py`: 各类存储实现 (CSV/JSON/JSONL/DB/MongoDB/Excel)
- `__init__.py`: 存储工厂和数据处理函数

## 核心类说明

### ToutiaoCrawler (core.py)
继承 `AbstractCrawler`，实现方法:
- `start()`: 爬虫入口，返回文章列表
- `search()`: 关键词搜索
- `get_specified_articles()`: 获取指定文章详情
- `batch_get_article_comments()`: 批量获取评论
- `get_creators_and_articles()`: 获取创作者及其文章

### ToutiaoClient (client.py)
继承 `AbstractApiClient`，实现API调用:
- `search_article_by_keyword()`: 搜索文章
- `get_article_detail()`: 获取文章详情
- `get_article_comments()`: 获取评论
- `get_article_all_comments()`: 获取所有评论（分页）
- `parse_search_results()`: 解析搜索结果

### ToutiaoLogin (login.py)
继承 `AbstractLogin`，实现登录:
- `login_by_qrcode()`: 二维码登录
- `login_by_mobile()`: 手机号登录
- `login_by_cookies()`: Cookie登录

## 数据字段映射

### 文章字段
| 标准字段 | 今日头条字段 |
|---------|------------|
| article_id | id / group_id |
| title | title |
| abstract | abstract / summary |
| content | content |
| author | source / media_name |
| read_count | read_count / go_detail_count |
| like_count | like_count / digg_count |
| comment_count | comment_count |
| share_count | share_count |
| publish_time | publish_time / behot_time |

### 评论字段
| 标准字段 | 今日头条字段 |
|---------|------------|
| comment_id | id / comment_id |
| content | content / text |
| create_time | create_time / publish_time |
| like_count | digg_count / like_count |
| reply_count | reply_count |
| user_id | user_id |
| nickname | user_name / name |

## 接口说明

### 搜索接口
```
GET https://so.toutiao.com/search
Params:
  - keyword: 搜索关键词
  - offset: 偏移量 (分页)
  - count: 每页数量
  - sort_by: 排序 (time/hot)
```

### 评论接口
```
GET https://www.toutiao.com/article/v4/tab_comments/
Params:
  - aid: 24 (固定)
  - group_id: 文章ID
  - offset: 偏移量
  - count: 数量
```

### 文章详情
```
GET https://www.toutiao.com/article/{article_id}/
```

## 使用示例

### 命令行运行
```bash
# 设置环境变量
set PLATFORM=toutiao
set KEYWORDS=AI新闻
set CRAWLER_TYPE=search
set ENABLE_GET_COMMENTS=true

# 运行
uv run python main.py
```

### MCP调用
```python
result = await crawl_media(
    platform="toutiao",
    keywords="AI新闻",
    max_count=20,
    is_get_comments=True
)
```

## 注意事项

1. **接口变更**: 今日头条接口可能变化，需要根据实际情况调整 `client.py`
2. **数据解析**: 搜索结果的解析逻辑在 `parse_search_results()` 中，需根据实际返回调整
3. **反爬策略**: 建议合理控制请求频率，使用 Cookie 登录方式
4. **存储扩展**: 如需数据库存储，需在 `database/models.py` 创建对应模型

## 待完善项

1. [ ] `ToutiaoDbStoreImplement`: 实现完整的数据库存储逻辑
2. [ ] `ToutiaoMongoStoreImplement`: 实现 MongoDB 存储
3. [ ] 数据库模型: 创建 `ToutiaoArticle`, `ToutiaoComment`, `ToutiaoCreator` 模型
4. [ ] API签名: 如接口需要签名验证，需添加签名逻辑
5. [ ] 子评论: 如需支持二级评论，需在 `client.py` 中实现

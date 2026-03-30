# MediaCrawler MCP 项目指南

## 项目概述

这是 MediaCrawler 的 MCP (Model Context Protocol) 服务器实现，支持爬取小红书、抖音、快手、B站、微博、贴吧、知乎等平台数据。

## 核心用法：`crawl_media` 工具

**爬取数据并自动生成舆情分析报告**

```
crawl_media(
    platform="xhs",          # 平台: xhs/dy/ks/bili/wb/tieba/zhihu
    crawler_type="search",   # 类型: search/detail/creator
    keywords="宝宝巴士",    # 搜索关键词
    max_count=20,            # 爬取数量 (1-100)
    is_get_comments=true,    # 是否获取评论
    max_comments_count=10,   # 每条评论数 (0-50)
    output_path="reports"    # 报告输出目录
)
```

**返回数据结构：**
```json
{
    "status": "success",
    "platform": "bili",
    "platform_name": "B站",
    "keywords": "宝宝巴士",
    "report_path": "D:\\mcp_work\\mediacrawlermcp\\reports\\B站_宝宝巴士_趋势报告_xxx.html",
    "relative_path": "reports\\B站_宝宝巴士_趋势报告_xxx.html",
    "summary": "控制台可读的舆情分析摘要",
    "html_content": "完整的HTML报告内容",
    "message": "舆情分析报告已生成"
}
```

**返回字段说明：**
- `report_path`: 绝对路径，可点击打开
- `relative_path`: 相对路径
- `summary`: 控制台可显示的文本摘要
- `html_content`: 完整HTML内容（客户端可自行保存）

## 示例场景

### 场景1：小红书品牌舆情监测
```python
# 分析小红书关于"完美日记"的用户反馈
result = await crawl_media(
    platform="xhs",
    keywords="完美日记",
    max_count=50,
    is_get_comments=True
)
print(result["summary"])  # 显示分析摘要
```

### 场景2：B站热点话题分析
```python
# 抓取B站"宝宝巴士"相关内容做舆情分析
result = await crawl_media(
    platform="bili",
    crawler_type="search",
    keywords="宝宝巴士广告",
    max_count=2,
    is_get_comments=True,
    max_comments_count=3
)
# 报告保存在 MCP 项目 reports 目录下
# 可直接点击 report_path 打开
```

### 场景3：竞品对比分析（多平台）
```python
# 分别分析B站和抖音上的同一品牌
bili_result = await crawl_media(platform="bili", keywords="宝宝巴士")
dy_result = await crawl_media(platform="dy", keywords="宝宝巴士")
```

## 生成的报告内容

HTML 报告自动包含：
1. 📈 核心数据概览（内容数、评论数、情感分布）
2. 💭 情感分析可视化（饼图）
3. ☁️ 热门讨论词云
4. 💡 舆情洞察与分析建议
5. 💬 代表性评论展示
6. 📎 可点击的报告文件链接（HTML底部）

## 本地开发命令

```bash
# 安装依赖
uv sync

# 安装浏览器驱动
uv run playwright install

# 启动 MCP 服务器
uv run python mcp_server.py

# 运行测试
uv run pytest
```

## 文件说明

- `mcp_server.py` - MCP 服务器主文件，提供 `crawl_media` 接口
- `report_generator.py` - 报告生成器（含情感分析），生成 HTML 舆情报告
- `mcp_adapter.py` - 爬虫适配器

## 技能文件

项目包含 Claude Code Skill：`.claude/skills/media-crawl-analyze.json`

触发关键词：爬取、舆情分析、热度分析、趋势报告等

# MediaCrawler MCP 项目指南

## 项目概述

这是 MediaCrawler 的 MCP (Model Context Protocol) 服务器实现，支持爬取小红书、抖音、快手、B站、微博、贴吧、知乎等平台数据。

## 🚀 报告生成模式

**默认使用 `auto` 模式**，自动检测 LLM 配置：配置了 LLM 则使用 AI 动态生成报告，否则使用脚本生成静态报告。用户可通过 `report_mode` 参数主动选择模式。

### 使用流程

```python
# 默认 AI 生成（推荐）
result = await crawl_media(
    platform="bili",
    keywords="宝宝巴士",
    max_count=20,
    is_get_comments=True
)

# 返回包含 prompt，Claude 根据数据特征生成独特的报告
```

### 为什么更好？

| 特性 | AI 动态生成 | 脚本静态生成 |
|-----|------------|-------------|
| 报告风格 | 根据数据特征智能设计 | 固定模板 |
| 配色主题 | 动态选择（粉紫/蓝紫/暖色等） | 3套预设 |
| 模块内容 | 根据有的数据自动组合 | 固定模块 |
| 洞察力 | 基于真实数据的独特分析 | 固定话术 |
| 适用场景 | 默认推荐 | 用户明确要求静态/统一格式 |

| 数据类型 | AI 生成的报告特点 |
|---------|----------------|
| B站视频（有播放量+弹幕） | 粉紫主题 + 播放趋势图 + 弹幕情感分析 |
| 小红书（有点赞+评论） | 蓝紫主题 + 种草分析 + 用户反馈 |
| 知乎（有赞同+评论） | 学术蓝主题 + 观点分布 + 争议识别 |

**每个报告都是独一无二的，根据真实数据特征定制！**

---

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

**返回数据结构（AI 模式默认）：**
```json
{
    "status": "success",
    "platform": "bili",
    "platform_name": "B站",
    "keywords": "宝宝巴士",
    "report_mode": "ai",
    "prompt": "给 AI 的完整提示词...",
    "data_profile": { "数据画像..." },
    "message": "AI 报告数据已生成"
}
```

**AI 模式返回字段说明：**
- `report_mode`: 报告模式，默认 "ai"
- `prompt`: 给 AI 的完整提示词，Claude 据此生成报告
- `data_profile`: 数据画像（数据结构、统计信息等）
- `message`: 操作结果说明

**脚本模式返回（当 report_mode="script"）：**
```json
{
    "status": "success",
    "platform": "bili",
    "report_mode": "script",
    "report_path": ".../B站_宝宝巴士_脚本报告_xxx.html",
    "summary": "控制台可读的舆情分析摘要",
    "html_content": "完整的HTML报告内容"
}
```

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

### 场景3：竞品对比分析（多平台合并报告）⭐ 推荐
```python
# 同时抓取多个平台，生成一个统一的合并报告
result = await crawl_multi_platform(
    platforms=["bili", "dy", "xhs"],  # 同时抓取B站、抖音、小红书
    crawler_type="search",
    keywords="宝宝巴士",
    max_count=20,
    is_get_comments=True,
    max_comments_count=10
)
# 生成一个包含所有平台数据的统一报告
print(result["platforms"])       # ["bili", "dy", "xhs"]
print(result["platform_names"])  # ["B站", "抖音", "小红书"]
print(result["summary"])         # 多平台综合分析摘要
```

**多平台报告特点：**
- 一个报告包含所有平台数据，便于对比分析
- 展示各平台数据分布比例
- 跨平台热词統一分析
- 各平台情感倾向对比
- 分平台内容策略建议

### 场景4：使用脚本生成（静态模板）
```python
# 当用户明确要求静态/统一格式时使用
result = await crawl_media(
    platform="bili",
    keywords="宝宝巴士",
    report_mode="script"  # "用脚本生成"、"静态报告"、"统一格式"
)
print(result["report_path"])  # 直接返回 HTML 文件路径
```

## 多平台抓取：`crawl_multi_platform` 工具

**当有对比多个平台数据需求时，使用此工具生成统一报告**

```
crawl_multi_platform(
    platforms=["xhs", "dy", "bili"],  # 平台列表
    crawler_type="search",           # 类型: search/detail/creator
    keywords="宝宝巴士",            # 搜索关键词
    max_count=20,                    # 每个平台爬取数量
    is_get_comments=true,            # 是否获取评论
    max_comments_count=10,           # 每条评论数
    output_path="reports"            # 报告输出目录
)
```

**返回数据结构：**
```json
{
    "status": "success",
    "platforms": ["xhs", "dy", "bili"],
    "platform_names": ["小红书", "抖音", "B站"],
    "keywords": "宝宝巴士",
    "report_mode": "ai_enhanced",
    "report_path": ".../多平台_宝宝巴士_舆情分析报告_xxx.html",
    "summary": "多平台综合分析摘要...",
    "total_items": 60,
    "platform_breakdown": {
        "xhs": 20,
        "dy": 20,
        "bili": 20
    },
    "message": "多平台舆情分析报告已生成: ..."
}
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

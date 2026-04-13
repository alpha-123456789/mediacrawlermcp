# MediaCrawler MCP 项目指南

## 项目概述

这是 MediaCrawler 的 MCP (Model Context Protocol) 服务器实现，支持爬取小红书、抖音、快手、B站、微博、贴吧、知乎、今日头条等平台数据。

## 🚀 报告生成模式

**默认使用 `auto` 模式**，自动检测 LLM 配置：配置了 LLM 则使用 AI 动态生成报告，否则使用脚本生成静态报告。用户可通过 `report_mode` 参数主动选择模式。

### 三种报告模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `auto`(默认) | 自动检测：配置了 LLM 则用 AI，否则用脚本 | 无需关心底层实现，一键使用 |
| `ai` | 强制使用 LLM 根据数据特征动态设计报告 | 需要灵活、个性化的分析 |
| `script` | 强制使用预设模板生成统一格式报告 | 需要固定格式、批量对比、离线使用 |

### 十种报告类型 (`report_type`)

| 类型 | 代码 | 说明 |
|------|------|------|
| 舆情分析 | `sentiment`(默认) | 情感分布、正负面分析、舆情洞察 |
| 趋势分析 | `trend` | 热度趋势、时间线分析、变化预测 |
| 热点话题 | `hot_topics` | 热门话题识别、话题聚类、传播路径 |
| 关键词分析 | `keyword` | 关键词频率、关联词、语义网络 |
| 传播量分析 | `volume` | 传播量统计、峰值检测、平台分布 |
| 病毒传播 | `viral_spread` | 传播节点、裂变路径、KOL影响 |
| 达人分析 | `influencer` | KOL识别、影响力评估、合作建议 |
| 受众分析 | `audience` | 用户画像、兴趣分布、活跃时段 |
| 竞品对比 | `comparison` | 竞品提取、对比分析、优劣势 |
| 风险预警 | `risk` | 风险识别、危机预警、应对建议 |

---

## 核心用法：`crawl_media` 工具

**爬取数据并自动生成舆情分析报告**

```
crawl_media(
    platform="xhs",          # 平台: xhs/dy/ks/bili/wb/tieba/zhihu/toutiao
    crawler_type="search",   # 类型: search/detail/creator
    keywords="宝宝巴士",     # 搜索关键词
    max_count=20,            # 爬取数量 (1-100)
    is_get_comments=true,    # 是否获取评论
    is_get_sub_comments=false, # 是否获取子评论
    max_comments_count=10,   # 每条评论数 (0-50)
    report_type="sentiment", # 报告类型 (10种)
    report_mode="auto",      # 报告模式: auto/ai/script
    save_data_option="",     # 存储: "" 或 "db"
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
    "report_mode": "ai",
    "report_path": "绝对路径/舆情分析报告_xxx.html",
    "relative_path": "reports/舆情分析报告_xxx.html",
    "summary": "控制台可读的舆情分析摘要",
    "has_ai_config": true,
    "verification_samples": [/* 前3条数据各含2条评论 */],
    "message": "报告已生成"
}
```

**返回字段说明：**
- `report_mode`: 实际使用的报告模式 (`"script"` 或 `"ai_enhanced"`)
- `report_path`: 报告文件绝对路径
- `relative_path`: 报告文件相对路径
- `summary`: 可读的分析摘要
- `has_ai_config`: 是否检测到 LLM 配置
- `verification_samples`: 前3条数据各含2条评论，用于验证数据真实性

**爬取数据自动保存：** 处理后的原始数据自动保存到 `original_data/` 目录下的 JSON 文件。

---

## 多平台抓取：`crawl_multi_platform` 工具

**当有对比多个平台数据需求时，使用此工具生成统一报告**

```
crawl_multi_platform(
    platforms=["xhs", "dy", "bili"],  # 平台列表
    crawler_type="search",           # 类型: search/detail/creator
    keywords="宝宝巴士",             # 搜索关键词
    max_count=20,                    # 每个平台爬取数量
    is_get_comments=true,            # 是否获取评论
    is_get_sub_comments=false,       # 是否获取子评论
    max_comments_count=10,           # 每条评论数
    report_type="sentiment",         # 报告类型 (10种)
    report_mode="auto",              # 报告模式: auto/ai/script
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
    "report_path": "绝对路径/多平台_宝宝巴士_舆情分析报告_xxx.html",
    "relative_path": "reports/多平台_宝宝巴士_舆情分析报告_xxx.html",
    "summary": "多平台综合分析摘要...",
    "total_items": 60,
    "platform_breakdown": {
        "xhs": 20,
        "dy": 20,
        "bili": 20
    },
    "verification_samples": {/* 各平台前3条 */},
    "message": "多平台舆情分析报告已生成"
}
```

**多平台报告特点：**
- 一个报告包含所有平台数据，便于对比分析
- 展示各平台数据分布比例
- 跨平台热词统一分析
- 各平台情感倾向对比
- 分平台内容策略建议
- 单个平台失败不会中断整个操作

---

## 辅助工具

| 工具名 | 功能 |
|--------|------|
| `get_platforms` | 获取支持的平台列表（代码、名称、描述） |
| `get_crawler_types` | 获取支持的爬取类型说明 |

---

## 示例场景

### 场景1：小红书品牌舆情监测
```python
result = await crawl_media(
    platform="xhs",
    keywords="完美日记",
    max_count=50,
    is_get_comments=True
)
print(result["summary"])
```

### 场景2：B站热点话题分析
```python
result = await crawl_media(
    platform="bili",
    crawler_type="search",
    keywords="宝宝巴士广告",
    max_count=20,
    is_get_comments=True,
    max_comments_count=10
)
```

### 场景3：竞品对比分析（多平台合并报告）
```python
result = await crawl_multi_platform(
    platforms=["bili", "dy", "xhs"],
    crawler_type="search",
    keywords="宝宝巴士",
    max_count=20,
    is_get_comments=True,
    max_comments_count=10
)
```

### 场景4：风险预警报告
```python
result = await crawl_media(
    platform="wb",
    keywords="品牌危机",
    report_type="risk",
    is_get_comments=True
)
```

### 场景5：使用脚本生成（静态模板）
```python
result = await crawl_media(
    platform="bili",
    keywords="宝宝巴士",
    report_mode="script"
)
print(result["report_path"])
```

---

## 评论采集说明

`is_get_sub_comments` 控制是否爬取子评论（二级评论），`max_comments_count` 同时控制一级评论数量和每条一级评论下的子评论数量。

**子评论数据流：** 各平台爬虫获取子评论后，会自动合并到一级评论的对应字段中（如 B 站的 `replies`、小红书的 `sub_comments`、抖音的 `reply_comment` 等），确保 `process_*_data` 能正确提取完整子评论，而非仅 API 默认预览的少量子评论。

| 平台 | 子评论字段 | 说明 |
|------|-----------|------|
| B站 | `replies` | 替换 API 预览数据，合并完整子评论 |
| 小红书 | `sub_comments` | 合并分页获取的完整子评论 |
| 抖音 | `reply_comment` | 收集所有分页子评论后替换 |
| 快手 | `subCommentsV2` | 合并 V2 API 获取的完整子评论 |
| 微博 | `comments` | 子评论嵌入一级评论中，无需额外处理 |
| 贴吧 | `sub_comment_list` | 合并 Playwright 获取的完整子评论 |
| 知乎 | `sub_comment_list` | 合并分页获取的完整子评论 |
| 今日头条 | `sub_comments` | 已正确实现 in-place 合并 |

---

## AI 报告生成管线

### 文件架构

```
reporting/ai_report_generator.py   → 准备数据 + 构建提示词
reporting/llm_report_generator.py  → 调用 LLM API + 生成 HTML 报告
reporting/auto_field_detector.py   → 自动字段映射（无需硬编码平台字段）
```

### AI 报告特性

- **自动字段检测**：`AutoFieldDetector` 通过语义匹配自动将平台字段映射为标准字段（likes/views/comments/shares/favorites/coins/followers/duration），支持命名规范检测和置信度评分
- **竞品提取**：AI 报告自动从内容和评论中提取竞品品牌提及（内置母婴/美妆/数码/汽车/快消/电商/游戏/外卖等行业品牌词典）
- **动态模块组合**：根据数据特征自动选择报告模块（有竞品数据才显示竞品模块，情感/风险类型才显示评论分析等）
- **10种报告类型**：每种类型有独特的分析重点、可视化要求和主题配色

### LLM 配置

**方式1：OpenAI 兼容格式（推荐，支持 DeepSeek、硅基流动等）**
```bash
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

**方式2：Anthropic 原生 API**
```bash
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

**模型选择优先级：** `ANTHROPIC_DEFAULT_SONNET_MODEL` > `ANTHROPIC_DEFAULT_OPUS_MODEL` > `ANTHROPIC_DEFAULT_HAIKU_MODEL` > `LLM_MODEL` > 默认 `claude-sonnet-4-6`

---

## CDP 浏览器模式

项目支持通过 Chrome DevTools Protocol 连接用户真实浏览器，提高反检测能力。

**配置项（`config/base_config.py`）：**
- `ENABLE_CDP_MODE = True` — 启用 CDP 模式
- `CDP_DEBUG_PORT = 9222` — CDP 调试端口
- `CUSTOM_BROWSER_PATH = ""` — 自定义浏览器路径
- `CDP_HEADLESS = False` — 是否无头模式
- `BROWSER_LAUNCH_TIMEOUT = 60` — 浏览器启动超时
- `AUTO_CLOSE_BROWSER = True` — 自动关闭浏览器

---

## 本地开发命令

```bash
# 安装依赖
uv sync

# 安装浏览器驱动
uv run playwright install chromium

# 启动 MCP 服务器
uv run python mcp_server.py

# 运行测试
uv run pytest
```

## 文件说明

- `mcp_server.py` — MCP 服务器主文件，提供 4 个工具（crawl_media, crawl_multi_platform, get_platforms, get_crawler_types）
- `mcp_core/mcp_adapter.py` — 爬虫适配器，桥接 MCP 和底层爬虫
- `reporting/report_generator.py` — 脚本报告生成器（含情感分析），支持 11 种报告类型
- `reporting/ai_report_generator.py` — AI 报告数据准备和提示词构建
- `reporting/llm_report_generator.py` — LLM API 调用和 HTML 报告生成
- `reporting/auto_field_detector.py` — 自动字段映射，消除硬编码平台字段依赖
- `tools/cdp_browser.py` — CDP 浏览器管理器

## 技能文件

项目包含 Claude Code Skill：`.claude/skills/media-crawl-analyze.json`

触发关键词：爬取、舆情分析、热度分析、趋势报告等

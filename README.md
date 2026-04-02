# 🔥 MediaCrawler MCP - 自媒体平台爬虫

> 本项目基于 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 修改，添加了 MCP Server 支持

一个支持多平台自媒体数据采集的 MCP 服务，可在 Claude Code、Cursor 等 AI 编辑器中直接调用。

## ✨ 支持平台

| 平台 | 代码 | 功能 |
|------|------|------|
| 小红书 | xhs | 关键词搜索、评论采集 |
| 抖音 | dy | 关键词搜索、评论采集 |
| 快手 | ks | 关键词搜索、评论采集 |
| B站 | bili | 关键词搜索、评论采集 |
| 微博 | wb | 关键词搜索、评论采集 |
| 百度贴吧 | tieba | 关键词搜索、评论采集 |
| 知乎 | zhihu | 关键词搜索、评论采集 |

## 📋 环境安装

### 1. 安装 uv（推荐）

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装依赖

```bash
# 进入项目目录
cd mediacrawlermcp

# 安装 Python 依赖
uv sync

# 安装浏览器驱动（会自动下载所需 Node.js 运行时）
uv run playwright install chromium
```

> **注意**：如果你需要本地开发/构建文档站点，则需要额外安装 Node.js >= 16.0.0

## 🤖 MCP 配置

### Claude Code / Cursor 配置

#### macOS / Linux

创建 `.claude/settings.json`：

```json
{
  "mcpServers": {
    "mediacrawler": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

#### Windows（推荐）

使用 cmd 切换目录后执行：

```json
{
  "mcpServers": {
    "mediacrawler": {
      "command": "cmd",
      "args": [
        "/c",
        "cd /d D:\\mcp_work\\mediacrawlermcp && uv run python mcp_server.py"
      ]
    }
  }
}
```

#### Windows（备用：直接调用虚拟环境 Python）

如果 `uv` 命令有问题，可以直接调用虚拟环境的 Python（注意：必须先 cd 到项目目录）：

```json
{
  "mcpServers": {
    "mediacrawler": {
      "command": "cmd",
      "args": [
        "/c",
        "cd /d D:\\mcp_work\\mediacrawlermcp && .venv\\Scripts\\python.exe mcp_server.py"
      ]
    }
  }
}
```

## 🚀 使用方法

配置完成后，在 AI 编辑器中直接使用自然语言或结构化参数爬取内容。

### 1. crawl_media 工具 - 单平台爬取

**基本用法：**

```python
# 爬取小红书关于"完美日记"的帖子和评论
result = await crawl_media(
    platform="xhs",
    crawler_type="search",
    keywords="完美日记",
    max_count=50,
    is_get_comments=True,
    max_comments_count=10
)
```

**参数说明：**

| 参数 | 必填 | 说明 | 可选值 |
|------|------|------|--------|
| `platform` | 是 | 平台代码 | `xhs`, `dy`, `ks`, `bili`, `wb`, `tieba`, `zhihu` |
| `crawler_type` | 否 | 爬取类型 | `search`(默认), `detail`, `creator` |
| `keywords` | 是 | 搜索关键词 | 任意文本 |
| `max_count` | 否 | 爬取数量 | 1-100，默认20 |
| `is_get_comments` | 否 | 是否获取评论 | `true`/`false`，默认`false` |
| `max_comments_count` | 否 | 每条帖子的评论数 | 0-50，默认10 |
| `report_mode` | 否 | 报告模式 | `auto`(默认), `ai`, `script` |
| `output_path` | 否 | 报告输出目录 | 默认`reports` |

**自然语言示例：**

```
搜索小红书上关于"Python编程"的热门帖子
爬取B站关于"宝宝巴士"的视频和评论
用脚本模式生成抖音"美食探店"的舆情报告
```

### 2. crawl_multi_platform 工具 - 多平台爬取

**同时抓取多个平台，生成统一报告**，便于对比分析各平台舆情差异。

**基本用法：**

```python
# 同时抓取B站、抖音、小红书三个平台的数据
result = await crawl_multi_platform(
    platforms=["bili", "dy", "xhs"],
    crawler_type="search",
    keywords="宝宝巴士",
    max_count=20,
    is_get_comments=True,
    max_comments_count=10
)
```

**多平台报告特点：**
- 一个HTML报告包含所有平台数据
- 展示各平台内容分布比例
- 跨平台热词統一分析
- 各平台情感倾向对比
- 分平台内容策略建议

**参数说明：**

| 参数 | 必填 | 说明 | 可选值 |
|------|------|------|--------|
| `platforms` | 是 | 平台代码列表 | `["xhs"]`, `["bili", "dy"]`, 等 |
| `crawler_type` | 否 | 爬取类型 | `search`(默认), `detail`, `creator` |
| `keywords` | 是 | 搜索关键词 | 任意文本 |
| `max_count` | 否 | 每个平台爬取数量 | 1-100，默认20 |
| `is_get_comments` | 否 | 是否获取评论 | `true`/`false`，默认`false` |
| `max_comments_count` | 否 | 每条帖子的评论数 | 0-50，默认10 |
| `report_mode` | 否 | 报告模式 | `auto`(默认), `ai`, `script` |
| `output_path` | 否 | 报告输出目录 | 默认`reports` |

**自然语言示例：**

```
抓取B站、抖音、小红书三个平台关于"国潮品牌"的内容做对比分析
同时分析微博和知乎上"新能源汽车"的讨论热度
使用脚本模式生成多平台对比报告
```

### 3. 辅助工具

| 工具名 | 功能 | 用法 |
|--------|------|------|
| `get_platforms` | 获取支持的平台列表 | 显示所有可爬取的平台代码和名称 |
| `get_crawler_types` | 获取支持的爬取类型 | 显示可用的爬取类型说明 |

### 报告模式说明

爬取完成后自动生成舆情分析报告：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `auto`(默认) | 自动检测：配置了 LLM 则用 AI，否则用脚本 | 无需关心底层实现，一键使用 |
| `ai` | 强制使用 LLM 根据数据特征动态设计报告 | 需要灵活、个性化的分析 |
| `script` | 强制使用预设模板生成统一格式报告 | 需要固定格式、批量对比、离线使用 |

**⚠️ AI 模式需要配置 LLM API**

使用 AI 模式前，需要配置以下环境变量之一：

**方式1：OpenAI 兼容格式（推荐，支持 DeepSeek、硅基流动等）**
```bash
# .env 文件或环境变量
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1  # 或其他兼容端点
LLM_MODEL=deepseek-chat  # 模型名称
```

**方式2：Anthropic 原生 API**
```bash
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com  # 可选
```

**常用模型配置参考：**
| 服务商 | OPENAI_BASE_URL | LLM_MODEL |
|--------|-----------------|-----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-72B-Instruct` |
| 阿里云百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-max` |
| 自部署 | `http://localhost:8000/v1` | 你的模型名称 |

> **注意**：AI 模式会调用 LLM API 生成报告，可能产生 API 调用费用。如需离线使用，请切换到 `script` 模式。

**单平台返回示例：**
```json
{
  "status": "success",
  "platform": "bili",
  "platform_name": "B站",
  "report_mode": "ai",
  "keywords": "宝宝巴士",
  "summary": "舆情分析摘要...",
  "report_path": "reports/舆情分析报告_xxx.html"
}
```

**多平台返回示例：**
```json
{
  "status": "success",
  "platforms": ["bili", "dy", "xhs"],
  "platform_names": ["B站", "抖音", "小红书"],
  "report_mode": "ai_enhanced",
  "keywords": "宝宝巴士",
  "total_items": 60,
  "summary": "多平台综合分析摘要...",
  "report_path": "reports/多平台_宝宝巴士_舆情分析报告_xxx.html"
}
```

### 完整使用示例

**示例1：单平台舆情监测**
```python
# 分析小红书关于"完美日记"的用户反馈
result = await crawl_media(
    platform="xhs",
    keywords="完美日记",
    max_count=50,
    is_get_comments=True
)
```

**示例2：多平台对比分析**
```python
# 同时抓取三个平台，生成对比报告
result = await crawl_multi_platform(
    platforms=["bili", "dy", "xhs"],
    keywords="国潮品牌",
    max_count=30,
    is_get_comments=True
)
```

**示例3：静态报告（固定格式）**
```python
# 需要统一格式、批量对比时使用
result = await crawl_media(
    platform="bili",
    keywords="宝宝巴士",
    report_mode="script"
)
```

## 📁 项目结构

```
.
├── mcp_server.py        # MCP 服务入口
├── mcp_adapter.py       # 爬虫适配器
├── report_generator.py  # 舆情分析报告生成器
├── ai_report_generator.py # AI 报告提示词生成器
├── media_platform/      # 各平台爬虫实现
├── config/             # 配置文件
├── store/              # 数据存储
├── reports/            # 生成的报告输出目录
└── pyproject.toml      # 项目依赖
```

## ⚠️ 免责声明

本项目仅供学习研究使用，禁止用于商业用途和非法活动。使用本项目即表示你同意承担所有相关责任。

原始项目：https://github.com/NanmiCoder/MediaCrawler

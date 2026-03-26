# 🔥 MediaCrawler MCP - 自媒体平台爬虫

> 本项目基于 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 修改，添加了 MCP Server 支持

一个支持多平台自媒体数据采集的 MCP 服务，可在 Claude Code、Cursor 等 AI 编辑器中直接调用。

## ✨ 支持平台

| 平台 | 代码 | 功能 |
|------|------|------|
| 小红书 | xhs | 关键词搜索、帖子详情、评论、创作者主页 |
| 抖音 | dy | 关键词搜索、视频详情、评论、用户主页 |
| 快手 | ks | 关键词搜索、视频详情、评论 |
| B站 | bili | 关键词搜索、视频详情、评论、用户主页 |
| 微博 | wb | 关键词搜索、帖子详情、评论 |
| 百度贴吧 | tieba | 关键词搜索、帖子详情、评论 |
| 知乎 | zhihu | 关键词搜索、回答详情、评论 |

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

配置完成后，在 AI 编辑器中直接使用自然语言：

```
搜索小红书上关于"Python编程"的热门帖子
爬取B站视频BV1xx411c7mD的详情和评论
获取抖音用户xxx发布的视频列表
```

### MCP 工具说明

| 工具名 | 功能 |
|--------|------|
| `crawl_media` | 爬取平台内容 |
| `get_platforms` | 获取支持的的平台列表 |
| `get_crawler_types` | 获取支持的爬取类型 |

### crawl_media 参数

- `platform`: 平台代码（xhs/dy/ks/bili/wb/tieba/zhihu）
- `crawler_type`: 爬取类型（search/detail/creator）
- `keywords`: 关键词/ID/用户ID
- `max_count`: 返回数量（1-100，默认5）
- `is_get_comments`: 是否获取评论（默认false）
- `is_get_sub_comments`: 是否获取子评论（默认false）
- `max_comments_count`: 评论数量（0-50，默认5）

## 📁 项目结构

```
.
├── mcp_server.py        # MCP 服务入口
├── mcp_adapter.py       # 爬虫适配器
├── media_platform/      # 各平台爬虫实现
├── config/             # 配置文件
├── store/              # 数据存储
└── pyproject.toml      # 项目依赖
```

## ⚠️ 免责声明

本项目仅供学习研究使用，禁止用于商业用途和非法活动。使用本项目即表示你同意承担所有相关责任。

原始项目：https://github.com/NanmiCoder/MediaCrawler

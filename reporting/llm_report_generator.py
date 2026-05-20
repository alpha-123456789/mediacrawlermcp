"""
LLM 报告生成器
使用配置的 LLM API (支持 Anthropic/兼容 OpenAI 格式的任何 API) 生成高质量报告
"""

import os
import asyncio
import json
from typing import Dict, Tuple, Optional, Any
from pathlib import Path
from datetime import datetime

# 共享常量，避免各处重复定义
PLATFORM_NAMES = {
    'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
    'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎', 'toutiao': '今日头条'
}

REPORT_TYPE_NAMES = {
    'sentiment': '舆情分析',
    'trend': '热门趋势',
    'volume': '声量分析',
    'keyword': '关键词分析',
    'hot_topics': '热门话题',
    'viral_spread': '传播分析',
    'influencer': '影响力账号',
    'audience': '用户画像',
    'comparison': '竞品对比',
    'risk': '舆情风险'
}


def _extract_sentiment_values(sentiment_dist: list) -> Dict[str, float]:
    """从情感分布列表中提取各情感的百分比"""
    result = {'正面': 0, '负面': 0, '中性': 0}
    for item in sentiment_dist:
        if isinstance(item, dict):
            name = item.get("name", "")
            if name in result:
                result[name] = item.get("value", 0)
    return result

def get_llm_client():
    """根据环境变量获取对应的 LLM 客户端

    检测 Anthropic 原生 API 端点（/apps/anthropic 等）vs OpenAI 兼容端点（/v1 等），
    自动选择对应的 SDK：
    - Anthropic 端点 → Anthropic SDK (messages.create)
    - OpenAI 兼容端点 → OpenAI SDK (chat.completions.create)

    阿里云 DashScope 的 /apps/anthropic 端点只支持 Anthropic messages API 格式，
    不支持 OpenAI chat.completions 格式，所以必须用 Anthropic SDK 调用。
    """
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")

    # 检测 base_url 是否是 Anthropic messages API 端点
    # 特征：URL 包含 /apps/anthropic 或以 /anthropic 结尾、或者就是官方 api.anthropic.com
    def _is_anthropic_messages_endpoint(url):
        if not url:
            return False
        url_lower = url.lower().rstrip("/")
        # Anthropic 官方端点
        if url_lower in ("https://api.anthropic.com", "https://api.anthropic.com/"):
            return True
        # 阿里云 DashScope 的 Anthropic 代理端点
        if "/apps/anthropic" in url_lower:
            return True
        # 其他 Anthropic 代理（URL 路径中包含 anthropic 但不含 /v1）
        if "/anthropic" in url_lower and "/v1" not in url_lower:
            return True
        return False

    # Anthropic 配置
    if anthropic_api_key and anthropic_base_url:
        if _is_anthropic_messages_endpoint(anthropic_base_url):
            # Anthropic messages API → 使用 Anthropic SDK
            try:
                from anthropic import AsyncAnthropic
                client = AsyncAnthropic(
                    api_key=anthropic_api_key,
                    base_url=anthropic_base_url
                )
                return "anthropic", client
            except ImportError:
                raise ImportError("Anthropic 端点需要 Anthropic SDK，请安装: uv add anthropic")

        # OpenAI 兼容端点 → 使用 OpenAI SDK
        base_url = _normalize_openai_base_url(anthropic_base_url)
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=anthropic_api_key, base_url=base_url)
            return "openai", client
        except ImportError:
            raise ImportError("请安装 openai SDK: uv add openai")

    # OpenAI 配置
    if openai_api_key and openai_base_url:
        base_url = _normalize_openai_base_url(openai_base_url)
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_api_key, base_url=base_url)
            return "openai", client
        except ImportError:
            raise ImportError("请安装 openai SDK: uv add openai")

    # 只有 API Key，没有 base_url → Anthropic 原生 SDK（默认端点）
    if anthropic_api_key:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=anthropic_api_key)
            return "anthropic", client
        except ImportError:
            pass

    return None, None


def _normalize_openai_base_url(base_url: str) -> str:
    """规范化 OpenAI 兼容格式的 base_url

    OpenAI SDK 的 chat.completions.create 会自动在 base_url 后拼接
    /chat/completions，所以 base_url 需要指向 API 根路径。

    不同服务的路径结构不同：
    - https://api.openai.com/v1 → 标准 OpenAI，SDK 拼接后为 /v1/chat/completions
    - https://dashscope.aliyuncs.com/compatible-mode/v1 → 已包含 /v1，SDK 拼接后为 .../compatible-mode/v1/chat/completions
    - https://dashscope.aliyuncs.com/apps/anthropic → 多级路径，SDK 拼接后为 .../apps/anthropic/chat/completions
    - https://api.deepseek.com → 需追加 /v1，SDK 拼接后为 /v1/chat/completions

    策略：
    1. URL 已包含 /v1 → 不追加
    2. URL 有多级路径（2段及以上）→ 视为完整端点，不追加 /v1
    3. URL 仅有域名或单级路径 → 追加 /v1
    """
    url = base_url.rstrip("/")

    # 已经包含 /v1，不需要追加
    if "/v1" in url:
        return url + "/"

    # 解析 URL 路径部分
    # 例如 "https://dashscope.aliyuncs.com/apps/anthropic" → path = "/apps/anthropic"
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path_segments = [s for s in parsed.path.split("/") if s]

    if len(path_segments) >= 2:
        # 多级路径（如 /apps/anthropic、/compatible-mode/v1）→ 用户已指定完整端点
        return url + "/"
    else:
        # 简单路径或无路径 → 追加 /v1
        return url + "/v1/"


def get_model_name():
    """获取模型名称，优先使用配置中的默认模型"""
    return (
        os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL") or
        os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL") or
        os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL") or
        os.getenv("LLM_MODEL") or
        "claude-sonnet-4-6"  # 默认兜底
    )


async def call_llm(prompt: str, max_retries: int = 3) -> str:
    """
    调用 LLM API 生成内容

    Args:
        prompt: 提示词
        max_retries: 最大重试次数

    Returns:
        生成的 HTML 内容
    """
    client_type, client = get_llm_client()

    if not client:
        raise ValueError("未配置 LLM API。请设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 环境变量")

    # 系统提示词，确保生成高质量的 HTML 报告
    system_prompt = """你是一个专业的前端开发和数据分析师。请根据提供的数据生成一个精美、专业的 HTML 舆情分析报告。

【强制要求】
1. 使用现代的 HTML5 + CSS3 + JavaScript
2. 使用 ECharts 绘制图表（饼图、词云等）
3. 响应式布局，美观大方
4. 所有数据必须使用用户提供的真实数据，严禁编造
5. 通过 CDN 引入 ECharts: `<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>`
6. 词云图需要额外引入 wordCloud 扩展: `<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>`
7. 所有 CSS 样式直接写在 `<style>` 标签中
8. 中文显示，专业视觉风格

【JavaScript 数据转义 - 必须严格遵守】
- 所有包含引号的文本（如标题、评论、作者名）必须进行正确的字符串转义
- **严禁在 JavaScript 字符串中使用未转号的双引号**，例如 `"标题：""微信派""发布报告"` 是错误的
- 使用反斜杠转义双引号：`"标题：\"微信派\"发布报告"` 或使用单引号包裹：`'标题："微信派"发布报告'`
- **特别注意 Emoji 和特殊 Unicode 字符**：不要使用 UTF-16 surrogate pair 表示（如 😁），直接保留原始字符（如 😁）
- 推荐做法：将 JavaScript 数据用 `JSON.stringify()` 风格处理，确保所有引号都正确转义
- **如果 JavaScript 语法错误，所有图表将无法渲染，这是最严重的错误**

【以下模块必须全部包含，不能合并、不能省略】
模块1. 核心数据概览（统计卡片展示：内容数、总点赞、总评论、总播放等）
模块2. 执行摘要（核心发现、关键指标、风险提示 - 醒目样式）
模块3. 热门内容 TOP 10 排行榜（**必须使用 ECharts 横向柱状图渲染**，不能用表格或列表）
    - 使用 ECharts bar chart with inverse Y axis，X轴为互动数据，Y轴为内容标题
    - 每个柱子上标注排名、标题、作者、点赞/评论数
    - 数据来自 prompt 中的 top_contents 数据

模块4. 情感分析可视化（**最重要**）
- 必须使用 ECharts 饼图，基于提供的 sentiment_distribution 数据
- 饼图中每个扇区必须有明确的数据标签，例如"正面 65%"
- 图表下方用文字总结情感趋势

模块5. 用户讨论热词云（**最重要**）
- 必须使用 ECharts 词云图，基于提供的热词数据
- 需要加载 echarts-wordcloud 扩展才能渲染词云图
- 每个词必须显示权重值，字体大小反映权重
- 不能仅用列表形式展示，必须是可视化的词云
- 词云图配置示例：
```javascript
var chart = echarts.init(document.getElementById('wordCloudChart'));
chart.setOption({
    series: [{
        type: 'wordCloud',
        shape: 'circle',
        left: 'center',
        top: 'center',
        width: '95%',
        height: '95%',
        sizeRange: [12, 60],
        rotationRange: [-45, 45],
        textStyle: {
            fontFamily: 'sans-serif',
            color: function() {
                return 'rgb(' + [
                    Math.round(Math.random() * 160),
                    Math.round(Math.random() * 160),
                    Math.round(Math.random() * 160)
                ].join(',') + ')';
            }
        },
        data: hotWordsData  // 使用提供的热词数据
    }]
});
```

模块6. 评论深度分析（用户关注焦点、典型正面/负面评价、高频诉求）
模块7. 舆情洞察与建议（4-6条，每条必须有：发现、依据、建议）
模块8. 处理建议与行动方案（紧急处理、产品优化、营销方向、内容策略）
模块9. 代表性用户评论展示（8-10条，含用户名、内容、点赞数、情感标签）

【分析重点 - 四维综合分析】
必须同时分析以下四个维度，交叉验证：
1. **用户评论内容** - 真实反馈、观点、情感表达
2. **评论热度** - 评论点赞数（反映观点受欢迎程度）
3. **帖子内容** - 标题/正文主题（评论的上下文）
4. **帖子互动数据** - 点赞/分享/收藏/播放热度

洞察规则：
- 高赞评论 + 高热度帖子 = 大众共识/爆款话题
- 高赞评论 + 低热度帖子 = 小众痛点/真实需求
- 评论高频词汇 → 用户关注焦点
- 评论情感 vs 帖子热度 → 舆论走向判断

每一条分析结论，必须同时引用**评论内容**和**互动数据**作为双重证据。

【数据可视化关键要求】
- 情感分析饼图必须使用用户提供的 sentiment_distribution 数据渲染
  * 数据格式示例: [{"value": 60.5, "name": "正面"}, ...]
  * 必须用这些具体数值初始化 ECharts 的 option.series.data
- 热词云必须使用用户提供的热词数据渲染
  * 数据格式示例: [{"name": "人工智能", "value": 185}, ...]
  * name=词, value=权重，用于 ECharts wordCloud series
- **严禁在图表位置显示"暂无数据"或留空**，必须使用真实数据渲染
- **所有排行榜/排行图表必须使用 ECharts 图表渲染（柱状图/折线图）**，不能仅用 HTML 表格或列表展示
- **每个 ECharts 图表需要对应的 div 容器**，例如 `<div id="topContentsChart" style="width:100%;height:400px;"></div>`
  - **严禁只使用 CSS 类设置 min-height，必须在 div 上直接写 style="height:XXXpx"**
  - sentimentChart: height:400px, wordCloudChart: height:450px, topContentsChart: height:500px

【评论引用要求】
每条分析和建议都必须：**引用具体用户评论（@用户名 + 评论内容摘要）** 作为支撑，不能泛泛而谈。例如：
"用户 @小明 在评论中指出'产品质量一般，性价比不高'，反映出用户对价格敏感..."

【ECharts 图表初始化代码示例 - 必须在 HTML 底部添加】
```html
<script>
// 情感分析饼图 - 使用真实数据
document.addEventListener('DOMContentLoaded', function() {
    var sentimentChart = echarts.init(document.getElementById('sentimentChart'));
    var sentimentData = {{sentiment_distribution}}; // 使用提供的数据
    sentimentChart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
        legend: { bottom: '5%', left: 'center' },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '45%'],
            data: sentimentData,  // 必须使用真实数据
            label: { show: true, formatter: '{b}\n{c}%' }
        }]
    });
    window.addEventListener('resize', function() { sentimentChart.resize(); });

    // 词云图 - 使用真实数据
    var wordCloudChart = echarts.init(document.getElementById('wordCloudChart'));
    var hotWordsData = {{hot_words}}; // 使用提供的热词数据
    wordCloudChart.setOption({
        series: [{
            type: 'wordCloud',
            shape: 'circle',
            left: 'center',
            top: 'center',
            width: '90%',
            height: '90%',
            sizeRange: [12, 50],
            rotationRange: [-45, 45],
            rotationStep: 15,
            gridSize: 10,
            drawOutOfBound: false,
            layoutAnimation: true,
            textStyle: {
                fontFamily: 'sans-serif',
                fontWeight: 'bold',
                color: function() {
                    return 'hsl(' + Math.random() * 360 + ', 70%, 50%)';
                }
            },
            emphasis: {
                focus: 'self',
                textStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(0,0,0,0.15)'
                }
            },
            data: hotWordsData  // 必须使用真实数据
        }]
    });
    window.addEventListener('resize', function() { wordCloudChart.resize(); });

    // 热门内容 TOP 10 - 使用 ECharts 横向柱状图（**必须生成此代码**）
    var topContentsChart = echarts.init(document.getElementById('topContentsChart'));
    // 从 prompt 中的 top_contents JSON 提取数据
    var topContentsData = [/* 填入 prompt 中提供的 top_contents 数组 */];
    topContentsData.sort(function(a, b) { return (b.score || 0) - (a.score || 0); });
    topContentsData = topContentsData.slice(0, 10);
    var titles = topContentsData.map(function(item) { return (item.title || '').substring(0, 20); });
    var scores = topContentsData.map(function(item) { return item.score || 0; });
    topContentsChart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
                var idx = params[0].dataIndex;
                var item = topContentsData[idx];
                return '<b>' + (params[0].name) + '</b><br/>' +
                    '作者: ' + (item.author || '未知') + '<br/>' +
                    '点赞: ' + (item.likes || 0) + '<br/>' +
                    '评论: ' + (item.comments || 0) + '<br/>' +
                    '播放: ' + (item.views || 0);
            }
        },
        xAxis: { type: 'value', name: '综合得分' },
        yAxis: { type: 'category', data: titles, axisLabel: { interval: 0 } },
        series: [{
            type: 'bar',
            data: scores,
            label: { show: true, position: 'right' },
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: '#667eea' },
                    { offset: 1, color: '#764ba2' }
                ])
            }
        }]
    });
    window.addEventListener('resize', function() { topContentsChart.resize(); });

    // ========== 话题热度排行 (hot_topics 报告类型专用) ==========
    // 如果报告类型是 hot_topics，初始化 topicHeatChart
    var topicHeatChart = echarts.init(document.getElementById('topicHeatChart'));
    var topicData = [/* 从 hot_words 提取 TOP10 */];
    topicHeatChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'value', name: '热度值' },
        yAxis: { type: 'category', data: topicData.map(item => item.name), axisLabel: { interval: 0 } },
        series: [{ type: 'bar', data: topicData.map(item => item.value), label: { show: true, position: 'right' } }]
    });
    window.addEventListener('resize', function() { topicHeatChart.resize(); });

    // ========== 影响力账号排行 (influencer 报告类型专用) ==========
    var influencerChart = echarts.init(document.getElementById('influencerChart'));
    var influencerData = [/* 按作者聚合的互动数据 */];
    influencerChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'value', name: '总互动量' },
        yAxis: { type: 'category', data: influencerData.map(item => item.author), axisLabel: { interval: 0 } },
        series: [{ type: 'bar', data: influencerData.map(item => item.total_score), label: { show: true, position: 'right' } }]
    });
    window.addEventListener('resize', function() { influencerChart.resize(); });

    // ========== 趋势分析 (trend 报告类型专用) ==========
    var trendChart = echarts.init(document.getElementById('trendChart'));
    trendChart.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: [/* 时间序列 */] },
        yAxis: { type: 'value', name: '热度' },
        series: [{ type: 'line', smooth: true, areaStyle: {} }]
    });
    window.addEventListener('resize', function() { trendChart.resize(); });

    // ========== 声量分析 (volume 报告类型专用) ==========
    var volumeChart = echarts.init(document.getElementById('volumeChart'));
    volumeChart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: ['内容数', '点赞', '评论', '播放', '分享'] },
        yAxis: { type: 'value' },
        series: [{ type: 'bar', data: [/* 声量数据 */] }]
    });
    window.addEventListener('resize', function() { volumeChart.resize(); });

    // ========== 关键词关系图 (keyword 报告类型专用) ==========
    var keywordChart = echarts.init(document.getElementById('keywordChart'));
    keywordChart.setOption({
        tooltip: {},
        series: [{ type: 'graph', layout: 'force', data: [/* 关键词节点 */], links: [/* 关联关系 */] }]
    });
    window.addEventListener('resize', function() { keywordChart.resize(); });

    // ========== 传播路径桑基图 (viral_spread 报告类型专用) ==========
    var viralChart = echarts.init(document.getElementById('viralChart'));
    viralChart.setOption({
        tooltip: { trigger: 'item' },
        series: [{ type: 'sankey', data: [/* 节点 */], links: [/* 链路 */], label: { position: 'right' } }]
    });
    window.addEventListener('resize', function() { viralChart.resize(); });

    // ========== 用户画像雷达图 (audience 报告类型专用) ==========
    var audienceChart = echarts.init(document.getElementById('audienceChart'));
    audienceChart.setOption({
        tooltip: {},
        radar: { indicator: [{name:'互动活跃度',max:100}, {name:'情感正向度',max:100}, {name:'参与深度',max:100}] },
        series: [{ type: 'radar', data: [/* 用户画像数据 */] }]
    });
    window.addEventListener('resize', function() { audienceChart.resize(); });

    // ========== 竞品对比雷达图 (comparison 报告类型专用) ==========
    var comparisonChart = echarts.init(document.getElementById('comparisonChart'));
    comparisonChart.setOption({
        tooltip: {},
        radar: { indicator: [{name:'声量',max:100}, {name:'互动率',max:100}, {name:'正面评价率',max:100}, {name:'传播力',max:100}, {name:'关注度',max:100}] },
        series: [{ type: 'radar', data: [{name:'被分析对象',value:[]}, {name:'竞品',value:[]}] }]
    });
    window.addEventListener('resize', function() { comparisonChart.resize(); });

    // ========== 舆情风险仪表盘 (risk 报告类型专用) ==========
    var riskChart = echarts.init(document.getElementById('riskChart'));
    riskChart.setOption({
        series: [{ type: 'gauge', min:0, max:100, data: [{value: /* 风险值 */, name: '风险等级'}] }]
    });
    window.addEventListener('resize', function() { riskChart.resize(); });
});
</script>
```

【关键检查点】
1. 所有图表必须基于提供的真实数据初始化，严禁显示"暂无数据"或空图表
2. HTML 必须包含完整的 </body></html> 结束标签
3. 图表初始化代码必须放在 </body> 之前
4. 词云图必须等待 echarts-wordcloud.min.js 加载完成后再初始化
5. 如果词云图为空，检查 hot_words 数据格式是否为 [{"name": "词", "value": 100}, ...]
6. **热门内容 TOP 10 必须使用 ECharts 横向柱状图**，使用 top_contents 数据，包含 div#topContentsChart
7. **每个 ECharts 图表必须对应一个唯一的 div 容器**，根据报告类型可能需要：
   - sentimentChart（情感分析饼图）- 所有报告类型
   - wordCloudChart（词云图）- 所有报告类型
   - topContentsChart（热门内容排行）- 所有报告类型
   - topicHeatChart（话题热度）- hot_topics 报告类型
   - influencerChart（影响力账号）- influencer 报告类型
   - trendChart（趋势分析）- trend 报告类型
   - volumeChart（声量分析）- volume 报告类型
   - keywordChart（关键词关联）- keyword 报告类型
   - viralChart（传播路径）- viral_spread 报告类型
   - audienceChart（用户画像）- audience 报告类型
   - comparisonChart（竞品对比）- comparison 报告类型
   - riskChart（舆情风险）- risk 报告类型
8. **所有排行榜/图表类模块严禁用纯表格/列表代替 ECharts 图表**

【最终输出要求 - 必须严格遵守】
- **只输出纯 HTML 代码，从<!DOCTYPE html>开始，到</html>结束**
- **严禁在</html>之后添加任何解释、说明、注释或其他文字**
- **严禁使用 ```html 和 ``` 代码块标记包裹 HTML**
- **输出必须是纯净的、可直接打开的 HTML 文件，不能有任何额外内容**

请只输出 HTML 代码，不要有任何其他文字。"""

    for attempt in range(max_retries):
        try:
            if client_type == "anthropic":
                # Anthropic messages API
                response = await client.messages.create(
                    model=get_model_name(),
                    max_tokens=16384,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                # 处理 thinking block：某些代理（如 DashScope）可能返回 thinking + text 两个 block
                html_content = ""
                for block in response.content:
                    if block.type == "text":
                        html_content = block.text
                        break
                if not html_content:
                    # 没找到 text block，取最后一个 block 的文本
                    html_content = response.content[-1].text if response.content else ""
            else:
                # OpenAI 兼容格式
                response = await client.chat.completions.create(
                    model=get_model_name(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=16384,
                    temperature=0.7
                )

                # 容错处理：某些 API 可能返回非标准格式
                if isinstance(response, str):
                    html_content = response
                elif hasattr(response, 'choices') and response.choices:
                    html_content = response.choices[0].message.content
                elif isinstance(response, dict) and 'choices' in response:
                    html_content = response['choices'][0]['message']['content']
                else:
                    # 最后兜底：尝试把 response 当作字符串
                    html_content = str(response)

            # 清理输出，提取 HTML 部分
            html_content = html_content.strip()

            # 如果输出被 ```html 和 ``` 包裹，去除它们
            if html_content.startswith("```html"):
                html_content = html_content[7:]
            if html_content.startswith("```"):
                html_content = html_content[3:]
            if html_content.endswith("```"):
                html_content = html_content[:-3]

            html_content = html_content.strip()

            # 确保是有效的 HTML
            if not html_content.startswith("<"):
                raise ValueError("生成的内容不是有效的 HTML")

            # 检查 HTML 完整性
            if "</html>" not in html_content.lower():
                raise ValueError("HTML 内容不完整，缺少 </html> 结束标签")

            return html_content

        except Exception as e:
            if attempt == max_retries - 1:
                raise Exception(f"LLM API 调用失败: {str(e)}")
            await asyncio.sleep(2 ** attempt)  # 指数退避

    raise Exception("LLM API 调用失败，已达到最大重试次数")


async def generate_report_with_llm(
    platform: str,
    keywords: str,
    ai_data: Dict,
    output_path: str,
    report_type: str = "sentiment"
) -> Tuple[str, str]:
    """
    使用 LLM 生成报告

    Args:
        platform: 平台标识
        keywords: 关键词
        ai_data: AI 报告数据（包含 prompt、数据画像等）
        output_path: 输出目录
        report_type: 报告类型

    Returns:
        (report_path, summary)
    """
    prompt = ai_data["prompt"]
    profile = ai_data.get("profile", {})
    detailed_data = ai_data.get("detailed_data", {})
    platform_name = platform

    # 确定平台名称和报告类型名称
    platform_name = PLATFORM_NAMES.get(platform, platform)
    report_type_name = REPORT_TYPE_NAMES.get(report_type, '舆情分析')

    # 调用 LLM 生成报告
    html_content = await call_llm(prompt)

    # 准备保存路径
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（包含报告类型）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = "".join(c if c.isalnum() or c in '-_ ' else '_' for c in keywords)
    safe_kw = safe_kw.strip()

    filename = f"{platform_name}_{safe_kw}_{report_type_name}_{timestamp}.html"
    report_path = output_dir / filename

    # 保存 HTML 文件
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 生成摘要
    summary = generate_summary(profile, detailed_data, platform_name, keywords, report_type, report_type_name)

    return str(report_path), summary


def generate_summary(
    profile: Dict,
    detailed_data: Dict,
    platform_name: str,
    keywords: str,
    report_type: str = "sentiment",
    report_type_name: str = "舆情分析"
) -> str:
    """生成报告摘要"""
    total_items = profile.get("总数据量", 0)
    stats = profile.get("数值统计", {}).get("总量", {})
    sentiment_dist = detailed_data.get("sentiment_distribution", [])
    content_type = profile.get("内容特征", {}).get("内容类型", "未知")

    summary_parts = [
        f"📊 {platform_name}「{keywords}」{report_type_name}报告\n",
        f"📈 数据概览：采集 {total_items} 条{content_type}",
        f"   总点赞: {stats.get('likes', 0)} | 总评论: {stats.get('comments', 0)} | 总播放: {stats.get('views', 0)}",
    ]

    # 根据报告类型生成不同的摘要内容
    if report_type == 'risk':
        # 风险报告摘要
        positive = 0
        negative = 0
        for item in sentiment_dist:
            if isinstance(item, dict):
                name = item.get("name", "")
                value = item.get("value", 0)
                if name == "正面":
                    positive = value
                elif name == "负面":
                    negative = value

        summary_parts.append(
            f"⚠️ 风险评估：负面评价 {negative:.1f}% | 正面评价 {positive:.1f}%"
        )

        if negative > 40:
            summary_parts.append("🚨 风险等级：高危，需立即采取应对措施")
        elif negative > 25:
            summary_parts.append("⚠️ 风险等级：中危，建议密切关注")
        elif negative > 15:
            summary_parts.append("⚡ 风险等级：低危，需适度关注")
        else:
            summary_parts.append("✅ 风险等级：正常，整体舆情健康")

    elif report_type in ['trend', 'volume']:
        # 趋势/声量报告摘要
        summary_parts.append(
            f"📊 声量规模：内容 {total_items} 条 | 总互动 {stats.get('likes', 0) + stats.get('comments', 0)}"
        )
        if stats.get('views', 0) > 0:
            summary_parts.append(f"👁️ 总曝光：{stats.get('views', 0)} 次")

    elif report_type in ['keyword', 'hot_topics']:
        # 关键词/话题报告摘要
        hot_words = detailed_data.get("hot_words", [])
        if hot_words:
            top_words = [w.get("name", "") for w in hot_words[:5] if isinstance(w, dict)]
            if top_words:
                summary_parts.append(f"🔑 核心关键词：{', '.join(top_words)}")

    elif report_type == 'influencer':
        # 影响力账号报告摘要
        top_contents = detailed_data.get("top_contents", [])
        if top_contents:
            top_author = top_contents[0].get('author', '未知') if top_contents else '未知'
            summary_parts.append(f"⭐ 头部账号：{top_author}")

    else:
        # 默认舆情分析摘要
        # 情感分析摘要 - sentiment_distribution 是列表格式
        positive = 0
        negative = 0
        neutral = 0
        for item in sentiment_dist:
            if isinstance(item, dict):
                name = item.get("name", "")
                value = item.get("value", 0)
                if name == "正面":
                    positive = value
                elif name == "负面":
                    negative = value
                elif name == "中性":
                    neutral = value

        summary_parts.append(
            f"💭 情感分布：正面 {positive:.1f}% | 负面 {negative:.1f}% | 中性 {neutral:.1f}%"
        )

        # 根据情感给出判断
        if positive > 60:
            summary_parts.append("✅ 整体口碑良好，正面评价占主导")
        elif negative > 30:
            summary_parts.append("⚠️ 负面评价较多，需要关注舆情风险")
        else:
            summary_parts.append("📊 舆情分布均匀，需要具体场景分析")

    # 热词摘要 - 所有报告类型都显示
    if report_type not in ['keyword', 'hot_topics']:
        hot_words = detailed_data.get("hot_words", [])
        if hot_words:
            top_words = [w.get("name", "") for w in hot_words[:5] if isinstance(w, dict)]
            if top_words:
                summary_parts.append(f"🔥 热门讨论：{', '.join(top_words)}")

    return "\n".join(summary_parts)


# =========================
# 多平台报告生成
# =========================

async def generate_multi_platform_report_with_llm(
    platform_data,
    keywords,
    ai_data,
    output_path,
    report_type="sentiment"
):
    """
    使用 LLM 生成多平台合并报告
    """
    prompt = ai_data["prompt"]
    profile = ai_data.get("profile", {})
    detailed_data = ai_data.get("detailed_data", {})

    # 平台名称和报告类型名称
    platforms_str = ', '.join([PLATFORM_NAMES.get(p, p) for p in platform_data.keys()])
    report_type_name = REPORT_TYPE_NAMES.get(report_type, '舆情分析')

    # 调用 LLM 生成报告
    html_content = await call_llm(prompt)

    # 准备保存路径
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = "".join(c if c.isalnum() or c in '-_ ' else '_' for c in keywords)
    safe_kw = safe_kw.strip()

    filename = f"多平台_{safe_kw}_{report_type_name}_{timestamp}.html"
    report_path = output_dir / filename

    # 保存 HTML 文件
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 生成多平台摘要
    summary = generate_multi_platform_summary(profile, detailed_data, platforms_str, keywords, report_type, report_type_name)

    return str(report_path), summary


def generate_multi_platform_summary(profile, detailed_data, platforms_str, keywords, report_type, report_type_name):
    """生成多平台报告摘要"""
    total_items = profile.get("总数据量", 0)
    stats = profile.get("数值统计", {}).get("总量", {})
    platform_stats = profile.get("平台分布", {})
    sentiment_dist = detailed_data.get("sentiment_distribution", [])


    summary_parts = [
        f"📊 多平台「{keywords}」{report_type_name}报告",
        f"🌐 覆盖平台：{platforms_str}",
        f"📈 总数据量：{total_items} 条内容",
    ]

    # 各平台分布
    if platform_stats:
        summary_parts.append("📊 平台分布：")
        for platform, count in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
            platform_name = PLATFORM_NAMES.get(platform, platform)
            summary_parts.append(f"   • {platform_name}: {count}条")

    # 互动数据
    if stats.get('likes', 0) > 0:
        summary_parts.append(f"❤️ 总点赞: {stats.get('likes', 0)}")
    if stats.get('comments', 0) > 0:
        summary_parts.append(f"💬 总评论: {stats.get('comments', 0)}")
    if stats.get('views', 0) > 0:
        summary_parts.append(f"👁️ 总播放: {stats.get('views', 0)}")

    # 情感分析
    if sentiment_dist:
        positive = 0
        negative = 0
        neutral = 0
        for item in sentiment_dist:
            if isinstance(item, dict):
                name = item.get("name", "")
                value = item.get("value", 0)
                if name == "正面":
                    positive = value
                elif name == "负面":
                    negative = value
                elif name == "中性":
                    neutral = value

        summary_parts.append(
            f"💭 情感分布：正面 {positive:.1f}% | 负面 {negative:.1f}% | 中性 {neutral:.1f}%"
        )

    # 热词
    hot_words = detailed_data.get("hot_words", [])
    if hot_words:
        top_words = [w.get("name", "") for w in hot_words[:5] if isinstance(w, dict)]
        if top_words:
            summary_parts.append(f"🔥 热门讨论：{', '.join(top_words)}")

    return "\n".join(summary_parts)
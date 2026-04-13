# -*- coding: utf-8 -*-
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

def get_llm_client():
    """根据环境变量获取对应的 LLM 客户端"""
    # 读取配置（来自 Claude Code settings.json 的 env 或 .env 文件）
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL")

    # 如果没有 Anthropic 配置，尝试 OpenAI 兼容格式
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")

    api_key = anthropic_api_key or openai_api_key
    base_url = anthropic_base_url or openai_base_url

    if api_key and base_url:
        # 使用 OpenAI 兼容格式（大部分自部署模型都支持）
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            return "openai", client
        except ImportError:
            raise ImportError("请安装 openai SDK: uv add openai")

    return None, None


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

【以下模块必须全部包含，不能合并、不能省略】
模块1. 核心数据概览（统计卡片展示：内容数、总点赞、总评论、总播放等）
模块2. 执行摘要（核心发现、关键指标、风险提示 - 醒目样式）
模块3. 热门内容 TOP 10 排行榜（带排名、标题、作者、互动数据）

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
  * 数据格式示例: [{"name": "宝宝巴士", "value": 185}, ...]
  * name=词, value=权重，用于 ECharts wordCloud series
- **严禁在图表位置显示"暂无数据"或留空**，必须使用真实数据渲染

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
            sizeRange: [14, 60],
            rotationRange: [-45, 45],
            textStyle: {
                color: function() {
                    return 'hsl(' + Math.random() * 360 + ', 70%, 50%)';
                }
            },
            data: hotWordsData  // 必须使用真实数据
        }]
    });
    window.addEventListener('resize', function() { wordCloudChart.resize(); });
});
</script>
```

【关键检查点】
1. 所有图表必须基于提供的真实数据初始化，严禁显示"暂无数据"或空图表
2. HTML 必须包含完整的 </body></html> 结束标签
3. 图表初始化代码必须放在 </body> 之前
4. 词云图必须等待 echarts-wordcloud.min.js 加载完成后再初始化
5. 如果词云图为空，检查 hot_words 数据格式是否为 [{"name": "词", "value": 100}, ...]

请输出完整的、可运行的、未被截断的 HTML 代码。"""

    for attempt in range(max_retries):
        try:
            if client_type == "anthropic":
                # Anthropic 原生 API
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=16384,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                html_content = response.content[0].text
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
                html_content = response.choices[0].message.content

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

    # 确定平台名称
    platform_names = {
        'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
        'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
    }
    platform_name = platform_names.get(platform, platform)

    # 报告类型名称映射
    report_type_names = {
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
    report_type_name = report_type_names.get(report_type, '舆情分析')

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

    # 平台名称映射
    platform_names = {
        'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
        'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
    }
    platforms_str = ', '.join([platform_names.get(p, p) for p in platform_data.keys()])

    # 报告类型名称映射
    report_type_names = {
        'sentiment': '舆情分析', 'trend': '热门趋势', 'volume': '声量分析',
        'keyword': '关键词分析', 'hot_topics': '热门话题', 'viral_spread': '传播分析',
        'influencer': '影响力账号', 'audience': '用户画像',
        'comparison': '竞品对比', 'risk': '舆情风险'
    }
    report_type_name = report_type_names.get(report_type, '舆情分析')

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

    # 平台名称映射
    platform_names = {
        'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
        'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
    }

    summary_parts = [
        f"📊 多平台「{keywords}」{report_type_name}报告",
        f"🌐 覆盖平台：{platforms_str}",
        f"📈 总数据量：{total_items} 条内容",
    ]

    # 各平台分布
    if platform_stats:
        summary_parts.append("📊 平台分布：")
        for platform, count in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
            platform_name = platform_names.get(platform, platform)
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

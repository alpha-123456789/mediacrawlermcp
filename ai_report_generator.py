# -*- coding: utf-8 -*-
"""
AI 驱动报告生成器 v4.0
将数据特征传递给 AI，由 AI 动态生成报告结构
"""

import os
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional


class DataProfiler:
    """数据特征分析器 - 为 AI 提供数据画像"""

    def __init__(self, data: List[Dict]):
        self.data = data

    def analyze(self) -> Dict:
        """生成完整的数据画像"""
        if not self.data:
            return {"error": "没有数据"}

        # 基础统计
        total_items = len(self.data)
        first_item = self.data[0]

        # 分析数据结构
        fields_found = self._detect_fields()

        # 数值统计
        numeric_stats = self._calculate_stats()

        # 内容分析
        content_analysis = self._analyze_content()

        # 互动模式
        engagement_pattern = self._analyze_engagement()

        return {
            "总数据量": total_items,
            "数据结构": fields_found,
            "数值统计": numeric_stats,
            "内容特征": content_analysis,
            "互动模式": engagement_pattern,
            "样例数据": self._get_samples()
        }

    def _detect_fields(self) -> Dict[str, bool]:
        """检测数据中包含哪些字段"""
        sample = self.data[0] if self.data else {}
        interact = sample.get('interact_info', {}) if isinstance(sample, dict) else {}

        return {
            "点赞": any(k in interact for k in ['like_count', 'digg_count', 'attitudes_count']),
            "评论数": any(k in interact for k in ['comment_count', 'comments_count']),
            "评论内容": any(item.get('comments') for item in self.data[:5]),
            "播放/阅读": any(k in interact for k in ['view_count', 'play_count', 'read_count']),
            "分享/转发": any(k in interact for k in ['share_count', 'reposts_count']),
            "收藏": any(k in interact for k in ['collect_count', 'favorite_count']),
            "投币": 'coin_count' in interact or 'coins' in interact,
            "标题": any(item.get('title') or item.get('desc') for item in self.data[:3]),
            "作者": any(item.get('nickname') or item.get('author') for item in self.data[:3]),
            "时间": any(item.get('create_time') or item.get('created_at') for item in self.data[:3])
        }

    def _calculate_stats(self) -> Dict:
        """计算数值统计"""
        stats = {"likes": 0, "comments": 0, "views": 0, "shares": 0}

        for item in self.data:
            interact = item.get('interact_info', {}) if isinstance(item, dict) else {}
            stats["likes"] += interact.get('like_count', 0) or interact.get('digg_count', 0) or 0
            stats["comments"] += interact.get('comment_count', 0) or interact.get('comments_count', 0) or 0
            stats["views"] += interact.get('view_count', 0) or interact.get('play_count', 0) or 0
            stats["shares"] += interact.get('share_count', 0) or interact.get('reposts_count', 0) or 0

        total = len(self.data)
        return {
            "总量": stats,
            "平均值": {k: round(v/total, 1) if total else 0 for k, v in stats.items()},
            "最大值": self._get_max_values(),
            "数据质量": "高" if total > 10 else "中等" if total > 5 else "低"
        }

    def _analyze_content(self) -> Dict:
        """分析内容特征"""
        # 检查评论内容长度分布
        comment_lengths = []
        has_purchase_intent = 0
        sentiment_keywords = {"positive": ["好", "喜欢", "棒", "赞"], "negative": ["差", "烂", "坑", "失望"]}

        for item in self.data:
            comments = item.get('comments', [])
            for c in comments[:5]:  # 采样前5条评论
                content = c.get('content', '') if isinstance(c, dict) else str(c)
                if content:
                    comment_lengths.append(len(content))
                    if any(kw in content for kw in ["买", "多少钱", "链接", "下单"]):
                        has_purchase_intent += 1

        return {
            "评论平均长度": round(sum(comment_lengths)/len(comment_lengths), 1) if comment_lengths else 0,
            "购买意向评论": has_purchase_intent,
            "内容类型": self._detect_content_type()
        }

    def _analyze_engagement(self) -> str:
        """分析互动模式"""
        interact = self.data[0].get('interact_info', {}) if self.data and isinstance(self.data[0], dict) else {}

        if 'view_count' in interact or 'play_count' in interact:
            return "视频观看型：重点是播放量、完播率、弹幕互动"
        elif 'attitudes_count' in interact or 'reposts_count' in interact:
            return "社交传播型：重点是转发、点赞、讨论热度"
        elif 'comment_count' in interact or interact.get('comments'):
            return "内容讨论型：重点是评论质量、用户反馈"
        else:
            return "基础展示型：重点是内容曝光、用户触达"

    def _detect_content_type(self) -> str:
        """检测内容类型"""
        sample_text = ""
        for item in self.data[:3]:
            sample_text += item.get('desc', '') or item.get('title', '') or ''

        if any(kw in sample_text for kw in ['教程', '攻略', '步骤', '方法']):
            return "教学/教程内容"
        elif any(kw in sample_text for kw in ['测评', '评测', '体验', '开箱']):
            return "测评/体验内容"
        elif any(kw in sample_text for kw in ['美食', '穿搭', '旅行', '日常']):
            return "生活分享内容"
        elif any(kw in sample_text for kw in ['观点', '分析', '解读', '看法']):
            return "观点/分析内容"
        return "综合内容"

    def _get_max_values(self) -> Dict:
        """获取各项最大值"""
        max_values = {"likes": 0, "comments": 0, "views": 0}

        for item in self.data:
            interact = item.get('interact_info', {}) if isinstance(item, dict) else {}
            max_values["likes"] = max(max_values["likes"], interact.get('like_count', 0) or interact.get('digg_count', 0) or 0)
            max_values["comments"] = max(max_values["comments"], interact.get('comment_count', 0) or 0)
            max_values["views"] = max(max_values["views"], interact.get('view_count', 0) or interact.get('play_count', 0) or 0)

        return max_values

    def _get_samples(self) -> List[Dict]:
        """获取样例数据摘要"""
        samples = []
        for item in self.data[:3]:
            if isinstance(item, dict):
                samples.append({
                    "title": (item.get('title') or item.get('desc', ''))[:50],
                    "author": item.get('nickname', item.get('author', '未知')),
                    "interact": {k: v for k, v in item.get('interact_info', {}).items() if v}
                })
        return samples


class AIReportPromptBuilder:
    """构建给 AI 的提示词"""

    def __init__(self, platform: str, keywords: str, profile: Dict):
        self.platform = platform
        self.keywords = keywords
        self.profile = profile

    def build_prompt(self) -> str:
        """构建完整的提示词"""
        platform_names = {
            'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
            'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
        }
        platform_name = platform_names.get(self.platform, self.platform)

        fields = self.profile.get("数据结构", {})
        stats = self.profile.get("数值统计", {})
        content = self.profile.get("内容特征", {})

        # 构建数据特征描述
        features_desc = []
        if fields.get("点赞"):
            avg_likes = stats.get("平均值", {}).get("likes", 0)
            features_desc.append(f"有点赞数据，平均{avg_likes:.0f}赞")
        if fields.get("评论内容"):
            features_desc.append("有评论内容，可做情感分析")
        if fields.get("播放/阅读"):
            avg_views = stats.get("平均值", {}).get("views", 0)
            features_desc.append(f"有播放数据，平均{avg_views:.0f}播放")
        if fields.get("收藏"):
            features_desc.append("有收藏数据")
        if fields.get("分享/转发"):
            features_desc.append("有转发数据")

        return f"""请根据以下数据特征，生成一个独特的数据可视化HTML报告。

## 数据概况
- 平台: {platform_name}
- 关键词: "{self.keywords}"
- 数据量: {self.profile.get("总数据量")} 条
- 互动模式: {self.profile.get("互动模式")}
- 内容类型: {content.get("内容类型")}
- 数据质量: {stats.get("数据质量")}

## 数据特征
{chr(10).join([f"- {f}" for f in features_desc]) if features_desc else "- 基础内容数据"}

## 设计要求
1. **根据数据特征设计独特的页面风格**：
   {"- 有播放量数据 -> 使用粉紫色渐变，突出趋势感" if fields.get("播放/阅读") else ""}
   {"- 有评论内容 -> 使用蓝紫色渐变，突出专业分析感" if fields.get("评论内容") else ""}
   {"- 主要是点赞数据 -> 使用暖色调，突出热度感" if fields.get("点赞") and not fields.get("播放/阅读") else ""}

2. **动态模块设计**：
   - 根据有的数据字段，设计对应的数据卡片
   {"- 有评论内容必须包含情感分析饼图" if fields.get("评论内容") else ""}
   {"- 有播放量数据可用面积图展示趋势" if fields.get("播放/阅读") else ""}
   {"- 有点赞和收藏对比可做玫瑰图" if fields.get("点赞") and fields.get("收藏") else ""}

3. **独特的洞察卡片**：
   - 根据数据量、互动量、内容类型生成3-4条针对性洞察
   - 不要套话，要基于真实数据特征的分析

4. **布局设计要求（重要）：**
   - **充足的留白**：每个区块 `.section` 使用 `padding: 30px; margin-bottom: 30px;`，避免内容拥挤
   - **卡片式设计**：使用 `border-radius: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.1);` 创造视觉层次
   - **数据卡片间距**：stats 卡片使用 `gap: 15px` 分开，不要挤在一起
   - **列表项间距**：每个视频/评论项使用 `padding: 12px 15px;` 和 `border-bottom: 1px solid #eee;` 分隔
   - **洞察卡片**：insight box 使用 `padding: 18px; margin-bottom: 15px;`，左边缘添加彩色边框
   - **词云设计**：使用 `flex-wrap: wrap; gap: 10px; padding: 20px;` 让标签自然分布，不要堆叠

5. **内容排列原则：**
   - 数据概览用 grid 卡片展示，`grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))`
   - 排行榜每项都要有独立的视觉容器
   - 柱状图/进度条要有足够的 `height: 26px;` 和 `margin-bottom: 12px;`
   - 评论区每条都要有独立背景和边框，不要纯文字堆砌

请输出完整的、独立的 HTML 代码（包含 CSS 和 JavaScript），中文显示，设计美观专业，布局宽松舒适。"""


def generate_ai_report_data(
    platform: str,
    keywords: str,
    data: List[Dict]
) -> Dict:
    """
    生成 AI 报告所需的数据结构
    返回：{
        "prompt": 给 AI 的提示词,
        "profile": 数据画像,
        "raw_data_sample": 原始数据样例
    }
    """
    profiler = DataProfiler(data)
    profile = profiler.analyze()

    prompt_builder = AIReportPromptBuilder(platform, keywords, profile)
    prompt = prompt_builder.build_prompt()

    return {
        "prompt": prompt,
        "profile": profile,
        "data_summary": {
            "count": len(data),
            "platform": platform,
            "keywords": keywords
        }
    }


def save_report(html_content: str, platform: str, keywords: str, output_path: str = "reports") -> str:
    """保存报告文件"""
    os.makedirs(output_path, exist_ok=True)

    platform_names = {
        'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
        'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
    }
    platform_name = platform_names.get(platform, platform)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = re.sub(r'[\\/*?:"<>|]', "_", f"{platform_name}_{keywords}_AI智能报告_{timestamp}.html")
    filepath = os.path.join(output_path, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return filepath


# 兼容旧接口
def generate_report(
    platform: str,
    keywords: str,
    data: List[Dict],
    output_path: str = "reports",
    report_type: str = "auto"
) -> Tuple[str, str, str]:
    """
    生成报告 - 返回数据和提示词，供 AI 使用
    """
    result = generate_ai_report_data(platform, keywords, data)

    summary = f"""
╔════════════════════════════════════════════════════════════════╗
║              🤖 AI 驱动报告数据源已生成                          ║
╠════════════════════════════════════════════════════════════════╣
║ 平台: {platform:<12} 关键词: {keywords:<25}      ║
║ 数据量: {result['data_summary']['count']:<5}                                     ║
╠════════════════════════════════════════════════════════════════╣
║ 📊 数据特征                                                      ║
"""
    for field, has in result['profile'].get("数据结构", {}).items():
        if has:
            summary += f"║    ✓ {field:<15}                                     ║\n"

    summary += f"""╠════════════════════════════════════════════════════════════════╣
║ 💡 请使用 generate_ai_report_data() 获取完整提示词             ║
║    或将 prompts 传递给 Claude/AI 生成报告                       ║
╚════════════════════════════════════════════════════════════════╝"""

    # 提示词作为 html_content 返回（实际使用时 AI 会生成真正的 HTML）
    return "", summary, result["prompt"]

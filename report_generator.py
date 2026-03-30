# -*- coding: utf-8 -*-
"""
舆情报告生成器
根据爬取的数据生成 HTML 报告
"""

import os
import re
import json
import jieba
import jieba.analyse
from datetime import datetime
from typing import Any, Dict, List, Tuple
from collections import Counter, defaultdict


class SentimentAnalyzer:
    """简单的情感分析器"""

    # 正面词典
    POSITIVE_WORDS = {
        '好', '棒', '优秀', '喜欢', '爱', '赞', '强', '完美', '推荐', '满意',
        '不错', '值得', '惊喜', '漂亮', '好看', '好用', '实用', '方便', '快速',
        '专业', '贴心', '周到', '划算', '便宜', '实惠', '超值', '高品质',
        '好用', '舒服', '愉快', '开心', '幸福', '感动', '感谢', '支持',
        '给力', '厉害', '牛', '香', '甜', '美', '可爱', '搞笑', '有趣',
        '精彩', '经典', '火爆', '热门', '流行', '时尚', '新颖', '创新',
        '清晰', '流畅', '稳定', '高效', '便捷', '智能', '贴心', '温暖',
        '靠谱', '放心', '安心', '省心', '省事儿', '好用', '耐用', '结实'
    }

    # 负面词典
    NEGATIVE_WORDS = {
        '差', '烂', '糟', '坏', '差劲', '失望', '后悔', '垃圾', '坑', '骗',
        '假', '贵', '慢', '卡', '顿', '麻烦', '复杂', '难用', '难吃', '难看',
        '丑', '臭', '脏', '乱', '吵', '挤', '远', '偏', '不方便', '不划算',
        '不值', '亏了', '上当', '受骗', '被坑', '差评', '投诉', '退货', '退款',
        '坏了', '破', '旧', '脏', '乱', '差', '弱', 'low', '土', '过时',
        '无聊', '没劲', '尴尬', '恶心', '讨厌', '烦', '累', '痛苦', '难过',
        '伤心', '气', '怒', '火', '骂', '批评', '质疑', '怀疑', '担心', '怕'
    }

    @classmethod
    def analyze(cls, text: str) -> Tuple[str, float]:
        """
        分析文本情感
        Returns: (sentiment: 'positive'|'negative'|'neutral', score: 0-1)
        """
        if not text:
            return 'neutral', 0.5

        text = str(text)
        pos_count = sum(1 for word in cls.POSITIVE_WORDS if word in text)
        neg_count = sum(1 for word in cls.NEGATIVE_WORDS if word in text)

        total = pos_count + neg_count
        if total == 0:
            return 'neutral', 0.5

        # 计算情感得分
        score = pos_count / (pos_count + neg_count * 1.2 + 0.1)

        if score > 0.6:
            return 'positive', min(score, 1.0)
        elif score < 0.4:
            return 'negative', max(1 - score, 0.0)
        else:
            return 'neutral', 0.5


class ReportGenerator:
    """舆情报告生成器"""

    PLATFORM_NAMES = {
        'xhs': '小红书',
        'dy': '抖音',
        'ks': '快手',
        'bili': 'B站',
        'wb': '微博',
        'tieba': '百度贴吧',
        'zhihu': '知乎'
    }

    def __init__(self, platform: str, keywords: str, data: List[Dict], output_path: str = "reports", report_path: str = None):
        self.platform = platform
        self.keywords = keywords
        self.data = data
        self.output_path = output_path
        self.report_path = report_path  # 完整的报告文件路径（显示用）
        # 预先将反斜杠转为正斜杠，用于 HTML 中的 file:// 链接
        self.report_path_slashed = report_path.replace('\\', '/') if report_path else None
        self.sentiment_stats = {'positive': 0, 'negative': 0, 'neutral': 0}
        self.total_comments = 0
        self.hot_words = []
        self.representative_comments = []

    def _analyze_sentiment(self) -> Dict:
        """分析情感分布"""
        sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}

        for item in self.data:
            # 分析主内容情感
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            sentiment, _ = SentimentAnalyzer.analyze(text)
            sentiments[sentiment] += 1

            # 分析评论情感
            comments = item.get('comments', [])
            for comment in comments:
                comment_text = comment.get('content', '')
                sentiment, _ = SentimentAnalyzer.analyze(comment_text)
                sentiments[sentiment] += 1
                self.total_comments += 1

        self.sentiment_stats = sentiments
        total = sum(sentiments.values())
        if total > 0:
            return {k: round(v / total * 100, 1) for k, v in sentiments.items()}
        return sentiments

    def _extract_hot_words(self) -> List[Tuple[str, int]]:
        """提取热词"""
        all_text = []

        for item in self.data:
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            all_text.append(text)

            for comment in item.get('comments', []):
                all_text.append(comment.get('content', ''))

        full_text = ' '.join(all_text)

        # 使用 jieba 提取关键词
        keywords = jieba.analyse.extract_tags(full_text, topK=30, withWeight=True)

        # 转换为计数格式
        hot_words = [(word, int(weight * 1000)) for word, weight in keywords]
        self.hot_words = hot_words[:20]
        return self.hot_words

    def _get_representative_comments(self) -> List[Dict]:
        """获取代表性评论"""
        comments = []

        for item in self.data:
            for comment in item.get('comments', []):
                content = comment.get('content', '')
                if len(content) > 10 and len(content) < 200:
                    sentiment, score = SentimentAnalyzer.analyze(content)
                    comments.append({
                        'content': content,
                        'sentiment': sentiment,
                        'score': score,
                        'like_count': comment.get('like_count', 0),
                        'nickname': comment.get('comment_nickname', '') or comment.get('user_nickname', '')
                    })

        # 按点赞数排序，取前15条
        comments.sort(key=lambda x: x['like_count'], reverse=True)
        self.representative_comments = comments[:15]
        return self.representative_comments

    def _get_interaction_stats(self) -> Dict:
        """获取互动数据统计"""
        stats = {
            'total_likes': 0,
            'total_comments': 0,
            'total_shares': 0,
            'avg_likes': 0,
            'avg_comments': 0
        }

        count = len(self.data)
        if count == 0:
            return stats

        for item in self.data:
            interact = item.get('interact_info', {})
            # 不同平台字段名不同
            stats['total_likes'] += interact.get('like_count', 0) or interact.get('digg_count', 0) or interact.get('attitudes_count', 0) or 0
            stats['total_comments'] += interact.get('comment_count', 0) or interact.get('comments_count', 0) or 0
            stats['total_shares'] += interact.get('share_count', 0) or interact.get('reposts_count', 0) or 0

        stats['avg_likes'] = round(stats['total_likes'] / count, 1)
        stats['avg_comments'] = round(stats['total_comments'] / count, 1)

        return stats

    def _generate_summary(self) -> str:
        """生成舆情摘要"""
        sentiment_pct = self._analyze_sentiment()
        dominant = max(sentiment_pct, key=sentiment_pct.get)

        if dominant == 'positive':
            sentiment_desc = "正面情绪为主"
        elif dominant == 'negative':
            sentiment_desc = "负面情绪较明显"
        else:
            sentiment_desc = "情绪分布相对中性"

        # 分析热词主题
        topics = [w[0] for w in self.hot_words[:5]] if self.hot_words else []
        topic_str = '、'.join(topics) if topics else '相关话题'

        return f"本次舆情监测显示，关于「{self.keywords}」的讨论整体呈{sentiment_desc}态势。用户主要关注{topic_str}等话题，共分析{len(self.data)}条内容，{self.total_comments}条评论。"

    def _generate_insights(self) -> List[str]:
        """生成分析洞察"""
        insights = []
        sentiment_pct = self._analyze_sentiment()

        # 情感分析洞察
        if sentiment_pct.get('positive', 0) > 60:
            insights.append("📈 整体口碑良好：正面评价占比超过60%，用户满意度较高")
        elif sentiment_pct.get('negative', 0) > 40:
            insights.append("⚠️ 负面声音较多：建议关注用户反馈，及时优化产品或服务")
        else:
            insights.append("📊 情感分布均衡：用户评价呈现多元化，有改进空间")

        # 热词洞察
        if self.hot_words:
            top_word = self.hot_words[0][0]
            insights.append(f"🔥 热点话题：「{top_word}」是最受关注的关键词，可围绕此话题进行内容策划")

        # 互动洞察
        stats = self._get_interaction_stats()
        if stats['avg_likes'] > 1000:
            insights.append(f"👍 高互动内容：平均点赞{stats['avg_likes']:.0f}，内容传播力较强")

        return insights

    def generate_html(self) -> str:
        """生成 HTML 报告"""
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        sentiment_pct = self._analyze_sentiment()
        hot_words = self._extract_hot_words()
        representative = self._get_representative_comments()
        interactions = self._get_interaction_stats()
        summary = self._generate_summary()
        insights = self._generate_insights()

        # 生成热词云 HTML
        word_cloud_html = self._generate_word_cloud_html(hot_words)

        # 生成 HTML
        html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{platform_name}_{self.keywords}_趋势报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header .meta {{ opacity: 0.9; font-size: 1.1em; }}
        .summary {{
            background: #f8f9fa;
            padding: 30px 40px;
            border-left: 5px solid #667eea;
            margin: 20px 40px;
            border-radius: 10px;
        }}
        .content {{ padding: 40px; }}
        .section {{ margin-bottom: 40px; }}
        .section-title {{
            font-size: 1.5em;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
            display: inline-block;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        .stat-card .number {{ font-size: 2.5em; font-weight: bold; margin-bottom: 5px; }}
        .stat-card .label {{ opacity: 0.9; font-size: 0.9em; }}
        .chart-container {{
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
        }}
        .word-cloud {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 15px;
        }}
        .word-tag {{
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: 500;
            transition: transform 0.2s;
        }}
        .word-tag:hover {{ transform: scale(1.1); }}
        .insights {{
            background: #e3f2fd;
            padding: 25px;
            border-radius: 15px;
            border-left: 5px solid #2196f3;
        }}
        .insights ul {{ list-style: none; padding-left: 0; }}
        .insights li {{
            padding: 10px 0;
            border-bottom: 1px dashed #bbdefb;
            font-size: 1.05em;
        }}
        .insights li:last-child {{ border-bottom: none; }}
        .comment-list {{
            display: grid;
            gap: 15px;
        }}
        .comment-item {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }}
        .comment-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.9em;
            color: #666;
        }}
        .comment-content {{ line-height: 1.6; }}
        .sentiment-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .positive {{ background: #c8e6c9; color: #2e7d32; }}
        .negative {{ background: #ffcdd2; color: #c62828; }}
        .neutral {{ background: #e0e0e0; color: #616161; }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 舆情分析报告</h1>
            <div class="meta">
                {platform_name} | 关键词: {self.keywords} | 生成时间: {timestamp}
            </div>
        </div>

        <div class="summary">
            <strong>📋 报告摘要：</strong>{summary}
        </div>

        <div class="content">
            <div class="section">
                <h2 class="section-title">📈 核心数据概览</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="number">{len(self.data)}</div>
                        <div class="label">分析内容数</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{self.total_comments}</div>
                        <div class="label">评论总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{sentiment_pct.get('positive', 0)}%</div>
                        <div class="label">正面评价</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{interactions['avg_likes']:.0f}</div>
                        <div class="label">平均点赞</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💭 情感分析分布</h2>
                <div class="chart-container">
                    <canvas id="sentimentChart" width="300" height="200"></canvas>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">🔥 热门讨论词云</h2>
                <div class="word-cloud">
                    {word_cloud_html}
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💡 舆情洞察</h2>
                <div class="insights">
                    <ul>
                        {''.join(f'<li>{insight}</li>' for insight in insights)}
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💬 代表性评论</h2>
                <div class="comment-list">
                    {self._generate_comments_html(representative)}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>MediaCrawler MCP 舆情分析系统生成</p>
            <p>本报告仅供数据分析参考</p>
            {f'<p>📄 报告位置：<a href="file:///{self.report_path_slashed}" style="color: #667eea; text-decoration: underline;">{self.report_path}</a></p>' if self.report_path else ''}
        </div>
    </div>

    <script>
        // 情感分析饼图
        const ctx = document.getElementById('sentimentChart').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: ['正面', '负面', '中性'],
                datasets: [{{
                    data: [{sentiment_pct.get('positive', 0)}, {sentiment_pct.get('negative', 0)}, {sentiment_pct.get('neutral', 0)}],
                    backgroundColor: ['#4caf50', '#f44336', '#9e9e9e'],
                    borderWidth: 0
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ font: {{ size: 14 }} }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

        return html_content

    def _generate_word_cloud_html(self, hot_words: List[Tuple[str, int]]) -> str:
        """生成词云 HTML"""
        if not hot_words:
            return '<span style="color: #999;">暂无热词数据</span>'

        max_count = max(w[1] for w in hot_words) if hot_words else 1
        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#fa709a']

        html_parts = []
        for i, (word, count) in enumerate(hot_words[:15]):
            size = max(0.8, count / max_count * 1.5)
            color = colors[i % len(colors)]
            html_parts.append(
                f'<span class="word-tag" style="font-size: {size:.1f}em; background: {color}20; color: {color};">'
                f'{word}</span>'
            )

        return '\n'.join(html_parts)

    def _generate_comments_html(self, comments: List[Dict]) -> str:
        """生成评论 HTML"""
        if not comments:
            return '<p style="color: #999;">暂无代表性评论</p>'

        html_parts = []
        for comment in comments[:10]:
            sentiment = comment.get('sentiment', 'neutral')
            sentiment_class = sentiment
            sentiment_label = '正面' if sentiment == 'positive' else '负面' if sentiment == 'negative' else '中性'

            html_parts.append(f'''
                <div class="comment-item">
                    <div class="comment-header">
                        <span>👤 {comment.get('nickname', '匿名用户')}</span>
                        <span>
                            <span class="sentiment-badge {sentiment_class}">{sentiment_label}</span>
                            👍 {comment.get('like_count', 0)}
                        </span>
                    </div>
                    <div class="comment-content">{comment.get('content', '')}</div>
                </div>
            ''')

        return '\n'.join(html_parts)

    def save_report(self) -> str:
        """保存报告并返回文件路径"""
        # 创建输出目录
        os.makedirs(self.output_path, exist_ok=True)

        # 生成文件名
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{platform_name}_{self.keywords}_趋势报告_{timestamp}.html"

        # 清理文件名中的非法字符
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        filepath = os.path.join(self.output_path, filename)

        # 写入文件
        html_content = self.generate_html()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    def get_console_summary(self) -> str:
        """获取控制台显示的摘要"""
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        sentiment_pct = self._analyze_sentiment()

        summary = f'''
╔══════════════════════════════════════════════════════════════╗
║                    📊 舆情分析完成                           ║
╠══════════════════════════════════════════════════════════════╣
║ 平台: {platform_name:<10} 关键词: {self.keywords:<25}    ║
╠══════════════════════════════════════════════════════════════╣
║ 📈 数据概览                                                  ║
║    • 分析内容数: {len(self.data):>4} 条                               ║
║    • 评论总数:   {self.total_comments:>4} 条                               ║
╠══════════════════════════════════════════════════════════════╣
║ 💭 情感分布                                                  ║
║    • 正面: {sentiment_pct.get('positive', 0):>5}%                                              ║
║    • 负面: {sentiment_pct.get('negative', 0):>5}%                                              ║
║    • 中性: {sentiment_pct.get('neutral', 0):>5}%                                              ║
╠══════════════════════════════════════════════════════════════╣
║ 🔥 热门关键词 Top5                                           ║
'''
        for i, (word, count) in enumerate(self.hot_words[:5], 1):
            summary += f'║    {i}. {word:<10} ({count}次)\n'

        summary += '''╠══════════════════════════════════════════════════════════════╣
║ 💡 报告已保存至:                                             ║
'''
        # 添加文件路径（会单独处理）
        summary += '╚══════════════════════════════════════════════════════════════╝'

        return summary


def generate_report(
    platform: str,
    keywords: str,
    data: List[Dict],
    output_path: str = "reports"
) -> Tuple[str, str, str]:
    """
    生成报告主函数

    Returns:
        (report_path, console_summary, html_content)
    """
    # 先导入并生成文件名
    import os
    os.makedirs(output_path, exist_ok=True)
    platform_name = ReportGenerator.PLATFORM_NAMES.get(platform, platform)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = re.sub(r'[\\/*?:"<>|]', "_", f"{platform_name}_{keywords}_趋势报告_{timestamp}.html")
    report_path = os.path.join(output_path, filename)
    abs_path = os.path.abspath(report_path)

    # 创建 generator 并传入路径
    generator = ReportGenerator(platform, keywords, data, output_path, abs_path)

    # 生成 HTML（包含路径链接）
    html_content = generator.generate_html()

    # 保存到文件
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    summary = generator.get_console_summary()
    return abs_path, summary, html_content


def generate_report_content(
    platform: str,
    keywords: str,
    data: List[Dict],
) -> Tuple[str, str]:
    """
    生成报告内容（不保存文件，仅返回内容）

    Returns:
        (console_summary, html_content)
    """
    generator = ReportGenerator(platform, keywords, data, "")
    summary = generator.get_console_summary()
    html_content = generator.generate_html()
    return summary, html_content

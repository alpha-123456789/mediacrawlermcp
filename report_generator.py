# -*- coding: utf-8 -*-
"""
智能舆情报告生成器 v3.0
根据数据特征动态生成不同风格的报告
"""

import os
import re
import json
import jieba
import jieba.analyse
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from collections import Counter
from pathlib import Path

# 默认报告目录（如果调用者未指定）
PROJECT_ROOT = Path(__file__).parent
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"


class SentimentAnalyzer:
    """情感分析器"""

    POSITIVE_WORDS = {
        '好', '棒', '优秀', '喜欢', '爱', '赞', '强', '完美', '推荐', '满意',
        '不错', '值得', '惊喜', '漂亮', '好看', '好用', '实用', '方便', '快速',
        '专业', '贴心', '周到', '划算', '便宜', '实惠', '超值', '高品质',
        '舒服', '愉快', '开心', '幸福', '感动', '感谢', '支持',
        '给力', '厉害', '牛', '香', '甜', '美', '可爱', '搞笑', '有趣',
        '精彩', '经典', '火爆', '热门', '流行', '时尚', '新颖', '创新',
        '清晰', '流畅', '稳定', '高效', '便捷', '智能', '温暖',
        '靠谱', '放心', '安心', '省心', '省事儿', '耐用', '结实',
        '神器', '爆款', '种草', '真香', 'yyds', '绝了', '封神', '入手', '回购'
    }

    NEGATIVE_WORDS = {
        '差', '烂', '糟', '坏', '差劲', '失望', '后悔', '垃圾', '坑', '骗',
        '假', '贵', '慢', '卡', '顿', '麻烦', '复杂', '难用', '难吃', '难看',
        '丑', '臭', '脏', '乱', '吵', '挤', '远', '偏', '不方便', '不划算',
        '不值', '亏了', '上当', '受骗', '被坑', '差评', '投诉', '退货', '退款',
        '坏了', '破', '旧', '弱', 'low', '土', '过时',
        '无聊', '没劲', '尴尬', '恶心', '讨厌', '烦', '累', '痛苦', '难过',
        '伤心', '气', '怒', '火', '骂', '批评', '质疑', '怀疑', '担心', '怕',
        '后悔', '踩雷', '劝退', '翻车', '避雷'
    }

    PURCHASE_INTENT_WORDS = {
        '买', '购买', '下单', '入手', '冲', '想买', '准备买', '考虑买',
        '多少钱', '价格', '贵不贵', '便宜', '优惠', '哪里买', '链接',
        '求链接', '求推荐', '值得买', '报暗号', '团购', '怎么买', '在哪买',
        '什么价', '有活动', '直播价'
    }

    @classmethod
    def analyze(cls, text: str) -> Tuple[str, float]:
        if not text:
            return 'neutral', 0.5
        text = str(text)
        pos_count = sum(1 for word in cls.POSITIVE_WORDS if word in text)
        neg_count = sum(1 for word in cls.NEGATIVE_WORDS if word in text)
        total = pos_count + neg_count
        if total == 0:
            return 'neutral', 0.5
        score = pos_count / (pos_count + neg_count * 1.2 + 0.1)
        if score > 0.6:
            return 'positive', min(score, 1.0)
        elif score < 0.4:
            return 'negative', max(1 - score, 0.0)
        else:
            return 'neutral', 0.5

    @classmethod
    def has_purchase_intent(cls, text: str) -> bool:
        if not text:
            return False
        return any(word in text for word in cls.PURCHASE_INTENT_WORDS)


class DataAnalyzer:
    """数据特征分析器 - 使用自动字段识别"""

    def __init__(self, data: List[Dict]):
        self.data = data
        from auto_field_detector import AutoFieldDetector
        self.detector = AutoFieldDetector()
        self.field_map = self.detector.detect_from_data_list(data)

    def detect_features(self) -> Dict[str, bool]:
        """检测数据包含哪些特征"""
        if not self.data:
            return {}

        first_item = self.data[0]

        features = {
            'has_likes': 'likes' in self.field_map,
            'has_comments': 'comments' in self.field_map,
            'has_shares': 'shares' in self.field_map,
            'has_views': 'views' in self.field_map,
            'has_collects': 'favorites' in self.field_map,
            'has_coins': 'coins' in self.field_map,
            'has_comment_data': False,
            'has_author_info': False,
            'has_time_info': False,
            'has_content_text': False,
        }

        # 检测实际评论内容
        for item in self.data:
            if item.get('comments') and len(item['comments']) > 0:
                features['has_comment_data'] = True
                break

        # 检测作者信息
        if first_item.get('nickname') or first_item.get('author'):
            features['has_author_info'] = True

        # 检测时间信息
        if first_item.get('create_time') or first_item.get('created_at'):
            features['has_time_info'] = True

        # 检测内容文本
        if first_item.get('desc') or first_item.get('title') or first_item.get('content_text') or first_item.get('caption'):
            features['has_content_text'] = True

        return features

    def _get_standardized_value(self, item: Dict, standard_field: str) -> int:
        """使用自动识别的字段映射获取值"""
        from auto_field_detector import get_standardized_value
        return get_standardized_value(item, self.field_map, standard_field)

    def get_data_profile(self) -> Dict:
        """获取数据画像"""
        features = self.detect_features()

        # 统计各类数据
        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_views = 0
        total_collects = 0

        for item in self.data:
            total_likes += self._get_standardized_value(item, 'likes')
            total_comments += self._get_standardized_value(item, 'comments')
            total_shares += self._get_standardized_value(item, 'shares')
            total_views += self._get_standardized_value(item, 'views')
            total_collects += self._get_standardized_value(item, 'favorites')

        count = len(self.data) if self.data else 1

        return {
            'count': len(self.data),
            'features': features,
            'totals': {
                'likes': total_likes,
                'comments': total_comments,
                'shares': total_shares,
                'views': total_views,
                'collects': total_collects,
            },
            'averages': {
                'likes': round(total_likes / count, 1),
                'comments': round(total_comments / count, 1),
                'shares': round(total_shares / count, 1),
                'views': round(total_views / count, 1),
                'collects': round(total_collects / count, 1),
            }
        }


class SmartReportGenerator:
    """智能报告生成器"""

    PLATFORM_NAMES = {
        'xhs': '小红书',
        'dy': '抖音',
        'ks': '快手',
        'bili': 'B站',
        'wb': '微博',
        'tieba': '百度贴吧',
        'zhihu': '知乎'
    }

    PLATFORM_ICONS = {
        'xhs': '&#128213;',  # 📕
        'dy': '&#127925;',   # 🎵
        'ks': '&#128241;',   # 📱
        'bili': '&#128250;', # 📺
        'wb': '&#127760;',   # 🌐
        'tieba': '&#128204;', # 📌
        'zhihu': '&#128161;', # 💡
    }

    REPORT_TYPE_NAMES = {
        'sentiment': '舆情分析',
        'trend': '热门趋势',
        'hot_topics': '热门话题',
        'keyword': '关键词分析',
        'volume': '声量分析',
        'viral_spread': '传播分析',
        'influencer': '影响力账号',
        'audience': '用户画像',
        'comparison': '竞品对比',
        'risk': '舆情风险',
        'auto': '智能分析',
    }

    def __init__(
        self,
        platform: str,
        keywords: str,
        data: List[Dict],
        output_path: str = "reports",
        report_path: str = None,
        report_type: str = "auto"
    ):
        self.platform = platform
        self.keywords = keywords
        self.data = data
        self.output_path = output_path
        self.report_path = report_path
        self.report_path_slashed = report_path.replace('\\', '/') if report_path else None

        # 分析数据特征
        self.analyzer = DataAnalyzer(data)
        self.profile = self.analyzer.get_data_profile()
        self.features = self.profile['features']

        # 自动选择报告类型
        self.report_type = self._auto_select_report_type(report_type)

        # 缓存分析结果
        self.sentiment_stats = {'positive': 0, 'negative': 0, 'neutral': 0}
        self.hot_words = []

    def _auto_select_report_type(self, requested_type: str) -> str:
        """根据数据特征自动选择报告类型"""
        if requested_type != "auto":
            return requested_type

        features = self.features

        # 如果有评论数据 -> 舆情分析
        if features.get('has_comment_data', False):
            return 'sentiment'

        # 如果有播放/阅读数据 -> 热门趋势
        if features.get('has_views', False):
            return 'trend'

        # 默认舆情分析
        return 'sentiment'

    def _analyze_sentiment(self) -> Dict:
        """分析情感分布"""
        sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}
        total_comments = 0

        for item in self.data:
            # 分析内容情感
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            if text:
                sentiment, _ = SentimentAnalyzer.analyze(text)
                sentiments[sentiment] += 1

            # 分析评论情感
            for comment in item.get('comments', []):
                comment_text = comment.get('content', '')
                if comment_text:
                    sentiment, _ = SentimentAnalyzer.analyze(comment_text)
                    sentiments[sentiment] += 1
                    total_comments += 1

        self.sentiment_stats = sentiments
        total = sum(sentiments.values())
        if total > 0:
            return {k: round(v / total * 100, 1) for k, v in sentiments.items()}
        return sentiments

    def _analyze_purchase_intent(self) -> Dict:
        """分析购买意向"""
        intent_count = 0
        total = 0

        for item in self.data:
            for comment in item.get('comments', []):
                text = comment.get('content', '')
                if len(text) > 3:
                    total += 1
                    if SentimentAnalyzer.has_purchase_intent(text):
                        intent_count += 1

        return {
            'intent_count': intent_count,
            'total': total,
            'intent_rate': round(intent_count / total * 100, 1) if total > 0 else 0
        }

    def _extract_hot_words(self) -> List[Tuple[str, int]]:
        """提取热词"""
        all_text = []

        for item in self.data:
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            if text:
                all_text.append(text)

            for comment in item.get('comments', []):
                content = comment.get('content', '')
                if content:
                    all_text.append(content)

        if not all_text:
            return []

        full_text = ' '.join(all_text)
        keywords = jieba.analyse.extract_tags(full_text, topK=30, withWeight=True)
        hot_words = [(word, int(weight * 1000)) for word, weight in keywords]
        self.hot_words = hot_words[:20]
        return self.hot_words

    def _get_representative_comments(self) -> List[Dict]:
        """获取代表性评论"""
        comments = []

        for item in self.data:
            for comment in item.get('comments', []):
                content = comment.get('content', '')
                if len(content) > 10 and len(content) < 300:
                    sentiment, score = SentimentAnalyzer.analyze(content)
                    comments.append({
                        'content': content,
                        'sentiment': sentiment,
                        'score': score,
                        'like_count': comment.get('like_count', 0),
                        'nickname': comment.get('comment_nickname', '') or comment.get('user_nickname', ''),
                        'has_intent': SentimentAnalyzer.has_purchase_intent(content)
                    })

        comments.sort(key=lambda x: (x['has_intent'], x['like_count']), reverse=True)
        return comments[:10]

    def _format_number(self, num: int) -> str:
        if num >= 10000:
            return f"{num / 10000:.1f}万"
        return str(num)

    def _generate_metric_cards(self) -> str:
        """根据数据特征生成指标卡片"""
        cards = []
        profile = self.profile
        totals = profile['totals']

        # 基础卡片：内容数
        cards.append({
            'icon': '&#128202;',  # 📊
            'value': str(profile['count']),
            'label': '分析内容数'
        })

        # 根据特征添加卡片
        if self.features.get('has_likes'):
            cards.append({
                'icon': '&#10084;&#65039;',  # ❤️
                'value': self._format_number(totals['likes']),
                'label': '总点赞数'
            })

        if self.features.get('has_comments'):
            cards.append({
                'icon': '&#128172;',  # 💬
                'value': self._format_number(totals['comments']),
                'label': '评论总数'
            })

        if self.features.get('has_views'):
            cards.append({
                'icon': '&#128065;',  # 👁️
                'value': self._format_number(totals['views']),
                'label': '总播放量'
            })

        if self.features.get('has_shares'):
            cards.append({
                'icon': '&#128640;',  # 🚀
                'value': self._format_number(totals['shares']),
                'label': '分享次数'
            })

        if self.features.get('has_collects'):
            cards.append({
                'icon': '&#11088;',  # ⭐
                'value': self._format_number(totals['collects']),
                'label': '收藏数'
            })

        # 如果有评论数据，添加情感分析卡片
        if self.features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            cards.append({
                'icon': '&#128077;',  # 👍
                'value': f"{sentiment_pct.get('positive', 0)}%",
                'label': '正面评价'
            })

        # 生成HTML
        html = '<div class="metric-grid">'
        for card in cards:
            html += f'''
            <div class="metric-card">
                <div class="metric-icon">{card['icon']}</div>
                <div class="metric-value">{card['value']}</div>
                <div class="metric-label">{card['label']}</div>
            </div>
            '''
        html += '</div>'
        return html

    def _generate_content_list(self) -> str:
        """生成内容列表（根据数据特征决定显示哪些字段）"""
        items = []

        for item in self.data[:10]:  # TOP 10
            interact = item.get('interact_info', {})

            # 获取标题
            title = item.get('title', item.get('desc', item.get('caption', '无标题')))[:60]

            # 获取作者
            author = item.get('nickname', item.get('author', '匿名'))[:15]

            # 构建统计信息（根据可用字段）
            stats = []

            if self.features.get('has_likes'):
                likes = interact.get('like_count', 0) or interact.get('digg_count', 0) or 0
                stats.append(f"&#10084;&#65039; {self._format_number(likes)}")

            if self.features.get('has_views'):
                views = interact.get('view_count', 0) or interact.get('play_count', 0) or 0
                stats.append(f"&#128065; {self._format_number(views)}")

            if self.features.get('has_comments'):
                comments = interact.get('comment_count', 0) or interact.get('comments_count', 0) or 0
                stats.append(f"&#128172; {self._format_number(comments)}")

            items.append({
                'title': title,
                'author': author,
                'stats': ' | '.join(stats) if stats else ''
            })

        html = '<div class="content-list">'
        for i, item in enumerate(items, 1):
            html += f'''
            <div class="content-item">
                <div class="content-rank">{i}</div>
                <div class="content-info">
                    <div class="content-title">{item['title']}</div>
                    <div class="content-meta">&#128100; {item['author']}</div>
                </div>
                <div class="content-stats">{item['stats']}</div>
            </div>
            '''
        html += '</div>'
        return html

    def _generate_insights(self) -> str:
        """根据数据特征生成洞察"""
        insights = []
        profile = self.profile
        features = self.features

        # 基于数据量的洞察
        if profile['count'] < 5:
            insights.append({
                'icon': '&#9888;&#65039;',
                'title': '数据样本较少',
                'content': f'当前仅分析到{profile["count"]}条内容，建议增加抓取数量以获得更准确的分析结果。'
            })
        else:
            insights.append({
                'icon': '&#9999;&#65039;',
                'title': '数据覆盖良好',
                'content': f'成功分析了{profile["count"]}条内容，数据样本充足，分析结果具有参考价值。'
            })

        # 基于互动数据的洞察
        if features.get('has_likes') and profile['averages']['likes'] > 1000:
            insights.append({
                'icon': '&#128293;',
                'title': '高互动内容',
                'content': f'平均每条内容获得{profile["averages"]["likes"]:.0f}点赞，整体热度较高。'
            })

        if features.get('has_views') and profile['averages']['views'] > 10000:
            insights.append({
                'icon': '&#128640;',
                'title': '高曝光内容',
                'content': f'平均播放量达到{self._format_number(int(profile["averages"]["views"]))}，内容传播力较强。'
            })

        # 基于评论的情感洞察
        if features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            if sentiment_pct.get('positive', 0) > 60:
                insights.append({
                    'icon': '&#128077;',
                    'title': '口碑良好',
                    'content': f'{sentiment_pct["positive"]}%的评论呈正面倾向，用户满意度较高。'
                })
            elif sentiment_pct.get('negative', 0) > 40:
                insights.append({
                    'icon': '&#9888;&#65039;',
                    'title': '负面声音较多',
                    'content': f'{sentiment_pct["negative"]}%的评论呈负面倾向，建议关注用户反馈。'
                })

        # 购买意向洞察
        if features.get('has_comment_data'):
            purchase = self._analyze_purchase_intent()
            if purchase['intent_rate'] > 20:
                insights.append({
                    'icon': '&#128722;',
                    'title': '购买意向强烈',
                    'content': f'{purchase["intent_rate"]}%的评论显示购买意向，转化潜力较大。'
                })

        # 生成HTML
        html = '<div class="insight-list">'
        for insight in insights:
            html += f'''
            <div class="insight-item">
                <div class="insight-title">{insight['icon']} {insight['title']}</div>
                <div class="insight-content">{insight['content']}</div>
            </div>
            '''
        html += '</div>'
        return html

    def _generate_hot_words(self) -> str:
        """生成热词云"""
        hot_words = self._extract_hot_words()

        if not hot_words:
            return '<div class="word-cloud"><span style="color: #999;">暂无足够文本数据生成热词</span></div>'

        max_count = max(w[1] for w in hot_words)
        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#11998e', '#38ef7d', '#ffd93d']

        html = '<div class="word-cloud">'
        for i, (word, count) in enumerate(hot_words[:20]):
            size_class = min(5, max(1, int(count / max_count * 5)))
            color = colors[i % len(colors)]
            bg_color = f"{color}20"
            html += f'<span class="word-tag size-{size_class}" style="background: {bg_color}; color: {color};">{word}</span>'
        html += '</div>'
        return html

    def _generate_comment_analysis(self) -> str:
        """生成评论深度分析模块"""
        if not self.features.get('has_comment_data', False):
            return ''

        # 获取代表性评论用于分析
        comments = self._get_representative_comments()
        if not comments:
            return ''

        # 统计情感分布
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        for comment in comments:
            sentiment_counts[comment['sentiment']] += 1

        # 分析用户关注点
        topics = []
        purchase_intent = self._analyze_purchase_intent()

        # 根据评论内容提取关注点
        for comment in comments[:10]:
            content = comment['content']
            if any(kw in content for kw in ['价格', '多少钱', '贵', '便宜', '性价比']):
                topics.append('价格关注')
            if any(kw in content for kw in ['质量', '效果', '好用', '不好用']):
                topics.append('产品效果')
            if any(kw in content for kw in ['服务', '客服', '售后']):
                topics.append('服务态度')
            if any(kw in content for kw in ['推荐', '种草', '安利']):
                topics.append('推荐意愿')

        # 统计高频话题
        topic_counter = Counter(topics)
        top_topics = topic_counter.most_common(3)

        # 获取正面和负面例子
        positive_examples = [c for c in comments if c['sentiment'] == 'positive'][:2]
        negative_examples = [c for c in comments if c['sentiment'] == 'negative'][:2]

        html = '''
        <div class="section">
            <div class="section-title">&#128172; 评论深度分析</div>
            <div style="display: grid; gap: 20px;">
        '''

        # 用户关注焦点
        if top_topics:
            html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 12px;">'
            html += '<div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#127919; 用户关注焦点</div>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
            theme = self._get_theme()
            for topic, count in top_topics:
                html += f'<span style="background: {theme["primary"]}20; color: {theme["primary"]}; padding: 6px 12px; border-radius: 16px; font-size: 0.85em;">{topic} ({count})</span>'
            html += '</div></div>'

        # 购买意向
        if purchase_intent['intent_rate'] > 0:
            html += f'''
            <div style="background: #f8f9fa; padding: 15px; border-radius: 12px;">
                <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128722; 购买意向分析</div>
                <p style="color: #666; line-height: 1.6;">
                    {purchase_intent['intent_count']}条评论显示购买意向，占比{purchase_intent['intent_rate']}%。
                    用户对产品的购买欲望{'较强' if purchase_intent['intent_rate'] > 20 else '一般' if purchase_intent['intent_rate'] > 10 else '较弱'}。
                </p>
            </div>
            '''

        # 典型正面评价
        if positive_examples:
            html += '<div style="background: #f6ffed; padding: 15px; border-radius: 12px; border-left: 4px solid #52c41a;">'
            html += '<div style="font-weight: 600; color: #52c41a; margin-bottom: 10px;">&#128077; 典型正面评价</div>'
            for ex in positive_examples:
                html += f'<p style="color: #555; line-height: 1.6; margin: 5px 0;">"{ex["content"][:100]}..."</p>'
            html += '</div>'

        # 典型负面评价
        if negative_examples:
            html += '<div style="background: #fff2f0; padding: 15px; border-radius: 12px; border-left: 4px solid #f5222d;">'
            html += '<div style="font-weight: 600; color: #f5222d; margin-bottom: 10px;">&#128078; 典型负面评价</div>'
            for ex in negative_examples:
                html += f'<p style="color: #555; line-height: 1.6; margin: 5px 0;">"{ex["content"][:100]}..."</p>'
            html += '</div>'
        else:
            html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 12px;">'
            html += '<div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128078; 典型负面评价</div>'
            html += '<p style="color: #888;">未发现明显负面评价</p>'
            html += '</div>'

        html += '</div></div>'
        return html

    def _generate_action_plan(self) -> str:
        """生成处理建议与行动方案"""
        if not self.features.get('has_comment_data', False):
            return ''

        sentiment_pct = self._analyze_sentiment()
        purchase = self._analyze_purchase_intent()

        # 根据数据生成建议
        suggestions = []

        # 情感分析建议
        if sentiment_pct.get('positive', 0) > 60:
            suggestions.append({
                'category': '营销方向',
                'icon': '&#128640;',
                'content': '正面评价占比高，建议将好评内容作为营销素材进行二次传播，增强品牌口碑效应。'
            })
        elif sentiment_pct.get('negative', 0) > 30:
            suggestions.append({
                'category': '紧急处理',
                'icon': '&#9888;&#65039;',
                'content': '负面评价较多，建议及时回应负面评论，了解具体问题并给出解决方案。'
            })

        # 购买意向建议
        if purchase['intent_rate'] > 20:
            suggestions.append({
                'category': '转化优化',
                'icon': '&#128722;',
                'content': f"购买意向率达{purchase['intent_rate']}%，建议加强购买链路引导，设置专属优惠码促进转化。"
            })

        # 内容策略建议
        if self.profile['averages'].get('likes', 0) > 1000:
            suggestions.append({
                'category': '内容策略',
                'icon': '&#128161;',
                'content': '高互动内容表现良好，建议持续产出同类型高质量内容，保持用户活跃度。'
            })

        if not suggestions:
            suggestions.append({
                'category': '数据收集',
                'icon': '&#128200;',
                'content': '建议增加数据采集量，覆盖更多用户反馈，以便进行更全面的舆情分析。'
            })

        html = '''
        <div class="section">
            <div class="section-title">&#128221; 处理建议与行动方案</div>
            <div style="display: grid; gap: 15px;">
        '''

        theme = self._get_theme()
        for s in suggestions:
            html += f'''
            <div style="display: flex; gap: 15px; align-items: flex-start; background: #f8f9fa; padding: 15px; border-radius: 12px;">
                <div style="font-size: 1.5em;">{s['icon']}</div>
                <div>
                    <div style="font-weight: 600; color: {theme['primary']}; margin-bottom: 5px;">{s['category']}</div>
                    <div style="color: #555; line-height: 1.6;">{s['content']}</div>
                </div>
            </div>
            '''

        html += '</div></div>'
        return html

    def _generate_comments_section(self) -> str:
        """生成评论区域（如果有评论数据）"""
        if not self.features.get('has_comment_data', False):
            return ''

        comments = self._get_representative_comments()
        if not comments:
            return ''

        html = '''
        <div class="section">
            <div class="section-title">&#128172; 代表性用户评论</div>
            <div class="comment-list">
        '''

        sentiment_labels = {
            'positive': ('正面', '#52c41a'),
            'negative': ('负面', '#f5222d'),
            'neutral': ('中性', '#faad14')
        }

        for comment in comments[:6]:
            sentiment = comment['sentiment']
            label, color = sentiment_labels.get(sentiment, ('中性', '#faad14'))

            intent_tag = '&#128722; 购买意向' if comment.get('has_intent') else ''

            html += f'''
            <div class="comment-item" style="border-left-color: {color};">
                <div class="comment-header">
                    <span class="comment-user">&#128100; {comment.get('nickname', '匿名用户')}</span>
                    <span class="comment-senti" style="background: {color}20; color: {color};">{label}</span>
                </div>
                <div class="comment-content">{comment['content']}</div>
                <div class="comment-footer">
                    <span>&#10084;&#65039; {comment.get('like_count', 0)}</span>
                    {f'<span style="color: #667eea;">{intent_tag}</span>' if intent_tag else ''}
                </div>
            </div>
            '''

        html += '</div></div>'
        return html

    def _generate_executive_summary(self) -> str:
        """生成执行摘要"""
        profile = self.profile
        features = self.features

        # 核心发现
        if features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            positive = sentiment_pct.get('positive', 0)
            negative = sentiment_pct.get('negative', 0)

            if positive > 60:
                core_finding = f"整体口碑良好，正面评价占比 {positive:.0f}%"
            elif negative > 30:
                core_finding = f"存在舆情风险，负面评价占比 {negative:.0f}%，建议关注"
            else:
                core_finding = "舆论分布较为均衡，需结合具体场景分析"
        else:
            core_finding = f"共分析 {profile['count']} 条内容"

        # 关键指标
        highlights = []
        if features.get('has_likes') and profile['totals']['likes'] > 0:
            highlights.append(f"总点赞 {self._format_number(profile['totals']['likes'])}")
        if features.get('has_views') and profile['totals']['views'] > 0:
            highlights.append(f"总播放 {self._format_number(profile['totals']['views'])}")
        if features.get('has_comments') and profile['totals']['comments'] > 0:
            highlights.append(f"总评论 {self._format_number(profile['totals']['comments'])}")

        # 风险提示
        risk_alert = ""
        if features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            if sentiment_pct.get('negative', 0) > 30:
                risk_alert = f"<div style='color: #f5222d; margin-top: 10px; font-weight: bold;'>&#9888; 负面评价占比 {sentiment_pct['negative']:.0f}%，建议及时处理</div>"

        return f'''
        <div class="section" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
            <div class="section-title" style="color: white; border-left-color: white;">&#128188; 执行摘要</div>
            <div style="font-size: 1.1em; margin-bottom: 15px;">
                <strong>核心发现：</strong>{core_finding}
            </div>
            <div style="margin-bottom: 10px;">
                <strong>关键指标：</strong>{' | '.join(highlights) if highlights else '暂无'}
            </div>
            {risk_alert}
        </div>
        '''

    def _generate_sentiment_chart(self) -> str:
        """生成情感分析图表（如果有评论数据）"""
        if not self.features.get('has_comment_data', False):
            return ''

        sentiment_pct = self._analyze_sentiment()

        # 生成情感分析文字说明
        analysis_text = ""
        if sentiment_pct.get('positive', 0) > sentiment_pct.get('negative', 0):
            analysis_text = "整体情绪偏正面，用户满意度较高"
        elif sentiment_pct.get('negative', 0) > 30:
            analysis_text = "负面情绪占比较高，建议关注用户核心诉求"
        else:
            analysis_text = "情绪分布较为中性，需具体分析用户关注点"

        return f'''
        <div class="section">
            <div class="section-title">&#128200; 情感分析分布</div>
            <div class="chart-container" id="sentimentChart" style="height: 280px;"></div>
            <div style="text-align: center; color: #666; margin-top: 10px; font-size: 0.9em;">
                {analysis_text}
            </div>
            <script>
                var chart = echarts.init(document.getElementById('sentimentChart'));
                chart.setOption({{
                    tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}%' }},
                    legend: {{ bottom: '5%', left: 'center' }},
                    series: [{{
                        type: 'pie',
                        radius: ['40%', '70%'],
                        center: ['50%', '45%'],
                        data: [
                            {{ value: {sentiment_pct.get('positive', 0)}, name: '正面', itemStyle: {{ color: '#52c41a' }} }},
                            {{ value: {sentiment_pct.get('neutral', 0)}, name: '中性', itemStyle: {{ color: '#faad14' }} }},
                            {{ value: {sentiment_pct.get('negative', 0)}, name: '负面', itemStyle: {{ color: '#f5222d' }} }}
                        ],
                        label: {{
                            formatter: '{{b}}<br/>{{c}}%'
                        }}
                    }}]
                }});
            </script>
        </div>
        '''

    def _get_theme(self) -> Dict:
        """根据数据特征选择主题色"""
        features = self.features

        # 有评论数据 -> 蓝紫色（舆情分析风格）
        if features.get('has_comment_data'):
            return {
                'primary': '#667eea',
                'secondary': '#764ba2',
                'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                'bg': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            }

        # 有播放数据 -> 粉紫色（趋势风格）
        if features.get('has_views'):
            return {
                'primary': '#ff9a9e',
                'secondary': '#fecfef',
                'gradient': 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
                'bg': 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
            }

        # 默认 -> 青绿色
        return {
            'primary': '#11998e',
            'secondary': '#38ef7d',
            'gradient': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
            'bg': 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)',
        }

    def generate_html(self) -> str:
        """生成完整HTML报告"""
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '分析')
        platform_icon = self.PLATFORM_ICONS.get(self.platform, '&#128240;')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        theme = self._get_theme()

        # 根据数据特征决定包含哪些模块
        executive_summary = self._generate_executive_summary()
        sentiment_section = self._generate_sentiment_chart() if self.features.get('has_comment_data') else ''
        comment_analysis_section = self._generate_comment_analysis() if self.features.get('has_comment_data') else ''
        action_plan_section = self._generate_action_plan()
        comments_section = self._generate_comments_section() if self.features.get('has_comment_data') else ''
        content_list_section = f'''
        <div class="section">
            <div class="section-title">&#127942; 热门内容排行 TOP 10</div>
            {self._generate_content_list()}
        </div>
        ''' if self.data else ''

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{platform_name}_{self.keywords}_{report_type_name}报告</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: {theme['bg']};
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            padding: 40px 20px;
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            margin-bottom: 25px;
            box-shadow: 0 15px 50px rgba(0,0,0,0.15);
        }}
        .header h1 {{
            font-size: 2.2em;
            background: {theme['gradient']};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header .subtitle {{
            color: #666;
            margin-top: 12px;
            font-size: 1.1em;
        }}
        .header .meta {{
            color: #999;
            margin-top: 12px;
            font-size: 0.9em;
        }}

        .section {{
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .section-title {{
            font-size: 1.4em;
            color: #333;
            margin-bottom: 20px;
            padding-left: 12px;
            border-left: 4px solid {theme['primary']};
        }}

        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 15px;
        }}
        .metric-card {{
            background: rgba(255,255,255,0.9);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
            transition: transform 0.3s;
        }}
        .metric-card:hover {{ transform: translateY(-3px); }}
        .metric-icon {{ font-size: 2em; margin-bottom: 8px; }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            background: {theme['gradient']};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .metric-label {{ color: #666; margin-top: 5px; font-size: 0.85em; }}

        .content-list {{ margin-top: 10px; }}
        .content-item {{
            display: flex;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }}
        .content-rank {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.85em;
            margin-right: 12px;
            background: #f0f0f0;
            color: #666;
            flex-shrink: 0;
        }}
        .content-item:nth-child(-n+3) .content-rank {{
            background: {theme['primary']};
            color: white;
        }}
        .content-info {{ flex: 1; min-width: 0; }}
        .content-title {{
            font-weight: 500;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: #333;
        }}
        .content-meta {{ font-size: 0.8em; color: #888; margin-top: 4px; }}
        .content-stats {{
            font-size: 0.8em;
            color: #666;
            text-align: right;
            white-space: nowrap;
        }}

        .word-cloud {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 16px;
        }}
        .word-tag {{
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 500;
            transition: transform 0.2s;
            cursor: pointer;
        }}
        .word-tag:hover {{ transform: scale(1.1); }}
        .word-tag.size-1 {{ font-size: 0.85em; opacity: 0.7; }}
        .word-tag.size-2 {{ font-size: 0.95em; opacity: 0.85; }}
        .word-tag.size-3 {{ font-size: 1.1em; }}
        .word-tag.size-4 {{ font-size: 1.25em; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }}
        .word-tag.size-5 {{ font-size: 1.5em; box-shadow: 0 4px 15px rgba(0,0,0,0.15); }}

        .insight-list {{ display: grid; gap: 15px; }}
        .insight-item {{
            background: #f8f9fa;
            border-left: 4px solid {theme['primary']};
            padding: 15px 20px;
            border-radius: 0 12px 12px 0;
        }}
        .insight-title {{
            color: {theme['primary']};
            font-weight: 600;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .insight-content {{ color: #555; font-size: 0.95em; line-height: 1.6; }}

        .comment-list {{ display: grid; gap: 12px; }}
        .comment-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 12px;
            border-left: 4px solid #ddd;
        }}
        .comment-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.8em;
        }}
        .comment-user {{ color: {theme['primary']}; font-weight: 500; }}
        .comment-senti {{
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            font-weight: bold;
        }}
        .comment-content {{ color: #333; line-height: 1.6; font-size: 0.95em; }}
        .comment-footer {{
            margin-top: 8px;
            font-size: 0.75em;
            color: #888;
            display: flex;
            gap: 12px;
        }}

        .chart-container {{ width: 100%; height: 350px; }}

        .footer {{
            text-align: center;
            padding: 30px;
            color: rgba(255,255,255,0.9);
        }}

        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.6em; }}
            .metric-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{platform_name} {report_type_name}报告</h1>
            <p class="subtitle">关键词：「{self.keywords}」</p>
            <p class="meta">{platform_icon} {platform_name} | 生成时间：{timestamp} | 分析样本：{len(self.data)}条</p>
        </header>

        <!-- 1. 执行摘要 -->
        {executive_summary}

        <!-- 2. 核心数据概览 -->
        <div class="section">
            <div class="section-title">&#128202; 核心数据概览</div>
            {self._generate_metric_cards()}
        </div>

        <!-- 3. 情感分析可视化 -->
        {sentiment_section}

        <!-- 4. 热门内容排行 -->
        {content_list_section}

        <!-- 5. 热词综合分析 -->
        <div class="section">
            <div class="section-title">&#9731; 热门讨论词云</div>
            {self._generate_hot_words()}
        </div>

        <!-- 6. 评论深度分析 -->
        {comment_analysis_section}

        <!-- 7. 舆情洞察与建议 -->
        <div class="section">
            <div class="section-title">&#128161; 舆情洞察与建议</div>
            {self._generate_insights()}
        </div>

        <!-- 8. 处理建议与行动方案 -->
        {action_plan_section}

        <!-- 9. 代表性用户评论 -->
        {comments_section}

        <footer class="footer">
            <p>&#128202; {platform_name} 智能分析报告 | 生成时间：{timestamp}</p>
            {f'<p style="margin-top: 8px;"><a href="file:///{self.report_path_slashed}" style="color: white;">打开报告文件</a></p>' if self.report_path else ''}
        </footer>
    </div>
</body>
</html>'''

    def save_report(self) -> str:
        """保存报告"""
        os.makedirs(self.output_path, exist_ok=True)

        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '分析报告')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = re.sub(r'[\\/*?:"<>|]', "_", self.keywords)[:30]  # 限制关键词长度
        filename = re.sub(r'[\\/*?:"<>|]', "_", f"{platform_name}_{safe_keyword}_{report_type_name}_{timestamp}.html")
        filepath = os.path.join(self.output_path, filename)

        html_content = self.generate_html()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    def get_console_summary(self) -> str:
        """获取控制台摘要"""
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        profile = self.profile
        features = self.features

        summary = f'''
╔════════════════════════════════════════════════════════════════╗
║                    &#128202; 数据分析完成                           ║
╠════════════════════════════════════════════════════════════════╣
║ 平台: {platform_name:<12} 关键词: {self.keywords:<25}      ║
╠════════════════════════════════════════════════════════════════╣
║ &#128230; 数据特征                                                  ║
'''

        if features.get('has_views'):
            summary += f"║    &#128065; 播放数据: 有                                          ║\n"
        if features.get('has_likes'):
            summary += f"║    &#10084;&#65039; 点赞数据: 有                                          ║\n"
        if features.get('has_comments'):
            summary += f"║    &#128172; 评论数据: 有                                          ║\n"
        if features.get('has_comment_data'):
            summary += f"║    &#128100; 评论内容: 有 (可情感分析)                             ║\n"
        if features.get('has_shares'):
            summary += f"║    &#128640; 分享数据: 有                                          ║\n"
        if features.get('has_collects'):
            summary += f"║    &#11088; 收藏数据: 有                                          ║\n"

        summary += f'''╠════════════════════════════════════════════════════════════════╣
║ &#128200; 数据统计                                                  ║
║    内容数: {profile['count']:>4}                                       ║
'''
        if features.get('has_likes'):
            summary += f"║    总点赞: {self._format_number(profile['totals']['likes']):>10}                               ║\n"
        if features.get('has_comments'):
            summary += f"║    总评论: {self._format_number(profile['totals']['comments']):>10}                               ║\n"
        if features.get('has_views'):
            summary += f"║    总播放: {self._format_number(profile['totals']['views']):>10}                               ║\n"

        summary += '''╚════════════════════════════════════════════════════════════════╝'''

        return summary


def generate_report(
    platform: str,
    keywords: str,
    data: List[Dict],
    output_path: str = "reports",
    report_type: str = "auto"
) -> Tuple[str, str, str]:
    """
    生成报告主函数

    Args:
        platform: 平台标识
        keywords: 关键词
        data: 爬取的数据
        output_path: 输出路径
        report_type: 报告类型 (auto/sentiment/trend/comparison)，默认auto自动检测

    Returns:
        (report_path, console_summary, html_content)
    """
    os.makedirs(output_path, exist_ok=True)

    # 临时报告路径，实际文件名由 SmartReportGenerator.save_report() 根据 report_type 生成
    temp_report_path = os.path.join(output_path, "temp.html")
    abs_temp_path = os.path.abspath(temp_report_path)

    generator = SmartReportGenerator(platform, keywords, data, output_path, abs_temp_path, report_type)
    html_content = generator.generate_html()

    # 使用 save_report 生成正确文件名的报告
    report_path = generator.save_report()
    abs_path = os.path.abspath(report_path)

    summary = generator.get_console_summary()
    return abs_path, summary, html_content


def generate_report_content(
    platform: str,
    keywords: str,
    data: List[Dict],
) -> Tuple[str, str]:
    """
    生成报告内容（不保存文件）

    Returns:
        (console_summary, html_content)
    """
    generator = SmartReportGenerator(platform, keywords, data, "", "", "auto")
    summary = generator.get_console_summary()
    html_content = generator.generate_html()
    return summary, html_content

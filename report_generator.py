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
        """根据报告类型和数据特征选择主题色"""
        report_type = self.report_type
        features = self.features

        # 舆情风险 -> 红色系
        if report_type == 'risk':
            return {
                'primary': '#f5222d',
                'secondary': '#ff7875',
                'gradient': 'linear-gradient(135deg, #f5222d 0%, #ff7875 100%)',
                'bg': 'linear-gradient(135deg, #ff4d4f 0%, #ffa39e 100%)',
            }

        # 热门趋势/声量 -> 橙色系
        if report_type in ['trend', 'volume']:
            return {
                'primary': '#fa8c16',
                'secondary': '#ffa940',
                'gradient': 'linear-gradient(135deg, #fa8c16 0%, #ffc53d 100%)',
                'bg': 'linear-gradient(135deg, #faad14 0%, #ffd666 100%)',
            }

        # 关键词/热门话题 -> 绿色系
        if report_type in ['keyword', 'hot_topics']:
            return {
                'primary': '#52c41a',
                'secondary': '#95de64',
                'gradient': 'linear-gradient(135deg, #52c41a 0%, #95de64 100%)',
                'bg': 'linear-gradient(135deg, #73d13d 0%, #b7eb8f 100%)',
            }

        # 传播分析 -> 青色系
        if report_type == 'viral_spread':
            return {
                'primary': '#13c2c2',
                'secondary': '#5cdbd3',
                'gradient': 'linear-gradient(135deg, #13c2c2 0%, #5cdbd3 100%)',
                'bg': 'linear-gradient(135deg, #36cfc9 0%, #87e8de 100%)',
            }

        # 影响力账号 -> 紫色系
        if report_type == 'influencer':
            return {
                'primary': '#722ed1',
                'secondary': '#b37feb',
                'gradient': 'linear-gradient(135deg, #722ed1 0%, #b37feb 100%)',
                'bg': 'linear-gradient(135deg, #9254de 0%, #d3adf7 100%)',
            }

        # 用户画像 -> 蓝色系
        if report_type == 'audience':
            return {
                'primary': '#1890ff',
                'secondary': '#69c0ff',
                'gradient': 'linear-gradient(135deg, #1890ff 0%, #69c0ff 100%)',
                'bg': 'linear-gradient(135deg, #40a9ff 0%, #91d5ff 100%)',
            }

        # 竞品对比 -> 靛青色系
        if report_type == 'comparison':
            return {
                'primary': '#2f4554',
                'secondary': '#546570',
                'gradient': 'linear-gradient(135deg, #2f4554 0%, #546570 100%)',
                'bg': 'linear-gradient(135deg, #3e4c5e 0%, #6c7a89 100%)',
            }

        # 舆情分析(默认) -> 蓝紫色
        return {
            'primary': '#667eea',
            'secondary': '#764ba2',
            'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            'bg': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        }

    def _generate_custom_section_by_type(self) -> str:
        """根据报告类型生成对应的专属模块"""
        report_type = self.report_type

        if report_type == 'trend':
            return self._generate_trend_section()
        elif report_type == 'volume':
            return self._generate_volume_section()
        elif report_type == 'keyword':
            return self._generate_keyword_section()
        elif report_type == 'hot_topics':
            return self._generate_hot_topics_section()
        elif report_type == 'viral_spread':
            return self._generate_viral_spread_section()
        elif report_type == 'influencer':
            return self._generate_influencer_section()
        elif report_type == 'audience':
            return self._generate_audience_section()
        elif report_type == 'comparison':
            return self._generate_comparison_section()
        elif report_type == 'risk':
            return self._generate_risk_section()
        else:
            return ''

    def _generate_trend_section(self) -> str:
        """热门趋势专属分析模块"""
        profile = self.profile
        features = self.features

        # 趋势洞察
        insights = []
        if features.get('has_views'):
            avg_views = profile['averages'].get('views', 0)
            if avg_views > 10000:
                insights.append('当前话题处于高热度状态，平均播放量超万级')
            elif avg_views > 1000:
                insights.append('话题热度中等，有一定关注度')
            else:
                insights.append('话题热度较低，属于小众话题')

        if features.get('has_likes'):
            like_rate = profile['averages'].get('likes', 0) / max(profile['averages'].get('views', 1), 1)
            if like_rate > 0.05:
                insights.append('用户互动意愿强，内容受欢迎度高')
            elif like_rate > 0.02:
                insights.append('用户互动意愿一般')
            else:
                insights.append('用户互动意愿较弱')

        # 时间趋势（如果有时间数据）
        time_trend = self._generate_time_trend()

        html = '''
        <div class="section">
            <div class="section-title">&#128293; 热门趋势分析</div>
            <div style="display: grid; gap: 20px;">
        '''

        # 趋势洞察
        if insights:
            html += '<div style="background: #fff7e6; padding: 15px; border-radius: 12px; border-left: 4px solid #faad14;">'
            html += '<div style="font-weight: 600; color: #fa8c16; margin-bottom: 10px;">&#128161; 趋势洞察</div>'
            html += '<ul style="margin-left: 20px; color: #666; line-height: 1.8;">'
            for insight in insights:
                html += f'<li>{insight}</li>'
            html += '</ul></div>'

        # 时间分布图
        html += time_trend

        html += '</div></div>'
        return html

    def _generate_volume_section(self) -> str:
        """声量分析专属模块"""
        profile = self.profile
        features = self.features

        # 计算声量指标
        total_likes = profile['totals'].get('likes', 0)
        total_comments = profile['totals'].get('comments', 0)
        total_views = profile['totals'].get('views', 0)
        count = profile['count']

        # 声量分级
        if total_likes > 100000 or total_views > 1000000:
            volume_level = '高'
            volume_color = '#f5222d'
        elif total_likes > 10000 or total_views > 100000:
            volume_level = '中'
            volume_color = '#faad14'
        else:
            volume_level = '低'
            volume_color = '#52c41a'

        html = f'''
        <div class="section">
            <div class="section-title">&#128266; 声量评估</div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                <div style="background: {volume_color}20; padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 2em; color: {volume_color}; font-weight: bold;">{volume_level}</div>
                    <div style="color: #666; margin-top: 5px;">整体声量级别</div>
                </div>
                <div style="background: #f6ffed; padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 1.8em; color: #52c41a; font-weight: bold;">{self._format_number(count)}</div>
                    <div style="color: #666; margin-top: 5px;">内容数量</div>
                </div>
                <div style="background: #e6f7ff; padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 1.8em; color: #1890ff; font-weight: bold;">{self._format_number(total_likes)}</div>
                    <div style="color: #666; margin-top: 5px;">总互动量(点赞)</div>
                </div>
            </div>
            <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 12px;">
                <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128200; 声量分析</div>
                <p style="color: #666; line-height: 1.6;">
                    本话题共产生 {self._format_number(total_likes)} 次点赞、{self._format_number(total_comments)} 条评论，
                    平均每篇内容获得 {int(total_likes/max(count,1))} 点赞，声量{volume_level.lower()}。
                    {f'预估总曝光量达 {self._format_number(total_views)} 次。' if total_views > 0 else ''}
                </p>
            </div>
        </div>
        '''
        return html

    def _generate_keyword_section(self) -> str:
        """关键词分析专属模块"""
        # 提取更多关键词信息
        hot_words = self._extract_hot_words()
        related_keywords = self._extract_related_keywords()

        html = '''
        <div class="section">
            <div class="section-title">&#128270; 关键词深度分析</div>
        '''

        # 核心关键词列表
        if hot_words:
            html += '''
            <div style="margin-bottom: 20px;">
                <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#127941; 核心关键词 TOP10</div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            '''
            for i, (word, count) in enumerate(hot_words[:10]):
                size = min(5, max(1, int(count / max(hot_words[0][1], 1) * 5)))
                sizes = {1: '12', 2: '14', 3: '16', 4: '18', 5: '20'}
                tags = ['', 'secondary', 'primary', 'success', 'warning', 'danger']
                colors = ['#666', '#666', '#52c41a', '#52c41a', '#faad14', '#f5222d']
                color = colors[size]
                html += f'''
                <span style="padding: 6px 12px; background: #f6ffed; color: {color};
                    border-radius: 16px; font-size: {sizes[size]}px; font-weight: 500;">
                    {i+1}. {word} ({count})
                </span>
                '''
            html += '</div></div>'

        # 关联关键词
        if related_keywords:
            html += '''
            <div>
                <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128279; 关联关键词</div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            '''
            for kw in related_keywords[:15]:
                html += f'''
                <span style="padding: 4px 10px; background: #e6f7ff; color: #1890ff;
                    border-radius: 12px; font-size: 13px;">{kw}</span>
                '''
            html += '</div></div>'

        html += '</div>'
        return html

    def _generate_hot_topics_section(self) -> str:
        """热门话题专属模块"""
        # 从热点发现中提取话题
        topics = self._extract_hot_topics()

        html = '''
        <div class="section">
            <div class="section-title">&#128165; 热门话题发现</div>
            <div style="display: grid; gap: 15px;">
        '''

        if topics:
            for i, topic in enumerate(topics[:8], 1):
                heat_bars = '&#128293;' * min(5, max(1, topic.get('heat', 3)))
                html += f'''
                <div style="display: flex; align-items: center; gap: 15px; padding: 15px;
                    background: #f8f9fa; border-radius: 12px;">
                    <div style="font-size: 1.3em; font-weight: bold; color: #ff4d4f;">
                        {f'&#129351;' if i == 1 else f'&#129352;' if i == 2 else f'&#129353;' if i == 3 else f'#{i}'}
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #333;">{topic['name']}</div>
                        <div style="font-size: 0.85em; color: #888; margin-top: 3px;">{topic.get('desc', '')}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.2em;">{heat_bars}</div>
                        <div style="font-size: 0.75em; color: #999;">热度 {topic.get('count', 0)}</div>
                    </div>
                </div>
                '''
        else:
            html += '<div style="text-align: center; padding: 30px; color: #999;">暂无足够数据识别热门话题</div>'

        html += '</div></div>'
        return html

    def _generate_viral_spread_section(self) -> str:
        """传播分析专属模块"""
        profile = self.profile
        features = self.features

        # 分析传播特征
        total_shares = profile['totals'].get('shares', 0)
        total_views = profile['totals'].get('views', 0)
        total_likes = profile['totals'].get('likes', 0)

        # 计算传播系数
        spread_factor = total_shares / max(total_views, 1) * 1000 if total_views > 0 else 0

        html = '''
        <div class="section">
            <div class="section-title">&#128260; 传播路径分析</div>
            <div style="display: grid; gap: 20px;">
        '''

        # 传播指标
        html += '''
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
        '''

        metrics = []
        if total_shares > 0:
            metrics.append(('&#128640; 总分享', total_shares))
        if total_views > 0:
            metrics.append(('&#128065; 总曝光', total_views))
        if features.get('has_likes'):
            metrics.append(('&#10084; 总点赞', total_likes))

        for label, value in metrics:
            html += f'''
            <div style="background: #e6fffb; padding: 15px; border-radius: 12px; text-align: center;">
                <div style="font-size: 1.5em; margin-bottom: 5px;">{label}</div>
                <div style="font-size: 1.6em; font-weight: bold; color: #13c2c2;">{self._format_number(value)}</div>
            </div>
            '''

        html += '</div>'

        # 传播特征分析
        if spread_factor > 0.1:
            spread_desc = '传播力强劲，内容具有很强的分享价值'
        elif spread_factor > 0.05:
            spread_desc = '传播力中等，有一定分享属性'
        else:
            spread_desc = '传播力一般，以观看为主'

        html += f'''
        <div style="background: #f0f5ff; padding: 15px; border-radius: 12px;">
            <div style="font-weight: 600; color: #2f54eb; margin-bottom: 10px;">&#128200; 传播特征</div>
            <p style="color: #666; line-height: 1.6;">{spread_desc}</p>
        </div>
        '''

        html += '</div></div>'
        return html

    def _generate_influencer_section(self) -> str:
        """影响力账号专属模块"""
        # 分析热门作者
        authors = self._analyze_authors()

        html = '''
        <div class="section">
            <div class="section-title">&#11088; 影响力账号分析</div>
            <div style="display: grid; gap: 15px;">
        '''

        if authors:
            for i, author in enumerate(authors[:8], 1):
                html += f'''
                <div style="display: flex; align-items: center; gap: 15px; padding: 15px;
                    background: #f9f0ff; border-radius: 12px; border-left: 4px solid #722ed1;">
                    <div style="font-size: 1.5em; color: #722ed1;">
                        {f'&#129351;' if i == 1 else f'&#129352;' if i == 2 else f'&#129353;' if i == 3 else f'#{i}'}
                    </div>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #333;">{author['name']}</div>
                        <div style="font-size: 0.85em; color: #666; margin-top: 3px;">
                            发布 {author.get('post_count', 0)} 篇 · 平均互动 {self._format_number(int(author.get('avg_interact', 0)))}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.2em; font-weight: bold; color: #722ed1;">
                            {self._format_number(author.get('total_interact', 0))}
                        </div>
                        <div style="font-size: 0.75em; color: #999;">总互动</div>
                    </div>
                </div>
                '''
        else:
            html += '<div style="text-align: center; padding: 30px; color: #999;">暂无足够数据分析影响力账号</div>'

        html += '</div></div>'
        return html

    def _generate_audience_section(self) -> str:
        """用户画像专属模块"""
        # 分析评论者特征
        user_patterns = self._analyze_user_patterns()

        html = '''
        <div class="section">
            <div class="section-title">&#128100; 用户画像分析</div>
            <div style="display: grid; gap: 20px;">
        '''

        # 用户行为特征
        if user_patterns:
            html += '''
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            '''

            for pattern in user_patterns[:4]:
                html += f'''
                <div style="background: #e6f7ff; padding: 15px; border-radius: 12px;">
                    <div style="font-size: 1.3em; margin-bottom: 8px;">{pattern['icon']}</div>
                    <div style="font-weight: 600; color: #1890ff;">{pattern['label']}</div>
                    <div style="font-size: 0.9em; color: #666; margin-top: 5px;">{pattern['value']}</div>
                </div>
                '''

            html += '</div>'

        # 活跃用户特征
        html += '''
        <div style="background: #f6ffed; padding: 15px; border-radius: 12px;">
            <div style="font-weight: 600; color: #52c41a; margin-bottom: 10px;">&#128161; 用户特征洞察</div>
            <ul style="margin-left: 20px; color: #666; line-height: 1.8;">
                <li>对相关内容保持较高关注度</li>
                <li>互动参与意愿' + ('较强' if self.profile['totals'].get('comments', 0) > self.profile['count'] * 5 else '一般') + '</li>
                <li>内容消费偏好明确</li>
            </ul>
        </div>
        '''

        html += '</div></div>'
        return html

    def _generate_comparison_section(self) -> str:
        """竞品对比专属模块"""
        html = '''
        <div class="section">
            <div class="section-title">&#128200; 竞品对比分析</div>
            <div style="display: grid; gap: 20px;">
        '''

        # 数据对比表
        profile = self.profile
        features = self.features

        html += '''
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">指标</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #ddd;">本话题</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #ddd;">评估</th>
                    </tr>
                </thead>
                <tbody>
        '''

        rows = [
            ('内容数量', profile['count'], '条'),
        ]

        if features.get('has_likes'):
            rows.append(('总点赞', profile['totals'].get('likes', 0), ''))
        if features.get('has_comments'):
            rows.append(('总评论', profile['totals'].get('comments', 0), ''))
        if features.get('has_views'):
            rows.append(('总曝光', profile['totals'].get('views', 0), ''))

        for label, value, unit in rows:
            assessment = '高' if value > 10000 else '中' if value > 1000 else '低'
            color = '#52c41a' if assessment == '高' else '#faad14' if assessment == '中' else '#999'

            html += f'''
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">{label}</td>
                <td style="padding: 12px; text-align: center; border-bottom: 1px solid #eee; font-weight: 500;">
                    {self._format_number(value)}{unit}
                </td>
                <td style="padding: 12px; text-align: center; border-bottom: 1px solid #eee;">
                    <span style="color: {color}; font-weight: 600;">{assessment}</span>
                </td>
            </tr>
            '''

        html += '''
                </tbody>
            </table>
        </div>
        '''

        # 综合评估
        html += '''
        <div style="background: #f5f5f5; padding: 15px; border-radius: 12px;">
            <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128200; 综合评估</div>
            <p style="color: #666; line-height: 1.6;">
                基于当前数据分析，本话题在市场中的声量和互动表现''' + ('较为突出' if profile['totals'].get('likes', 0) > 5000 else '处于中等水平' if profile['totals'].get('likes', 0) > 1000 else '相对较弱') + '''。
                建议结合竞品维度进一步深入研究。
            </p>
        </div>
        '''

        html += '</div></div>'
        return html

    def _generate_risk_section(self) -> str:
        """舆情风险专属模块"""
        if not self.features.get('has_comment_data'):
            return ''

        sentiment_pct = self._analyze_sentiment()
        negative_pct = sentiment_pct.get('negative', 0)

        # 风险等级
        if negative_pct > 40:
            risk_level = '高危'
            risk_color = '#f5222d'
            risk_desc = '负面评价占比过高，需立即采取应对措施'
        elif negative_pct > 25:
            risk_level = '中危'
            risk_color = '#faad14'
            risk_desc = '负面情绪有所上升，建议密切关注'
        elif negative_pct > 15:
            risk_level = '低危'
            risk_color = '#fa8c16'
            risk_desc = '存在一些负面声音，需适度关注'
        else:
            risk_level = '正常'
            risk_color = '#52c41a'
            risk_desc = '整体舆情健康'

        # 提取负面关键词
        negative_keywords = self._extract_negative_keywords()

        html = f'''
        <div class="section">
            <div class="section-title">&#9888; 舆情风险评估</div>
            <div style="display: grid; gap: 20px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div style="background: {risk_color}20; padding: 20px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 1.2em; color: #666;">风险等级</div>
                        <div style="font-size: 2em; font-weight: bold; color: {risk_color}; margin-top: 5px;">{risk_level}</div>
                    </div>
                    <div style="background: #f6ffed; padding: 20px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 1.2em; color: #666;">正面评价</div>
                        <div style="font-size: 2em; font-weight: bold; color: #52c41a; margin-top: 5px;">{sentiment_pct.get('positive', 0)}%</div>
                    </div>
                    <div style="background: #fff2f0; padding: 20px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 1.2em; color: #666;">负面评价</div>
                        <div style="font-size: 2em; font-weight: bold; color: #f5222d; margin-top: 5px;">{negative_pct}%</div>
                    </div>
                </div>
                <div style="background: #fff2f0; padding: 15px; border-radius: 12px; border-left: 4px solid {risk_color};">
                    <div style="font-weight: 600; color: {risk_color}; margin-bottom: 8px;">&#9888; 风险分析</div>
                    <p style="color: #666; line-height: 1.6;">{risk_desc}</p>
                </div>
        '''

        if negative_keywords:
            html += '''
            <div style="background: #fff; padding: 15px; border-radius: 12px; border: 1px solid #ffccc7;">
                <div style="font-weight: 600; color: #f5222d; margin-bottom: 10px;">&#128204; 负面高频词</div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            '''
            for word, count in negative_keywords[:10]:
                html += f'''
                <span style="padding: 4px 10px; background: #ff4d4f; color: white; border-radius: 12px; font-size: 13px;">
                    {word} ({count})
                </span>
                '''
            html += '</div></div>'

        html += '</div></div>'
        return html

    def _generate_time_trend(self) -> str:
        """生成时间趋势图 (辅助方法)"""
        # 简化版时间趋势展示
        return '''
        <div style="background: #f8f9fa; padding: 15px; border-radius: 12px;">
            <div style="font-weight: 600; color: #333; margin-bottom: 10px;">&#128200; 热度变化趋势</div>
            <p style="color: #666; line-height: 1.6;">基于当前数据分析，话题热度呈现活跃状态，建议持续关注后续变化。</p>
        </div>
        '''

    def _extract_related_keywords(self) -> List[str]:
        """提取关联关键词 (辅助方法)"""
        # 基于热词提取相关词
        hot_words = self._extract_hot_words()
        # 简单返回一些常用关联词，实际可通过更复杂的算法提取
        return [w[0] for w in hot_words[3:]] if len(hot_words) > 3 else []

    def _extract_hot_topics(self) -> List[Dict]:
        """提取热门话题 (辅助方法)"""
        hot_words = self._extract_hot_words()
        topics = []
        for word, count in hot_words[:8]:
            topics.append({
                'name': word,
                'count': count,
                'heat': min(5, max(1, count // max(hot_words[0][1]//5, 1))),
                'desc': f"出现 {count} 次"
            })
        return topics

    def _analyze_authors(self) -> List[Dict]:
        """分析影响力账号 (辅助方法)"""
        author_stats = {}
        for item in self.data:
            author = item.get('nickname', '未知')
            if not author or author == '未知':
                continue

            interact_info = item.get('interact_info', {})
            likes = interact_info.get('likes', 0)
            if isinstance(likes, str):
                likes = int(likes) if likes.isdigit() else 0

            if author not in author_stats:
                author_stats[author] = {
                    'name': author,
                    'post_count': 0,
                    'total_interact': 0,
                    'interacts': []
                }

            author_stats[author]['post_count'] += 1
            author_stats[author]['total_interact'] += likes
            author_stats[author]['interacts'].append(likes)

        for author in author_stats.values():
            count = author['post_count']
            author['avg_interact'] = author['total_interact'] / max(count, 1)

        return sorted(author_stats.values(), key=lambda x: x['total_interact'], reverse=True)

    def _analyze_user_patterns(self) -> List[Dict]:
        """分析用户行为模式 (辅助方法)"""
        # 简化版用户画像
        comments_count = self.profile['totals'].get('comments', 0)
        content_count = self.profile['count']

        patterns = [
            {'icon': '&#128101;', 'label': '互动活跃度', 'value': '高' if comments_count > content_count * 5 else '中' if comments_count > content_count else '低'},
            {'icon': '&#128150;', 'label': '内容偏好', 'value': '积极互动型' if self._analyze_sentiment().get('positive', 0) > 50 else '中性观望型'},
        ]

        return patterns

    def _extract_negative_keywords(self) -> List[Tuple[str, int]]:
        """提取负面关键词 (辅助方法)"""
        negative_words = list(self.sentiment_analyzer.NEGATIVE_WORDS)
        word_counts = {}

        for item in self.data:
            comments = item.get('comments', [])
            for comment in comments:
                content = comment.get('content', '') if isinstance(comment, dict) else str(comment)
                for word in negative_words:
                    if word in content:
                        word_counts[word] = word_counts.get(word, 0) + 1

        return sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

    def generate_html(self) -> str:
        """生成完整HTML报告"""
        platform_name = self.PLATFORM_NAMES.get(self.platform, self.platform)
        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '分析')
        platform_icon = self.PLATFORM_ICONS.get(self.platform, '&#128240;')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        theme = self._get_theme()

        # 根据报告类型和数据特征决定包含哪些模块
        # 这是根据报告类型动态生成不同模块的核心逻辑
        custom_section = self._generate_custom_section_by_type()

        # 基础模块
        executive_summary = self._generate_executive_summary()
        action_plan_section = self._generate_action_plan()
        content_list_section = f'''
        <div class="section">
            <div class="section-title">&#127942; 热门内容排行 TOP 10</div>
            {self._generate_content_list()}
        </div>
        ''' if self.data else ''

        # 舆情分析类报告才包含情感分析模块
        sentiment_section = ''
        comment_analysis_section = ''
        comments_section = ''
        if self.report_type in ['sentiment', 'risk'] and self.features.get('has_comment_data'):
            sentiment_section = self._generate_sentiment_chart()
            comment_analysis_section = self._generate_comment_analysis()
            comments_section = self._generate_comments_section()

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

        <!-- 3. 报告类型专属模块 -->
        {custom_section}

        <!-- 4. 情感分析可视化 (仅限舆情类报告) -->
        {sentiment_section}

        <!-- 5. 热门内容排行 -->
        {content_list_section}

        <!-- 6. 热词综合分析 -->
        <div class="section">
            <div class="section-title">&#9731; 热门讨论词云</div>
            {self._generate_hot_words()}
        </div>

        <!-- 7. 评论深度分析 (仅限舆情类报告) -->
        {comment_analysis_section}

        <!-- 8. 舆情洞察与建议 -->
        <div class="section">
            <div class="section-title">&#128161; 舆情洞察与建议</div>
            {self._generate_insights()}
        </div>

        <!-- 9. 处理建议与行动方案 -->
        {action_plan_section}

        <!-- 10. 代表性用户评论 (仅限舆情类报告) -->
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


# =========================
# 多平台合并报告生成器
# =========================

class MultiPlatformReportGenerator:
    """多平台合并报告生成器 - 合并多个平台数据生成统一报告"""

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
        'xhs': '📕',
        'dy': '🎵',
        'ks': '📱',
        'bili': '📺',
        'wb': '🌐',
        'tieba': '📌',
        'zhihu': '💡',
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
        platform_data: Dict[str, List[Dict]],
        keywords: str,
        output_path: str = "reports",
        report_type: str = "sentiment"
    ):
        """
        初始化多平台报告生成器

        Args:
            platform_data: {平台代码: 数据列表} 的字典
            keywords: 搜索关键词
            output_path: 输出路径
            report_type: 报告类型
        """
        self.platform_data = platform_data
        self.keywords = keywords
        self.output_path = output_path
        self.report_type = report_type

        # 合并所有平台数据用于分析
        self.all_data = []
        self.platform_stats = {}
        self._merge_platform_data()

        # 使用合并后的数据进行特征分析
        self.analyzer = DataAnalyzer(self.all_data)
        self.profile = self.analyzer.get_data_profile()
        self.features = self.profile['features']

        # 缓存分析结果
        self.sentiment_stats = {'positive': 0, 'negative': 0, 'neutral': 0}
        self.hot_words = []

    def _merge_platform_data(self):
        """合并多平台数据并统计各平台数据量"""
        for platform, data in self.platform_data.items():
            if data:
                # 为每条数据添加平台标记
                for item in data:
                    item['_platform'] = platform
                self.all_data.extend(data)
                self.platform_stats[platform] = len(data)

    def _analyze_sentiment(self) -> Dict:
        """分析所有数据的情感分布"""
        sentiments = {'positive': 0, 'negative': 0, 'neutral': 0}

        for item in self.all_data:
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

        self.sentiment_stats = sentiments
        total = sum(sentiments.values())
        if total > 0:
            return {k: round(v / total * 100, 1) for k, v in sentiments.items()}
        return sentiments

    def _extract_hot_words(self) -> List[Tuple[str, int]]:
        """提取所有数据的热词"""
        all_text = []

        for item in self.all_data:
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
        """获取所有平台的代表性评论"""
        comments = []

        for item in self.all_data:
            platform = item.get('_platform', '')
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
                        'platform': platform,
                        'has_intent': SentimentAnalyzer.has_purchase_intent(content)
                    })

        comments.sort(key=lambda x: (x['has_intent'], x['like_count']), reverse=True)
        return comments[:15]

    def _format_number(self, num: int) -> str:
        if num >= 10000:
            return f"{num / 10000:.1f}万"
        return str(num)

    def _get_platform_breakdown(self) -> str:
        """生成各平台数据分布HTML"""
        html = '<div class="platform-breakdown" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">'

        total = sum(self.platform_stats.values())
        for platform, count in sorted(self.platform_stats.items(), key=lambda x: x[1], reverse=True):
            platform_name = self.PLATFORM_NAMES.get(platform, platform)
            icon = self.PLATFORM_ICONS.get(platform, '📊')
            percentage = round(count / total * 100, 1) if total > 0 else 0

            html += f'''
            <div style="background: rgba(102,126,234,0.1); padding: 15px; border-radius: 12px; text-align: center;">
                <div style="font-size: 1.5em; margin-bottom: 5px;">{icon}</div>
                <div style="font-weight: 600; color: #333;">{platform_name}</div>
                <div style="font-size: 0.9em; color: #666; margin-top: 5px;">{count}条 ({percentage}%)</div>
            </div>
            '''

        html += '</div>'
        return html

    def _generate_metric_cards(self) -> str:
        """生成多平台的综合指标卡片"""
        cards = []
        profile = self.profile
        totals = profile['totals']

        # 基础卡片：内容数
        cards.append({
            'icon': '📊',
            'value': str(len(self.all_data)),
            'label': '分析内容总数'
        })

        # 统计平台数
        cards.append({
            'icon': '🌐',
            'value': str(len(self.platform_data)),
            'label': '覆盖平台数'
        })

        # 根据特征添加卡片
        if self.features.get('has_likes'):
            cards.append({
                'icon': '❤️',
                'value': self._format_number(totals['likes']),
                'label': '总点赞数'
            })

        if self.features.get('has_comments'):
            cards.append({
                'icon': '💬',
                'value': self._format_number(totals['comments']),
                'label': '评论总数'
            })

        if self.features.get('has_views'):
            cards.append({
                'icon': '👁️',
                'value': self._format_number(totals['views']),
                'label': '总播放量'
            })

        if self.features.get('has_shares'):
            cards.append({
                'icon': '🚀',
                'value': self._format_number(totals['shares']),
                'label': '分享次数'
            })

        # 如果有评论数据，添加情感分析卡片
        if self.features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            cards.append({
                'icon': '👍',
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

    def _generate_platform_content_list(self) -> str:
        """生成各平台热门内容列表"""
        items = []

        # 按平台分类展示TOP3
        for platform, data in self.platform_data.items():
            platform_name = self.PLATFORM_NAMES.get(platform, platform)
            for i, item in enumerate(data[:3], 1):  # 每个平台取TOP3
                interact = item.get('interact_info', {})

                # 获取标题
                title = item.get('title', item.get('desc', item.get('caption', '无标题')))[:50]

                # 获取作者
                author = item.get('nickname', item.get('author', '匿名'))[:10]

                # 构建统计信息
                stats = []
                likes = interact.get('like_count', 0) or interact.get('digg_count', 0) or 0
                if likes:
                    stats.append(f"❤️ {self._format_number(likes)}")

                views = interact.get('view_count', 0) or interact.get('play_count', 0) or 0
                if views:
                    stats.append(f"👁️ {self._format_number(views)}")

                comments = interact.get('comment_count', 0) or interact.get('comments_count', 0) or 0
                if comments:
                    stats.append(f"💬 {self._format_number(comments)}")

                items.append({
                    'platform': platform_name,
                    'platform_color': '#667eea',
                    'rank': i,
                    'title': title,
                    'author': author,
                    'stats': ' | '.join(stats) if stats else ''
                })

        html = '<div class="content-list">'
        for item in items:
            html += f'''
            <div class="content-item">
                <div class="content-rank" style="background: {item['platform_color']}; color: white; font-size: 0.7em;">
                    {item['platform'][:2]}\n#{item['rank']}
                </div>
                <div class="content-info">
                    <div class="content-title">{item['title']}</div>
                    <div class="content-meta">👤 {item['author']}</div>
                </div>
                <div class="content-stats">{item['stats']}</div>
            </div>
            '''
        html += '</div>'
        return html

    def _generate_sentiment_chart(self) -> str:
        """生成情感分析图表"""
        if not self.features.get('has_comment_data', False) and len(self.all_data) < 5:
            return ''

        sentiment_pct = self._analyze_sentiment()

        return f'''
        <div class="section">
            <div class="section-title">📊 情感分析分布</div>
            <div class="chart-container" id="sentimentChart" style="height: 280px;"></div>
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
            html += f'<span class="word-tag size-{size_class}" style="background: {color}20; color: {color};">{word}</span>'
        html += '</div>'
        return html

    def _generate_insights(self) -> str:
        """生成多平台数据洞察"""
        insights = []
        profile = self.profile

        # 数据覆盖度洞察
        if len(self.platform_data) >= 3:
            insights.append({
                'icon': '🌐',
                'title': '多平台声量覆盖',
                'content': f'共覆盖{len(self.platform_data)}个平台，采集{len(self.all_data)}条内容，数据覆盖全面。'
            })

        # 平台分布洞察
        max_platform = max(self.platform_stats.items(), key=lambda x: x[1])
        max_platform_name = self.PLATFORM_NAMES.get(max_platform[0], max_platform[0])
        insights.append({
            'icon': '📈',
            'title': '主要声量来源',
            'content': f'{max_platform_name}贡献了最多的讨论内容（{max_platform[1]}条），是该话题的主要讨论阵地。'
        })

        # 互动数据洞察
        if self.features.get('has_likes') and profile['averages']['likes'] > 1000:
            insights.append({
                'icon': '🔥',
                'title': '高互动内容',
                'content': f'平均每条内容获得{profile["averages"]["likes"]:.0f}点赞，整体热度较高。'
            })

        # 情感洞察
        if self.features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            if sentiment_pct.get('positive', 0) > 60:
                insights.append({
                    'icon': '👍',
                    'title': '口碑良好',
                    'content': f'{sentiment_pct["positive"]}%的评论呈正面倾向，跨平台用户满意度较高。'
                })
            elif sentiment_pct.get('negative', 0) > 30:
                insights.append({
                    'icon': '⚠️',
                    'title': '需要关注',
                    'content': f'{sentiment_pct["negative"]}%的评论呈负面倾向，建议关注用户反馈。'
                })

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

    def _generate_comments_section(self) -> str:
        """生成代表性评论区域"""
        if not self.features.get('has_comment_data', False):
            return ''

        comments = self._get_representative_comments()
        if not comments:
            return ''

        html = '''
        <div class="section">
            <div class="section-title">💬 代表性用户评论</div>
            <div class="comment-list">
        '''

        sentiment_labels = {
            'positive': ('正面', '#52c41a'),
            'negative': ('负面', '#f5222d'),
            'neutral': ('中性', '#faad14')
        }

        # 按平台分组展示
        platform_groups = {}
        for comment in comments:
            platform = comment.get('platform', 'unknown')
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(comment)

        for platform, platform_comments in list(platform_groups.items())[:3]:  # 最多显示3个平台
            platform_name = self.PLATFORM_NAMES.get(platform, platform)
            icon = self.PLATFORM_ICONS.get(platform, '📊')

            html += f'<div style="margin-bottom: 15px; padding: 10px; background: rgba(102,126,234,0.05); border-radius: 8px;">'
            html += f'<div style="font-weight: 600; color: #667eea; margin-bottom: 10px;">{icon} {platform_name}</div>'

            for comment in platform_comments[:3]:  # 每个平台最多3条
                sentiment = comment['sentiment']
                label, color = sentiment_labels.get(sentiment, ('中性', '#faad14'))

                intent_tag = ' 🛒 购买意向' if comment.get('has_intent') else ''

                html += f'''
                <div class="comment-item" style="border-left-color: {color}; margin-bottom: 10px;">
                    <div class="comment-header">
                        <span class="comment-user">👤 {comment.get('nickname', '匿名用户')}</span>
                        <span class="comment-senti" style="background: {color}20; color: {color};">{label}{intent_tag}</span>
                    </div>
                    <div class="comment-content">{comment['content'][:150]}...</div>
                    <div class="comment-footer">
                        <span>❤️ {comment.get('like_count', 0)}</span>
                    </div>
                </div>
                '''

            html += '</div>'

        html += '</div></div>'
        return html

    def generate_html(self) -> str:
        """生成多平台合并的HTML报告"""
        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '舆情分析')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 生成各模块
        platform_breakdown = self._get_platform_breakdown()
        metric_cards = self._generate_metric_cards()
        sentiment_chart = self._generate_sentiment_chart() if self.report_type in ['sentiment', 'risk'] else ''
        content_list = self._generate_platform_content_list()
        hot_words = self._generate_hot_words()
        insights = self._generate_insights()
        comments_section = self._generate_comments_section()

        # 平台列表
        platform_names = [self.PLATFORM_NAMES.get(p, p) for p in self.platform_data.keys()]

        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>多平台_{self.keywords}_{report_type_name}报告</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            border-left: 4px solid #667eea;
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
        }}
        .metric-icon {{ font-size: 2em; margin-bottom: 8px; }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            width: 50px;
            height: 50px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.75em;
            margin-right: 12px;
            background: #f0f0f0;
            color: #666;
            flex-shrink: 0;
            text-align: center;
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
            cursor: pointer;
        }}
        .word-tag.size-1 {{ font-size: 0.85em; opacity: 0.7; }}
        .word-tag.size-2 {{ font-size: 0.95em; opacity: 0.85; }}
        .word-tag.size-3 {{ font-size: 1.1em; }}
        .word-tag.size-4 {{ font-size: 1.25em; box-shadow: 0 3px 10px rgba(0,0,0,0.1); }}
        .word-tag.size-5 {{ font-size: 1.5em; box-shadow: 0 4px 15px rgba(0,0,0,0.15); }}

        .insight-list {{ display: grid; gap: 15px; }}
        .insight-item {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            border-radius: 0 12px 12px 0;
        }}
        .insight-title {{
            color: #667eea;
            font-weight: 600;
            margin-bottom: 6px;
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
        .comment-user {{ color: #667eea; font-weight: 500; }}
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

        .chart-container {{ width: 100%; height: 280px; }}

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
            <h1>多平台 {report_type_name}报告</h1>
            <p class="subtitle">关键词：「{self.keywords}」</p>
            <p class="meta">覆盖平台：{', '.join(platform_names)} | 生成时间：{timestamp} | 总样本：{len(self.all_data)}条</p>
        </header>

        <!-- 1. 平台分布概览 -->
        <div class="section">
            <div class="section-title">🌐 平台数据分布</div>
            {platform_breakdown}
        </div>

        <!-- 2. 核心数据概览 -->
        <div class="section">
            <div class="section-title">📊 核心数据概览</div>
            {metric_cards}
        </div>

        <!-- 3. 情感分析 -->
        {sentiment_chart}

        <!-- 4. 热门内容排行 -->
        <div class="section">
            <div class="section-title">🏆 各平台热门内容 TOP 3</div>
            {content_list}
        </div>

        <!-- 5. 热词分析 -->
        <div class="section">
            <div class="section-title">☁️ 热门讨论词云</div>
            {hot_words}
        </div>

        <!-- 6. 舆情洞察 -->
        <div class="section">
            <div class="section-title">💡 多平台舆情洞察</div>
            {insights}
        </div>

        <!-- 7. 代表性评论 -->
        {comments_section}

        <footer class="footer">
            <p>📊 多平台智能分析报告 | 生成时间：{timestamp}</p>
        </footer>
    </div>
</body>
</html>'''

    def save_report(self) -> str:
        """保存报告"""
        os.makedirs(self.output_path, exist_ok=True)

        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '舆情分析')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = re.sub(r'[\\/*?:"<>|]', "_", self.keywords)[:30]
        filename = f"多平台_{safe_keyword}_{report_type_name}_{timestamp}.html"
        filepath = os.path.join(self.output_path, filename)

        html_content = self.generate_html()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return filepath

    def get_console_summary(self) -> str:
        """获取控制台摘要"""
        total_items = len(self.all_data)
        platform_names = [self.PLATFORM_NAMES.get(p, p) for p in self.platform_data.keys()]

        summary_parts = [
            f"📊 多平台「{self.keywords}」舆情分析报告",
            f"🌐 覆盖平台：{', '.join(platform_names)}",
            f"📈 数据概览：共采集 {total_items} 条内容",
        ]

        # 平台分布
        for platform, count in sorted(self.platform_stats.items(), key=lambda x: x[1], reverse=True):
            platform_name = self.PLATFORM_NAMES.get(platform, platform)
            summary_parts.append(f"   • {platform_name}: {count}条")

        # 互动数据
        if self.features.get('has_likes'):
            summary_parts.append(f"❤️ 总点赞: {self._format_number(self.profile['totals']['likes'])}")
        if self.features.get('has_comments'):
            summary_parts.append(f"💬 总评论: {self._format_number(self.profile['totals']['comments'])}")
        if self.features.get('has_views'):
            summary_parts.append(f"👁️ 总播放: {self._format_number(self.profile['totals']['views'])}")

        # 情感分析
        if self.features.get('has_comment_data'):
            sentiment_pct = self._analyze_sentiment()
            summary_parts.append(f"💭 情感分布：正面 {sentiment_pct.get('positive', 0)}% | 负面 {sentiment_pct.get('negative', 0)}% | 中性 {sentiment_pct.get('neutral', 0)}%")

        return "\n".join(summary_parts)


def generate_multi_platform_report(
    platform_data: Dict[str, List[Dict]],
    keywords: str,
    output_path: str = "reports",
    report_type: str = "sentiment"
) -> Tuple[str, str, str]:
    """
    生成多平台合并报告主函数

    Args:
        platform_data: {平台代码: 数据列表} 的字典
        keywords: 关键词
        output_path: 输出路径
        report_type: 报告类型

    Returns:
        (report_path, console_summary, html_content)
    """
    os.makedirs(output_path, exist_ok=True)

    generator = MultiPlatformReportGenerator(platform_data, keywords, output_path, report_type)

    # 保存报告
    report_path = generator.save_report()
    abs_path = os.path.abspath(report_path)

    # 生成摘要
    summary = generator.get_console_summary()

    return abs_path, summary, generator.generate_html()

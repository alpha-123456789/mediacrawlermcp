# -*- coding: utf-8 -*-
"""
AI 驱动报告生成器 v4.0
将数据特征传递给 AI，由 AI 动态生成报告结构
支持自动字段识别，无需手动配置平台字段映射
"""

import json
from typing import Any, Dict, List
import jieba
import jieba.analyse

from auto_field_detector import AutoFieldDetector, get_standardized_value


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

    @classmethod
    def analyze(cls, text: str):
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


class DataProfiler:
    """数据特征分析器 - 使用自动字段识别，无需硬编码平台映射"""

    def __init__(self, data: List[Dict]):
        self.data = data
        # 自动识别字段映射
        self.detector = AutoFieldDetector()
        self.field_map = self.detector.detect_from_data_list(data)

    def _extract_competitors_from_content(self) -> Dict:
        """
        从帖子内容和评论中提取竞品/相关品牌
        返回：{竞品名: {"mention_count": 提及次数, "contexts": [上下文列表]}}
        """
        import re
        from collections import Counter

        # 所有文本内容
        all_texts = []

        # 收集所有文本
        for item in self.data:
            # 帖子内容
            content = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            if content:
                all_texts.append(content)

            # 评论内容
            for comment in item.get('comments', []):
                if isinstance(comment, dict):
                    comment_content = comment.get('content', '')
                    if comment_content:
                        all_texts.append(comment_content)

        # 合并所有文本用于分析
        all_text_combined = ' '.join(all_texts)

        if not all_text_combined:
            return {}

        # 常见品牌/竞品词库（用于匹配）
        common_brands = [
            # 母婴/教育
            '小小优趣', '洪恩', '贝乐虎', '叽里呱啦', '凯叔', '喜马拉雅', '叫叫',
            '斑马', '小火花', '豌豆思维', '火花思维', '猿辅导', '作业帮',
            # 美妆
            '花西子', '橘朵', '完美日记', 'colorkey', '珂拉琪', '3ce', 'mac', '雅诗兰黛',
            '兰蔻', 'ysl', '迪奥', '香奈儿', '毛戈平', '卡姿兰', '美宝莲',
            # 手机/数码
            '华为', '小米', 'oppo', 'vivo', '一加', '荣耀', '三星', '苹果', 'iphone',
            '红米', 'realme', 'iqoo', '魅族', '努比亚',
            # 汽车
            '特斯拉', '比亚迪', '蔚来', '小鹏', '理想', '问界', '极氪', '零跑',
            '埃安', '五菱', '长安', '吉利', '奇瑞', '长城', '宝马', '奔驰', '奥迪',
            # 快消
            '可口可乐', '百事', '农夫山泉', '元气森林', '旺仔', '李子柒',
            # 电商/平台
            '淘宝', '京东', '拼多多', '抖音', '快手', '小红书', '得物', '唯品会',
            # 游戏
            '原神', '王者', '吃鸡', '和平精英', '英雄联盟', '蛋仔派对',
            # 外卖/本地
            '美团', '饿了么', '滴滴', '高德', '百度',
        ]

        # 找出来文本中实际出现的品牌
        found_brands = {}
        for brand in common_brands:
            if brand in all_text_combined:
                count = all_text_combined.count(brand)
                if count >= 1:  # 至少出现1次
                    found_brands[brand] = count

        # 使用正则提取英文品牌（如 iPhone、Tesla 等）
        english_brands = re.findall(r'\b[A-Za-z]+\d*\b', all_text_combined)
        english_brands = [b.lower() for b in english_brands if len(b) > 2]
        english_freq = Counter(english_brands)

        # 常见英文品牌映射
        english_brand_map = {
            'iphone': '苹果', 'apple': '苹果', 'ios': '苹果系统',
            'huawei': '华为', 'xiaomi': '小米', 'oppo': 'OPPO', 'vivo': 'VIVO',
            'tesla': '特斯拉', 'bmw': '宝马', 'benz': '奔驰', 'audi': '奥迪',
            'mac': '魅可', 'nike': '耐克', 'adidas': '阿迪达斯',
            'starbucks': '星巴克', 'kfc': '肯德基', 'mcdonalds': '麦当劳',
        }

        for eng, cn in english_brand_map.items():
            if eng in english_freq and cn not in found_brands:
                found_brands[cn] = english_freq[eng]

        # 提取竞品上下文（用户在什么语境下提到竞品）
        competitor_contexts = {}
        for brand, count in found_brands.items():
            contexts = []
            for text in all_texts:
                if brand in text:
                    # 找到提及位置，提取上下文
                    idx = text.find(brand)
                    start = max(0, idx - 20)
                    end = min(len(text), idx + len(brand) + 20)
                    context = text[start:end].strip()
                    if len(context) > 10:
                        contexts.append(context)
            competitor_contexts[brand] = {
                "mention_count": count,
                "contexts": contexts[:5]  # 最多保留5条上下文
            }

        # 按提及次数排序
        sorted_competitors = dict(sorted(
            competitor_contexts.items(),
            key=lambda x: x[1]["mention_count"],
            reverse=True
        ))

        return sorted_competitors

    def analyze(self) -> Dict:
        """生成完整的数据画像"""
        if not self.data:
            return {"error": "没有数据"}

        # 基础统计
        total_items = len(self.data)

        # 分析数据结构（使用自动识别的映射）
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
            "样例数据": self._get_samples(),
            "_field_map": self.field_map  # 内部使用，用于调试
        }

    def _detect_fields(self) -> Dict[str, bool]:
        """检测数据中包含哪些字段（基于自动识别的映射）"""
        # 使用自动识别的字段映射来判断
        return {
            "点赞": "likes" in self.field_map,
            "评论数": "comments" in self.field_map,
            "评论内容": any(item.get('comments') for item in self.data[:5]),
            "播放/阅读": "views" in self.field_map,
            "分享/转发": "shares" in self.field_map,
            "收藏": "favorites" in self.field_map,
            "投币": "coins" in self.field_map,
            "标题": any(item.get('title') or item.get('desc') or item.get('caption')
                      for item in self.data[:3]),
            "作者": any(item.get('nickname') or item.get('author')
                      for item in self.data[:3]),
            "时间": any(item.get('create_time') or item.get('created_at')
                      for item in self.data[:3])
        }

    def _get_standardized_value(self, item: Dict, standard_field: str) -> int:
        """获取标准化字段值"""
        return get_standardized_value(item, self.field_map, standard_field)

    def _calculate_stats(self) -> Dict:
        """计算数值统计"""
        stats = {"likes": 0, "comments": 0, "views": 0, "shares": 0}

        for item in self.data:
            stats["likes"] += self._get_standardized_value(item, "likes")
            stats["comments"] += self._get_standardized_value(item, "comments")
            stats["views"] += self._get_standardized_value(item, "views")
            stats["shares"] += self._get_standardized_value(item, "shares")

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
        # 视频观看型：有播放量数据
        if "views" in self.field_map:
            return "视频观看型：重点是播放量、完播率、弹幕互动"
        # 社交传播型：有转发数据
        elif "shares" in self.field_map:
            return "社交传播型：重点是转发、点赞、讨论热度"
        # 内容讨论型：有评论数据
        elif "comments" in self.field_map or any(item.get('comments') for item in self.data[:3]):
            return "内容讨论型：重点是评论质量、用户反馈"
        else:
            return "基础展示型：重点是内容曝光、用户触达"

    def _detect_content_type(self) -> str:
        """检测内容类型"""
        sample_text = ""
        for item in self.data[:3]:
            sample_text += item.get('desc', '') or item.get('title', '') or item.get('caption', '')

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
            max_values["likes"] = max(max_values["likes"], self._get_standardized_value(item, "likes"))
            max_values["comments"] = max(max_values["comments"], self._get_standardized_value(item, "comments"))
            max_values["views"] = max(max_values["views"], self._get_standardized_value(item, "views"))

        return max_values

    def _get_samples(self) -> List[Dict]:
        """获取样例数据摘要"""
        samples = []
        for item in self.data[:3]:
            if isinstance(item, dict):
                interact = item.get('interact_info', {})
                # 显示自动识别的映射关系
                mapped = {}
                for std_field, actual_field in self.field_map.items():
                    if actual_field in interact:
                        mapped[std_field] = interact[actual_field]

                samples.append({
                    "title": (item.get('title') or item.get('desc', '') or item.get('caption', ''))[:50],
                    "author": item.get('nickname', item.get('author', '未知')),
                    "interact": mapped or {k: v for k, v in interact.items() if v}
                })
        return samples

    def _extract_hot_words(self) -> List:
        """提取热词"""
        all_text = []
        for item in self.data:
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            if text:
                all_text.append(text)
            for comment in item.get('comments', []):
                content = comment.get('content', '') if isinstance(comment, dict) else str(comment)
                if content:
                    all_text.append(content)

        if not all_text:
            return []

        full_text = ' '.join(all_text)
        keywords = jieba.analyse.extract_tags(full_text, topK=20, withWeight=True)
        # 返回对象数组格式，便于 ECharts 直接使用
        return [{"name": word, "value": int(weight * 1000)} for word, weight in keywords]

    def get_detailed_data(self) -> Dict:
        """获取详细的真实数据，用于 AI 生成报告"""
        # 1. 热门内容 TOP 10
        top_contents = []
        for item in self.data[:10]:
            if isinstance(item, dict):
                interact = item.get('interact_info', {})
                # 计算互动总分用于排序展示
                score = (
                    self._get_standardized_value(item, "likes") +
                    self._get_standardized_value(item, "comments") * 2 +
                    self._get_standardized_value(item, "views") * 0.1
                )
                top_contents.append({
                    "title": (item.get('title') or item.get('desc', '') or item.get('caption', ''))[:100],
                    "author": item.get('nickname', item.get('author', '未知')),
                    "likes": self._get_standardized_value(item, "likes"),
                    "comments": self._get_standardized_value(item, "comments"),
                    "views": self._get_standardized_value(item, "views"),
                    "shares": self._get_standardized_value(item, "shares"),
                    "score": round(score, 1),
                    "comment_count": len(item.get('comments', []))
                })

        # 2. 代表性评论
        representative_comments = []
        for item in self.data:
            for comment in item.get('comments', []):
                if isinstance(comment, dict):
                    content = comment.get('content', '')
                    if len(content) > 10:  # 过滤太短的评论
                        sentiment, score = SentimentAnalyzer.analyze(content)
                        representative_comments.append({
                            "content": content[:300],  # 限制长度
                            "author": comment.get('comment_nickname', comment.get('user_nickname', '匿名')),
                            "likes": comment.get('like_count', 0),
                            "sentiment": sentiment,
                            "sentiment_score": round(score, 2)
                        })

        # 按点赞数排序，取前 15 条
        representative_comments.sort(key=lambda x: x['likes'], reverse=True)
        representative_comments = representative_comments[:15]

        # 3. 情感分布统计
        sentiment_stats = {'positive': 0, 'negative': 0, 'neutral': 0}
        for item in self.data:
            # 分析内容情感
            text = item.get('desc', '') or item.get('title', '') or item.get('caption', '')
            if text:
                s, _ = SentimentAnalyzer.analyze(text)
                sentiment_stats[s] += 1
            # 分析评论情感
            for comment in item.get('comments', []):
                if isinstance(comment, dict):
                    content = comment.get('content', '')
                    if content:
                        s, _ = SentimentAnalyzer.analyze(content)
                        sentiment_stats[s] += 1

        total = sum(sentiment_stats.values())
        if total > 0:
            # 转换为 ECharts 饼图友好的格式
            sentiment_distribution = [
                {"value": round(v / total * 100, 1), "name": {"positive": "正面", "negative": "负面", "neutral": "中性"}[k]}
                for k, v in sentiment_stats.items() if v > 0
            ]
        else:
            sentiment_distribution = []

        # 4. 正面/负面典型案例
        positive_examples = [c for c in representative_comments if c['sentiment'] == 'positive'][:5]
        negative_examples = [c for c in representative_comments if c['sentiment'] == 'negative'][:5]
        # 如果没有，从评论里再找
        if not positive_examples:
            for item in self.data:
                for comment in item.get('comments', []):
                    if isinstance(comment, dict):
                        content = comment.get('content', '')
                        sentiment, score = SentimentAnalyzer.analyze(content)
                        if sentiment == 'positive' and len(content) > 15:
                            positive_examples.append({
                                "content": content[:300],
                                "author": comment.get('comment_nickname', '匿名'),
                                "likes": comment.get('like_count', 0),
                                "sentiment": sentiment
                            })
                            if len(positive_examples) >= 5:
                                break
                if len(positive_examples) >= 5:
                    break

        if not negative_examples:
            for item in self.data:
                for comment in item.get('comments', []):
                    if isinstance(comment, dict):
                        content = comment.get('content', '')
                        sentiment, score = SentimentAnalyzer.analyze(content)
                        if sentiment == 'negative' and len(content) > 15:
                            negative_examples.append({
                                "content": content[:300],
                                "author": comment.get('comment_nickname', '匿名'),
                                "likes": comment.get('like_count', 0),
                                "sentiment": sentiment
                            })
                            if len(negative_examples) >= 5:
                                break
                if len(negative_examples) >= 5:
                    break

        return {
            "top_contents": top_contents,
            "representative_comments": representative_comments,
            "sentiment_distribution": sentiment_distribution,
            "positive_examples": positive_examples,
            "negative_examples": negative_examples,
            "hot_words": self._extract_hot_words(),
            "competitors": self._extract_competitors_from_content()
        }


class AIReportPromptBuilder:
    """构建给 AI 的提示词"""

    # 报告类型名称映射
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

    # 报告类型主题色
    REPORT_TYPE_THEMES = {
        'sentiment': '#667eea → #764ba2 (蓝紫色)',
        'trend': '#fa8c16 → #ffc53d (橙黄色)',
        'volume': '#faad14 → #ffd666 (金黄色)',
        'keyword': '#52c41a → #95de64 (绿色)',
        'hot_topics': '#52c41a → #95de64 (绿色)',
        'viral_spread': '#13c2c2 → #5cdbd3 (青色)',
        'influencer': '#722ed1 → #b37feb (紫色)',
        'audience': '#1890ff → #69c0ff (蓝色)',
        'comparison': '#2f4554 → #546570 (靛青色)',
        'risk': '#f5222d → #ff7875 (红色)'
    }

    def __init__(self, platform: str, keywords: str, profile: Dict, report_type: str = 'sentiment'):
        self.platform = platform
        self.keywords = keywords
        self.profile = profile
        self.report_type = report_type

    def _get_module4_content(self) -> str:
        """根据报告类型生成模块4的内容"""
        detailed_data = self.profile.get("详细数据", {})
        sentiment_dist = json.dumps(detailed_data.get("sentiment_distribution", []), ensure_ascii=False)

        modules = {
            'sentiment': f"""### 4. 情感分析可视化（**最重要**）
- 必须使用 ECharts 饼图，基于提供的 sentiment_distribution 数据
- 饼图中每个扇区必须有明确的数据标签，例如"正面 65%"
- 图表下方用文字总结情感趋势
- 结合评论热度（点赞数）分析情感权重
- 关联帖子互动数据分析整体舆论走向""",

            'trend': f"""### 4. 热度趋势分析（**最重要**）
- 使用 ECharts 折线图或柱状图展示热度变化趋势
- 基于帖子发布时间（如果有）绘制时间序列图
- 标注热度高峰点，分析热点事件
- 下方文字总结：话题热度处于什么阶段（上升期/爆发期/衰退期）
- 预测未来趋势走向
- 如果有情感数据可辅助分析：{sentiment_dist}""",

            'volume': f"""### 4. 声量分布分析（**最重要**）
- 使用 ECharts 柱状图或雷达图展示声量指标
- 声量维度包括：内容数量、总点赞、总评论、总曝光
- 对比各项指标的占比分布
- 下方文字总结：整体声量级别（高/中/低）
- 分析哪些平台/渠道贡献了主要声量
- 情感分布参考（如有评论数据）：{sentiment_dist}""",

            'keyword': f"""### 4. 关键词关联分析（**最重要**）
- 使用 ECharts 关系图或桑基图展示关键词关联
- 核心关键词居中，关联词围绕分布
- 用线条粗细表示关联强度
- 下方文字总结：核心关键词是什么，与哪些词关联最紧密
- 分析关键词的情感倾向（正面/负面词有哪些）
- 情感分布参考：{sentiment_dist}""",

            'hot_topics': f"""### 4. 话题热度排行（**最重要**）
- 使用 ECharts 横向柱状图展示 TOP 10 热门话题
- 每个话题标注热度值和出现频次
- 用颜色区分话题类型（产品/服务/活动/人物等）
- 下方文字总结：最热门的话题是什么，为什么火
- 分析话题之间的关联和演变
- 情感分布参考：{sentiment_dist}""",

            'viral_spread': f"""### 4. 传播路径分析（**最重要**）
- 使用 ECharts 桑基图或关系图展示传播链路
- 分析内容从发布到扩散的传播节点
- 标注关键传播者（点赞/分享高的用户）
- 下方文字总结：传播模式是什么（病毒式/圈层式/线性式）
- 传播关键节点和加速因素分析
- 情感在传播过程中的变化：{sentiment_dist}""",

            'influencer': f"""### 4. 影响力账号排行（**最重要**）
- 使用 ECharts 横向柱状图展示 TOP 10 影响力账号
- 排序依据：总互动量（点赞+评论+分享）
- 每个账号展示：发布内容数、平均互动、粉丝影响力
- 下方文字总结：谁是核心意见领袖，有什么特征
- 分析头部账号的内容策略和互动特点
- 这些账号的评论区情感倾向：{sentiment_dist}""",

            'audience': f"""### 4. 用户画像分析（**最重要**）
- 使用 ECharts 饼图或雷达图展示用户特征分布
- 维度包括：互动活跃度、评论情感倾向、参与深度
- 用不同颜色区分用户类型（积极/观望/负面）
- 下方文字总结：核心用户群体特征是什么
- 分析用户行为模式和消费偏好
- 用户情感分布：{sentiment_dist}""",

            'comparison': f"""### 4. 竞品对比雷达图（**最重要**）
- 使用 ECharts 雷达图展示多维度对比
- 维度包括：声量、互动率、正面评价率、传播力、关注度
- 被分析对象 vs 竞品进行直观对比
- 下方文字总结：各维度的优劣势分析
- 明确给出竞争建议和改进方向
- 情感对比数据：{sentiment_dist}""",

            'risk': f"""### 4. 舆情风险评估可视化（**最重要**）
- 使用 ECharts 仪表盘或饼图展示风险等级
- 风险维度：负面评价占比、负面词频、传播速度、影响范围
- 用红色系突出显示高风险区域
- 下方文字总结：当前风险等级（高危/中危/低危/正常）
- 分析风险来源和可能的影响
- 情感分布（重点关注负面）：{sentiment_dist}"""
        }

        return modules.get(self.report_type, modules['sentiment'])

    def _get_report_modules(self) -> str:
        """根据报告类型生成完整的模块结构"""
        fields = self.profile.get("数据结构", {})
        has_competitors = len(self.profile.get("详细数据", {}).get("competitors", {})) > 0

        # 基础模块（所有报告类型都有）
        base_modules = """### 1. 核心数据概览
统计卡片展示：内容数、总点赞、总评论、总播放、平均互动率等

### 2. 执行摘要 (Executive Summary)
在报告顶部用醒目的样式展示：
- 核心发现：用1-2句话概括整体态势
- 关键指标：最重要的3个数据亮点
- 风险提示：如果有负面评价超过30%，需要醒目提示"""

        # 模块 4（根据报告类型变化）
        module4 = self._get_module4_content()

        # 热门内容模块（所有报告类型都有）
        content_module = """### 3. 热门内容 TOP 10 排行榜
使用上面提供的真实数据，每项展示：
- 排名、标题、作者
- 互动数据（点赞/评论/播放）
- 简短分析为什么这条内容受欢迎"""

        # 热词模块
        hotword_module = """### 5. 热词综合分析
- 热词云图：帖子高频词 + 评论高频词
- 每个热词标注频次"""

        # 评论分析模块（仅舆情类和风险类报告显示）
        comment_module = ""
        if self.report_type in ['sentiment', 'risk'] and fields.get("评论内容"):
            comment_module = """
### 6. 评论深度分析
- 用户关注焦点：从评论中提炼出3-5个用户最关心的话题
- 典型正面评价：引用2-3条真实正面评论
- 典型负面评价：引用2-3条真实负面评论
- 高频诉求：用户反复提到的问题或需求"""

        # 洞察建议模块
        insight_module = """
### 7. 数据洞察与建议
基于真实数据生成4-6条洞察，每条包含：
- 发现：发现了什么现象/问题
- 依据：引用具体数据或评论作为支撑
- 建议：应该采取什么行动"""

        # 竞品模块
        competitor_module = ""
        if has_competitors:
            competitor_module = """
### 8. 竞品对比分析
- 列出所有在内容中被提及的竞品品牌
- 展示用户提及竞品的频次和具体上下文
- 分析用户对竞品的评价
- 对比分析：品牌 vs 竞品在用户心中的优劣势"""

        # 行动方案模块
        action_module = """
### 9. 处理建议与行动方案
分类给出具体的处理建议：
- 紧急处理：如果有负面舆情，如何回应
- 产品优化：基于用户反馈的改进建议
- 营销方向：应该强化哪些卖点
- 内容策略：后续应该发什么类型的内容"""

        # 评论展示模块
        comment_display = ""
        if fields.get("评论内容"):
            comment_display = """
### 10. 代表性用户评论展示区
展示8-10条代表性评论，包含：
- 用户名、评论内容、点赞数、情感标签
- 高亮的购买意向标签（如果评论有购买意向）"""

        # 组装所有模块
        all_modules = [base_modules, content_module, module4, hotword_module]

        if comment_module:
            all_modules.append(comment_module)

        all_modules.append(insight_module)

        if competitor_module:
            all_modules.append(competitor_module)

        all_modules.append(action_module)

        if comment_display:
            all_modules.append(comment_display)

        return '\n'.join(all_modules)

    def _get_page_theme(self) -> str:
        """获取页面主题色"""
        return self.REPORT_TYPE_THEMES.get(self.report_type, '#667eea → #764ba2 (蓝紫色)')

    def _get_analysis_focus(self) -> str:
        """获取分析重点说明"""
        focus_map = {
            'sentiment': """本报告需综合分析以下**四个维度**：
1. **用户评论内容** - 用户的真实反馈、观点、情感
2. **评论热度** - 评论的点赞数（反映观点的受欢迎程度）
3. **帖子内容** - 帖子标题/正文的主题和关键信息
4. **帖子互动数据** - 点赞、分享、收藏、播放量等""",

            'trend': """本报告重点分析**热度趋势**：
1. **时间序列分析** - 话题热度随时间的变化规律
2. **关键节点** - 热度爆发的时间点和触发因素
3. **内容趋势** - 不同类型内容的热度表现
4. **未来预测** - 基于历史数据的趋势预判""",

            'volume': """本报告重点分析**声量规模**：
1. **总量评估** - 内容数、曝光量、互动量的总和
2. **声源分布** - 不同渠道/账号的声量贡献
3. **声量质量** - 互动深度 vs 广度
4. **对比基准** - 与行业平均水平的对比""",

            'keyword': """本报告重点分析**关键词特征**：
1. **核心词提取** - 高频出现的关键词
2. **关联词分析** - 词与词之间的关系强度
3. **情感词识别** - 正面/负面关键词分布
4. **词云分布** - 关键词的重要性层级""",

            'hot_topics': """本报告重点分析**热门话题**：
1. **话题发现** - 从内容中聚类出热门话题
2. **热度排序** - 按讨论量和互动量排序
3. **话题演变** - 话题的生命周期分析
4. **用户参与** - 不同话题的用户参与度""",

            'viral_spread': """本报告重点分析**传播规律**：
1. **传播链路** - 内容从发布到扩散的路径
2. **关键节点** - 影响传播的关键用户/账号
3. **传播速度** - 内容扩散的时间特征
4. **传播模式** - 病毒式/圈层式/线性式""",

            'influencer': """本报告重点分析**影响力账号**：
1. **账号排序** - 按总互动量排序的TOP账号
2. **内容特征** - 头部账号的内容策略
3. **互动质量** - 账号与粉丝的互动深度
4. **影响力评估** - 账号的舆论引导能力""",

            'audience': """本报告重点分析**用户群体**：
1. **用户分层** - 按活跃度/情感倾向分层
2. **行为特征** - 用户的互动行为模式
3. **需求洞察** - 用户的关注点/痛点/期待
4. **价值评估** - 不同用户群体的价值贡献""",

            'comparison': """本报告重点分析**竞品对比**：
1. **多维度对比** - 声量/互动/口碑/传播力
2. **优劣势分析** - 明确各维度的强弱项
3. **用户认知** - 用户对不同品牌的印象差异
4. **竞争策略** - 基于对比结果的策略建议""",

            'risk': """本报告重点分析**舆情风险**：
1. **负面监测** - 负面评价的数量和占比
2. **风险来源** - 负面舆情的产生原因
3. **传播态势** - 负面内容的扩散情况
4. **预警建议** - 风险等级和应对建议"""
        }

        return focus_map.get(self.report_type, focus_map['sentiment'])

    def build_prompt(self) -> str:
        """构建完整的提示词"""
        platform_names = {
            'xhs': '小红书', 'dy': '抖音', 'ks': '快手', 'bili': 'B站',
            'wb': '微博', 'tieba': '百度贴吧', 'zhihu': '知乎'
        }
        platform_name = platform_names.get(self.platform, self.platform)
        report_type_name = self.REPORT_TYPE_NAMES.get(self.report_type, '舆情分析')

        fields = self.profile.get("数据结构", {})
        stats = self.profile.get("数值统计", {})
        content = self.profile.get("内容特征", {})
        detailed_data = self.profile.get("详细数据", {})

        # 根据报告类型构建数据特征描述
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

        # 格式化详细数据
        top_contents_str = json.dumps(detailed_data.get("top_contents", []), ensure_ascii=False, indent=2)
        hot_words_str = json.dumps(detailed_data.get("hot_words", []), ensure_ascii=False, indent=2)
        sentiment_dist = json.dumps(detailed_data.get("sentiment_distribution", {}), ensure_ascii=False)
        positive_examples = json.dumps(detailed_data.get("positive_examples", [])[:5], ensure_ascii=False, indent=2)
        negative_examples = json.dumps(detailed_data.get("negative_examples", [])[:5], ensure_ascii=False, indent=2)
        all_comments = json.dumps(detailed_data.get("representative_comments", [])[:10], ensure_ascii=False, indent=2)

        # 从详细数据中获取提取的竞品
        competitors_data = detailed_data.get("competitors", {})
        has_competitors = len(competitors_data) > 0
        competitors_str = json.dumps(competitors_data, ensure_ascii=False, indent=2) if has_competitors else "{}"

        # 获取动态生成的模块内容
        report_modules = self._get_report_modules()
        page_theme = self._get_page_theme()
        analysis_focus = self._get_analysis_focus()

        return f"""请根据以下数据，生成一个专业的{report_type_name} HTML 报告，保存到 ./reports/ 目录下。

## 数据概况
- 平台: {platform_name}
- 关键词: "{self.keywords}"
- 报告类型: {report_type_name}
- 数据量: {self.profile.get("总数据量")} 条
- 互动模式: {self.profile.get("互动模式")}
- 内容类型: {content.get("内容类型")}

【分析重点要求】
{analysis_focus}

分析时要结合多维度：
- 高赞评论 + 高热度帖子 = 大众共识/爆款话题
- 高赞评论 + 低热度帖子 = 小众痛点/真实需求
- 帖子内容引发的高频评论 = 用户关注点
- 评论观点分布 vs 帖子互动趋势 = 舆论走向

## 统计数据
- 总点赞: {stats.get("总量", {}).get("likes", 0)}
- 总评论: {stats.get("总量", {}).get("comments", 0)}
- 总播放: {stats.get("总量", {}).get("views", 0)}
- 平均点赞: {stats.get("平均值", {}).get("likes", 0)}
- 平均评论: {stats.get("平均值", {}).get("comments", 0)}

## 热门内容 TOP 10 (真实数据，必须在报告中展示)
```json
{top_contents_str}
```

## 热词分析 [必须用 ECharts 词云图渲染这些数据]
```json
{hot_words_str}
```
**使用说明**：将上述 JSON 数组作为 ECharts wordCloud series 的 data 源，格式 [{{"name": "热词", "value": 权重}}, ...]

## 情感分布统计 [必须用 ECharts 饼图渲染这些数据]
```json
{sentiment_dist}
```
**使用说明**：将上述 JSON 作为 ECharts pie series 的 data 源，格式 [{{"value": 60.5, "name": "正面"}}, ...]

## 正面评价示例 (真实用户评论)
```json
{positive_examples}
```

## 负面评价示例 (真实用户评论)
```json
{negative_examples}
```

## 代表性评论 (真实数据)
```json
{all_comments}
```
""" + (f"""
## 从内容中提取的竞品数据
```json
{competitors_str}
```
""" if has_competitors else "") + f"""

## 页面风格
**必须使用以下主题色**：
渐变背景: {page_theme}

## 报告必须包含以下模块 (使用真实数据，严禁编造)：

{report_modules}
""" + (f"""
## 竞品对比分析补充
根据以下从帖子内容和评论中提取的真实竞品数据，生成竞品分析：
```json
{competitors_str}
```
- 列出所有在内容中被提及的竞品品牌
- 展示用户提及竞品的频次和具体上下文
- 分析用户对竞品的评价（正面/负面/中性）
- 对比分析：品牌 vs 竞品在用户心中的优劣势

如果没有竞品数据（上面 JSON 为空），则**完全不要显示这个模块**。
""" if has_competitors else "") + """

## 设计要求
1. **所有数据必须来自上面提供的 JSON，严禁编造**
2. **洞察要具体，必须引用真实评论作为依据**，如"用户 @xxx 在评论中提到'xxx'"
3. **建议要有可操作性**，不要泛泛而谈
4. **使用 ECharts 绘制图表**，响应式布局
5. **中文显示，美观专业，布局宽松舒适**
6. **每个模块有明显的视觉区分**，使用卡片式设计
7. **模块4是最重要的可视化模块**，必须使用 ECharts 渲染

请输出完整的、独立的 HTML 代码（包含 CSS 和 JavaScript）。
2. **洞察要具体，必须引用真实评论作为依据**，如"用户 @xxx 在评论中提到'xxx'"
3. **建议要有可操作性**，不要泛泛而谈
4. **使用 ECharts 绘制图表**，响应式布局
5. **中文显示，美观专业，布局宽松舒适**
6. **每个模块有明显的视觉区分**，使用卡片式设计

请输出完整的、独立的 HTML 代码（包含 CSS 和 JavaScript）。"""


def generate_ai_report_data(
    platform: str,
    keywords: str,
    data: List[Dict],
    report_type: str = 'sentiment'
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

    # 获取详细数据用于 AI 报告生成
    detailed_data = profiler.get_detailed_data()
    profile["详细数据"] = detailed_data

    prompt_builder = AIReportPromptBuilder(platform, keywords, profile, report_type)
    prompt = prompt_builder.build_prompt()

    return {
        "prompt": prompt,
        "profile": profile,
        "data_summary": {
            "count": len(data),
            "platform": platform,
            "keywords": keywords,
            "report_type": report_type
        },
        "detailed_data": detailed_data
    }

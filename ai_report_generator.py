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
        return [(word, int(weight * 1000)) for word, weight in keywords]

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
            sentiment_distribution = {
                k: round(v / total * 100, 1) for k, v in sentiment_stats.items()
            }
        else:
            sentiment_distribution = sentiment_stats

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
        detailed_data = self.profile.get("详细数据", {})

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

        return f"""请根据以下数据，生成一个专业的舆情分析 HTML 报告，保存到 ./reports/ 目录下。

## 数据概况
- 平台: {platform_name}
- 关键词: "{self.keywords}"
- 数据量: {self.profile.get("总数据量")} 条
- 互动模式: {self.profile.get("互动模式")}
- 内容类型: {content.get("内容类型")}

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

## 热词分析 (真实数据，必须用词云展示)
```json
{hot_words_str}
```

## 情感分布统计
{sentiment_dist}

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

## 页面风格
- B站/有播放数据 → 粉紫色渐变 (#ff9a9e → #fecfef)
- 小红书/有评论 → 蓝紫色渐变 (#667eea → #764ba2)
- 抖音/快手 → 暖色调 (#ff6b6b → #feca57)
- 其他 → 清新蓝绿 (#11998e → #38ef7d)

## 报告必须包含以下模块 (使用真实数据，严禁编造)：

### 1. 核心数据概览
统计卡片展示：内容数、总点赞、总评论、总播放、平均互动率等

### 2. 执行摘要 (Executive Summary)
在报告顶部用醒目的样式展示：
- 核心发现：用1-2句话概括整体舆情态势（如"整体口碑良好，正面评价占比XX%"）
- 关键指标：最重要的3个数据亮点
- 风险提示：如果有负面评价超过30%，需要醒目提示

### 3. 热门内容 TOP 10 排行榜
使用上面提供的真实数据，每项展示：
- 排名、标题、作者
- 互动数据（点赞/评论/播放）
- 简短分析为什么这条内容受欢迎

### 4. 情感分析可视化
- 情感分布饼图（使用上面的情感分布数据）
- 情感趋势总结

### 5. 热词云
使用上面提供的热词数据，突出用户讨论焦点

### 6. 评论深度分析
- 用户关注焦点：从评论中提炼出3-5个用户最关心的话题
- 典型正面评价：引用2-3条真实正面评论，说明用户喜欢什么
- 典型负面评价：引用2-3条真实负面评论，说明用户不满什么
- 高频诉求：用户反复提到的问题或需求

### 7. 竞品对比分析 (根据数据内容决定是否包含)
"""

        if has_competitors:
            prompt += f'''
根据以下从帖子内容和评论中提取的真实竞品数据，生成竞品分析模块：
```json
{competitors_str}
```
- 列出所有在内容中被提及的竞品品牌
- 展示用户提及竞品的频次和具体上下文
- 分析用户对竞品的评价（正面/负面/中性）
- 对比分析：品牌 vs 竞品在用户心中的优劣势
'''

        prompt += """
如果没有竞品数据（上面 JSON 为空），则**完全不要显示这个模块**，直接跳到第8部分。

### 8. 舆情洞察与建议 (非常重要)
基于真实数据生成4-6条洞察，每条包含：
- 发现：发现了什么现象/问题
- 依据：引用具体数据或评论作为支撑
- 建议：应该采取什么行动

示例格式：
- 🔍 **发现**：产品体验整体良好，但存在XX问题
- 📊 **依据**：XX%的评论提到XX，如用户@xxx说："..."
- 💡 **建议**：建议优化XX功能，加强XX方面的宣传

### 9. 处理建议与行动方案
分类给出具体的处理建议：
- 紧急处理：如果有负面舆情，如何回应
- 产品优化：基于用户反馈的改进建议
- 营销方向：应该强化哪些卖点
- 内容策略：后续应该发什么类型的内容

### 10. 代表性用户评论展示区
展示8-10条代表性评论，包含：
- 用户名、评论内容、点赞数、情感标签
- 高亮的购买意向标签（如果评论有购买意向）

## 设计要求
1. **所有数据必须来自上面提供的 JSON，严禁编造**
2. **洞察要具体，必须引用真实评论作为依据**，如"用户 @xxx 在评论中提到'xxx'"
3. **建议要有可操作性**，不要泛泛而谈
4. **使用 ECharts 绘制图表**，响应式布局
5. **中文显示，美观专业，布局宽松舒适**
6. **每个模块有明显的视觉区分**，使用卡片式设计

请输出完整的、独立的 HTML 代码（包含 CSS 和 JavaScript）。"""


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

    # 获取详细数据用于 AI 报告生成
    detailed_data = profiler.get_detailed_data()
    profile["详细数据"] = detailed_data

    prompt_builder = AIReportPromptBuilder(platform, keywords, profile)
    prompt = prompt_builder.build_prompt()

    return {
        "prompt": prompt,
        "profile": profile,
        "data_summary": {
            "count": len(data),
            "platform": platform,
            "keywords": keywords
        },
        "detailed_data": detailed_data
    }

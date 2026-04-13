# -*- coding: utf-8 -*-
"""
智能字段自动识别器
自动检测不同平台的字段名映射，无需手动配置
支持中英文、缩写、变体、驼峰/下划线命名
"""

import re
import difflib
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict


class AutoFieldDetector:
    """
    自动识别数据字段的智能检测器

    通过语义相似度 + 数据特征分析，自动建立字段映射
    支持：
    - 中英文混合字段名
    - 驼峰/下划线/短横线命名
    - 字段名变化自动适配
    - 数值类型自动推断
    """

    # 字段语义定义（标准字段 → 可能的变体）
    FIELD_SEMANTICS = {
        "likes": {
            "keywords": ["like", "digg", "thumb", "praise", "up", "good", "heart", "love",
                        "赞", "喜欢", "点赞", "顶", "好评", "棒", "赞数", "喜欢数"],
            "exclude": ["unlike", "dislike", "踩", "不喜欢"],
            "value_type": "number",
            "priority": 100
        },
        "views": {
            "keywords": ["view", "play", "watch", "read", "pv", "visit", "impression", "expose",
                        "观看", "播放", "阅读", "浏览", "访问量", "曝光", "展现", "点击"],
            "exclude": ["review", "preview"],
            "value_type": "number",
            "priority": 95
        },
        "comments": {
            "keywords": ["comment", "reply", "discuss", "talk", "message", "danmaku", "dm", "bullet",
                        "评论", "回复", "讨论", "留言", "弹幕", "评价", "点评"],
            "exclude": [],
            "value_type": "number",
            "priority": 90
        },
        "shares": {
            "keywords": ["share", "repost", "forward", "transmit", "spread", "retweet",
                        "分享", "转发", "扩散", "传播", "转", "分享数"],
            "exclude": [],
            "value_type": "number",
            "priority": 85
        },
        "favorites": {
            "keywords": ["favorite", "collect", "save", "star", "bookmark", "store",
                        "收藏", "喜爱", "保存", "收藏数", "喜欢数", "星标"],
            "exclude": [],
            "value_type": "number",
            "priority": 80
        },
        "coins": {
            "keywords": ["coin", "b_coin", "money", "pay", "tip", "reward",
                        "投币", "币", "硬币", "打赏", "赞赏"],
            "exclude": [],
            "value_type": "number",
            "priority": 75
        },
        "followers": {
            "keywords": ["follow", "fan", "subscribe", "subscription",
                        "关注", "粉丝", "订阅", "关注数", "粉丝数"],
            "exclude": ["following"],
            "value_type": "number",
            "priority": 70
        },
        "duration": {
            "keywords": ["duration", "length", "time", "period", "span",
                        "时长", "长度", "时间", "持续时间", "视频时长"],
            "exclude": ["create_time", "publish_time", "update_time"],
            "value_type": "number",
            "priority": 65
        }
    }

    # 命名风格模式
    NAMING_PATTERNS = {
        "snake_case": re.compile(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$'),      # like_count
        "camelCase": re.compile(r'^[a-z][a-zA-Z0-9]*$'),                 # likeCount
        "PascalCase": re.compile(r'^[A-Z][a-zA-Z0-9]*$'),                # LikeCount
        "kebab-case": re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$'),      # like-count
        "chinese": re.compile(r'^[\u4e00-\u9fa5]+(数|量|次数)?$'),        # 点赞数
        "mixed": re.compile(r'.*[_\-].*'),                                # 包含分隔符
    }

    def __init__(self, confidence_threshold: float = 0.6):
        """
        初始化检测器

        Args:
            confidence_threshold: 匹配置信度阈值（0-1），低于此值视为未匹配
        """
        self.confidence_threshold = confidence_threshold
        self.field_map: Dict[str, str] = {}  # standard_field -> actual_field
        self.confidence_scores: Dict[str, float] = {}

    def detect(self, sample_data: Dict) -> Dict[str, str]:
        """
        自动检测字段映射

        Args:
            sample_data: 样例数据（通常是第一条数据的 interact_info）

        Returns:
            字段映射字典 {标准字段名: 实际字段名}
        """
        if not sample_data or not isinstance(sample_data, dict):
            return {}

        self.field_map = {}
        self.confidence_scores = {}

        all_keys = list(sample_data.keys())
        used_keys: Set[str] = set()

        # 按优先级排序标准字段
        sorted_fields = sorted(
            self.FIELD_SEMANTICS.items(),
            key=lambda x: x[1]["priority"],
            reverse=True
        )

        for standard_field, semantics in sorted_fields:
            best_match, confidence = self._find_best_match(
                standard_field, semantics, all_keys, used_keys
            )

            if best_match and confidence >= self.confidence_threshold:
                self.field_map[standard_field] = best_match
                self.confidence_scores[standard_field] = confidence
                used_keys.add(best_match)

        return self.field_map

    def _find_best_match(
        self,
        standard_field: str,
        semantics: Dict,
        all_keys: List[str],
        used_keys: Set[str]
    ) -> Tuple[Optional[str], float]:
        """
        为单个标准字段找到最佳匹配
        """
        candidates = []
        keywords = semantics["keywords"]
        exclude = semantics.get("exclude", [])

        for key in all_keys:
            if key in used_keys:
                continue

            # 排除黑名单
            if any(excl.lower() in key.lower() for excl in exclude):
                continue

            # 计算匹配分数
            score = self._calculate_match_score(key, keywords, standard_field)

            if score > 0:
                candidates.append((key, score))

        if not candidates:
            return None, 0.0

        # 返回分数最高的
        best = max(candidates, key=lambda x: x[1])
        return best

    def _calculate_match_score(
        self,
        key: str,
        keywords: List[str],
        standard_field: str
    ) -> float:
        """
        计算字段名与关键字的匹配分数
        """
        key_lower = key.lower()
        key_normalized = self._normalize_field_name(key)
        scores = []

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # 1. 精确包含（最高分）
            if keyword_lower in key_lower:
                # 完全匹配字段名
                if key_lower == keyword_lower:
                    scores.append(1.0)
                # 前缀匹配（如 like_count 包含 like）
                elif key_lower.startswith(keyword_lower + '_') or \
                     key_lower.startswith(keyword_lower + '-') or \
                     key_lower.endswith('_' + keyword_lower) or \
                     key_lower.endswith('-' + keyword_lower):
                    scores.append(0.95)
                # 中间包含
                else:
                    scores.append(0.85)

            # 2. 编辑距离相似度（处理拼写变体）
            similarity = difflib.SequenceMatcher(None, key_normalized, keyword_lower).ratio()
            if similarity > 0.7:
                scores.append(similarity * 0.8)

            # 3. 驼峰匹配（likeCount → like）
            camel_split = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', key)
            for part in camel_split:
                if part.lower() == keyword_lower:
                    scores.append(0.9)

            # 4. 下划线分割匹配
            if '_' in key:
                parts = key_lower.split('_')
                if keyword_lower in parts:
                    scores.append(0.88)

        return max(scores) if scores else 0.0

    def _normalize_field_name(self, field: str) -> str:
        """
        标准化字段名（统一命名风格）
        """
        # 移除数字后缀（count_123 → count）
        field = re.sub(r'_\d+$', '', field)
        # 统一分隔符为空格
        field = re.sub(r'[_\-]+', ' ', field)
        # 驼峰转空格
        field = re.sub(r'([a-z])([A-Z])', r'\1 \2', field)
        return field.lower().strip()

    def detect_from_data_list(self, data_list: List[Dict]) -> Dict[str, str]:
        """
        从多条数据中智能推断字段映射（更可靠）

        通过分析多条数据的共同字段，提高识别准确率
        """
        if not data_list:
            return {}

        # 收集所有字段出现频率
        field_frequency = defaultdict(int)
        field_samples = defaultdict(list)

        for item in data_list[:10]:  # 分析前10条
            interact = item.get('interact_info', {}) if isinstance(item, dict) else {}
            if not isinstance(interact, dict) or not interact:
                continue

            for key in interact.keys():
                field_frequency[key] += 1
                field_samples[key].append(interact[key])

        # 找出高频字段（在至少50%数据中出现）
        total = min(len(data_list), 10)
        common_fields = {
            k: v for k, v in field_frequency.items()
            if v >= total * 0.5
        }

        # 使用第一条数据作为样本，但只考虑高频字段
        raw_sample = data_list[0].get('interact_info', {})
        sample = raw_sample if isinstance(raw_sample, dict) else {}
        filtered_sample = {k: v for k, v in sample.items() if k in common_fields}

        return self.detect(filtered_sample)

    def get_field_value(self, data: Dict, standard_field: str) -> int:
        """
        获取标准字段的值

        Args:
            data: 数据字典（通常是 interact_info）
            standard_field: 标准字段名（如 "likes", "views"）

        Returns:
            字段值，未找到返回 0
        """
        if not self.field_map:
            return 0

        actual_field = self.field_map.get(standard_field)
        if not actual_field or actual_field not in data:
            return 0

        value = data[actual_field]
        if value is None:
            return 0

        try:
            # 处理字符串数字
            if isinstance(value, str):
                # 处理 "1.2万" 这样的格式
                if '万' in value:
                    return int(float(value.replace('万', '')) * 10000)
                # 处理 "1.2k" 这样的格式
                if 'k' in value.lower():
                    return int(float(value.lower().replace('k', '')) * 1000)
                # 移除逗号
                value = value.replace(',', '')

            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def explain_detection(self) -> str:
        """
        解释字段识别的结果（用于调试）
        """
        lines = ["=== 字段自动识别结果 ==="]

        for std_field, actual_field in sorted(self.field_map.items()):
            conf = self.confidence_scores.get(std_field, 0)
            lines.append(f"  {std_field:12} ← {actual_field:20} (置信度: {conf:.2%})")

        return "\n".join(lines)


class AdaptiveFieldMapper:
    """
    自适应字段映射器
    可以学习已识别的映射，加速后续识别
    """

    def __init__(self):
        self.detector = AutoFieldDetector()
        self.learned_mappings: Dict[str, Dict[str, str]] = {}

    def detect_for_platform(self, platform: str, data_list: List[Dict]) -> Dict[str, str]:
        """
        为特定平台检测字段映射（带缓存）
        """
        # 如果有学习过的映射，先尝试使用
        if platform in self.learned_mappings:
            sample = data_list[0].get('interact_info', {}) if data_list else {}
            if self._validate_mapping(self.learned_mappings[platform], sample):
                return self.learned_mappings[platform]

        # 重新检测
        field_map = self.detector.detect_from_data_list(data_list)

        # 保存学习结果
        if field_map:
            self.learned_mappings[platform] = field_map

        return field_map

    def _validate_mapping(self, mapping: Dict[str, str], sample: Dict) -> bool:
        """
        验证已学习的映射是否仍然有效
        """
        if not sample:
            return False

        # 至少要有50%的字段能匹配上
        matched = sum(1 for field in mapping.values() if field in sample)
        return matched >= len(mapping) * 0.5


# 便捷函数
def auto_detect_fields(data_list: List[Dict]) -> Dict[str, str]:
    """
    便捷函数：自动检测数据列表的字段映射

    Example:
        >>> data = [{"interact_info": {"like": 100, "view": 1000}}]
        >>> auto_detect_fields(data)
        {'likes': 'like', 'views': 'view'}
    """
    detector = AutoFieldDetector()
    return detector.detect_from_data_list(data_list)


def get_standardized_value(item: Dict, field_map: Dict[str, str], standard_field: str) -> int:
    """
    使用字段映射获取标准化值

    Example:
        >>> item = {"interact_info": {"like": 100}}
        >>> field_map = {"likes": "like"}
        >>> get_standardized_value(item, field_map, "likes")
        100
    """
    interact = item.get('interact_info', {}) if isinstance(item, dict) else {}
    actual_field = field_map.get(standard_field)

    if not actual_field or actual_field not in interact:
        return 0

    value = interact[actual_field]
    if value is None:
        return 0

    try:
        if isinstance(value, str):
            if '万' in value:
                return int(float(value.replace('万', '')) * 10000)
            if 'k' in value.lower():
                return int(float(value.lower().replace('k', '')) * 1000)
            value = value.replace(',', '')
        return int(float(value))
    except (ValueError, TypeError):
        return 0

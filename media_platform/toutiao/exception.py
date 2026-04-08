# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条自定义异常
"""


class DataFetchError(Exception):
    """数据获取异常"""
    pass


class IPBlockError(Exception):
    """IP被封异常"""
    pass


class LoginError(Exception):
    """登录异常"""
    pass

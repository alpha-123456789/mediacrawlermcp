# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

"""
今日头条登录模块
"""

import asyncio
from typing import Optional

from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractLogin
from tools import utils

from .exception import LoginError


class ToutiaoLogin(AbstractLogin):
    """今日头条登录"""

    def __init__(
        self,
        login_type: str,
        login_phone: str = "",
        browser_context: Optional[BrowserContext] = None,
        context_page: Optional[Page] = None,
        cookie_str: str = "",
    ):
        self.login_type = login_type
        self.login_phone = login_phone
        self.browser_context = browser_context
        self.context_page = context_page
        self.cookie_str = cookie_str

    async def begin(self):
        """开始登录流程"""
        utils.logger.info("[ToutiaoLogin.begin] 开始登录...")

        if self.login_type == "qrcode":
            await self.login_by_qrcode()
        elif self.login_type == "phone":
            await self.login_by_mobile()
        elif self.login_type == "cookie":
            await self.login_by_cookies()
        else:
            raise LoginError(f"[ToutiaoLogin.begin] 不支持的登录类型: {self.login_type}")

    async def check_login_state(self) -> bool:
        """检查登录状态"""
        try:
            cookies = await self.browser_context.cookies()
            for cookie in cookies:
                if cookie.get("name") in ["sessionid", "tt_webid"]:
                    return True
            # 检查页面上是否有用户头像
            user_avatar = await self.context_page.query_selector(
                ".user-avatar, .avatar, [class*=\"avatar\"]"
            )
            return user_avatar is not None
        except:
            return False

    async def login_by_qrcode(self):
        """二维码登录"""
        utils.logger.info("[ToutiaoLogin.login_by_qrcode] 开始二维码登录...")

        try:
            # 循环刷新直到二维码显示，最多尝试5次
            max_retries = 5
            qrcode_img = None

            for retry in range(max_retries):
                utils.logger.info(f"[ToutiaoLogin.login_by_qrcode] 第 {retry + 1}/{max_retries} 次尝试获取二维码")

                # 如果之前有弹窗，先关闭
                if retry > 0:
                    try:
                        close_btn = self.context_page.locator(".ttp-modal-close-btn, .close-btn, [aria-label='关闭弹窗']").first
                        await close_btn.click(timeout=2000)
                        await asyncio.sleep(1)
                    except:
                        # 尝试点击ESC或点击遮罩关闭
                        await self.context_page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)

                # 等待并点击登录按钮
                # 按钮结构: <a class="login-button" rel="nofollow">登录</a>
                login_selectors = [
                    "a.login-button",
                    "text=登录",
                    ".login-button",
                ]

                clicked = False
                for selector in login_selectors:
                    try:
                        btn = self.context_page.locator(selector).first
                        await btn.wait_for(state="visible", timeout=3000)
                        await btn.click()
                        clicked = True
                        break
                    except:
                        continue

                if not clicked:
                    # 使用 JavaScript 强制点击
                    await self.context_page.evaluate(
                        '() => document.querySelector("a.login-button")?.click()'
                    )
                    clicked = True

                if clicked:
                    utils.logger.info("[ToutiaoLogin.login_by_qrcode] 已点击登录按钮")
                await asyncio.sleep(2)

                # 等待登录弹窗出现
                # 头条可能会显示多种登录方式，尝试切换到二维码登录
                qr_tab_selectors = [
                    ".web-login-union__login__scan-code__title",  # 扫码登录标题
                    "text=扫码登录",
                    ".web-login-scan-code",
                    "img[aria-label='二维码']",
                ]

                qr_tab_clicked = False
                for selector in qr_tab_selectors:
                    try:
                        qr_tab = await self.context_page.wait_for_selector(
                            selector, timeout=2000, state="visible"
                        )
                        if qr_tab:
                            await qr_tab.click()
                            utils.logger.info(f"[ToutiaoLogin.login_by_qrcode] 点击二维码选项: {selector}")
                            qr_tab_clicked = True
                            await asyncio.sleep(1)
                            break
                    except:
                        continue

                if not qr_tab_clicked:
                    utils.logger.info("[ToutiaoLogin.login_by_qrcode] 未找到二维码选项，尝试直接获取二维码")

                # 等待二维码图片出现
                await asyncio.sleep(2)

                # 尝试查找二维码图片
                qrcode_selectors = [
                    ".web-login-scan-code__content__qrcode-wrapper__qrcode",  # 主要选择器
                    "img[aria-label='二维码']",
                    ".web-login-scan-code img",
                    "[class*='qrcode'] img",
                ]

                for selector in qrcode_selectors:
                    try:
                        qrcode_img = await self.context_page.wait_for_selector(
                            selector, timeout=5000, state="visible"
                        )
                        if qrcode_img:
                            utils.logger.info(f"[ToutiaoLogin.login_by_qrcode] 找到二维码: {selector}")
                            break
                    except:
                        continue

                if qrcode_img:
                    utils.logger.info("[ToutiaoLogin.login_by_qrcode] 二维码已显示，请扫码登录...")
                    await asyncio.sleep(10)
                    break
                else:
                    utils.logger.warning(f"[ToutiaoLogin.login_by_qrcode] 第 {retry + 1} 次未找到二维码，准备重试")
                    await self.context_page.screenshot(path=f"toutiao_qrcode_debug_{retry + 1}.png")

            if not qrcode_img:
                utils.logger.error("[ToutiaoLogin.login_by_qrcode] 多次尝试后仍未找到二维码，请检查页面")

            # 等待扫码完成（最多300秒 = 5分钟）
            for i in range(300):
                await asyncio.sleep(1)
                if await self.check_login_state():
                    utils.logger.info("[ToutiaoLogin.login_by_qrcode] 登录成功!")
                    return

            utils.logger.warning("[ToutiaoLogin.login_by_qrcode] 登录超时")

        except Exception as e:
            utils.logger.error(f"[ToutiaoLogin.login_by_qrcode] 二维码登录失败: {e}")
            # 截图保存调试信息
            try:
                await self.context_page.screenshot(path="toutiao_login_error.png")
                utils.logger.info("[ToutiaoLogin.login_by_qrcode] 已保存错误截图: toutiao_login_error.png")
            except:
                pass
            raise LoginError(f"二维码登录失败: {e}")

    async def login_by_mobile(self):
        """手机号登录"""
        utils.logger.info("[ToutiaoLogin.login_by_mobile] 开始手机号登录...")

        try:
            # 等待并点击登录按钮
            login_selectors = [
                "a.login-button",
                "text=登录",
                ".login-button",
            ]

            clicked = False
            for selector in login_selectors:
                try:
                    btn = self.context_page.locator(selector).first
                    await btn.wait_for(state="visible", timeout=3000)
                    await btn.click()
                    clicked = True
                    break
                except:
                    continue

            if not clicked:
                await self.context_page.evaluate(
                    '() => document.querySelector("a.login-button")?.click()'
                )
                clicked = True

            if clicked:
                utils.logger.info("[ToutiaoLogin.login_by_mobile] 已点击登录按钮")
            await asyncio.sleep(2)

            # 切换到手机号登录
            phone_tab_selectors = [
                "text=手机号登录",
                ".phone-tab",
                "[data-testid=\"phone-login\"]",
            ]

            phone_tab_clicked = False
            for selector in phone_tab_selectors:
                try:
                    phone_tab = await self.context_page.wait_for_selector(
                        selector, timeout=2000, state="visible"
                    )
                    if phone_tab:
                        await phone_tab.click()
                        phone_tab_clicked = True
                        await asyncio.sleep(1)
                        break
                except:
                    continue

            if not phone_tab_clicked:
                utils.logger.warning("[ToutiaoLogin.login_by_mobile] 未找到手机号登录选项")

            # 输入手机号
            if self.login_phone:
                phone_input = await self.context_page.wait_for_selector(
                    'input[type="tel"], input[placeholder*="手机号"], input[name="phone"]',
                    timeout=5000
                )
                if phone_input:
                    await phone_input.fill(self.login_phone)
                    await asyncio.sleep(1)

                    # 点击获取验证码
                    code_btn = await self.context_page.query_selector(
                        'text=获取验证码, .send-code-btn'
                    )
                    if code_btn:
                        await code_btn.click()
                        utils.logger.info("[ToutiaoLogin.login_by_mobile] 验证码已发送")

            # 等待用户手动完成登录
            utils.logger.info("[ToutiaoLogin.login_by_mobile] 请在浏览器中完成登录...")

            for i in range(60):
                await asyncio.sleep(1)
                if await self.check_login_state():
                    utils.logger.info("[ToutiaoLogin.login_by_mobile] 登录成功!")
                    return

        except Exception as e:
            utils.logger.error(f"[ToutiaoLogin.login_by_mobile] 手机号登录失败: {e}")
            raise LoginError(f"手机号登录失败: {e}")

    async def login_by_cookies(self):
        """Cookie登录"""
        utils.logger.info("[ToutiaoLogin.login_by_cookies] 开始Cookie登录...")

        try:
            if not self.cookie_str:
                raise LoginError("Cookie字符串为空")

            # 解析cookies
            cookies = []
            for cookie_pair in self.cookie_str.split(";"):
                cookie_pair = cookie_pair.strip()
                if not cookie_pair:
                    continue
                if "=" in cookie_pair:
                    name, value = cookie_pair.split("=", 1)
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": ".toutiao.com",
                        "path": "/",
                    })

            # 添加cookies
            await self.browser_context.add_cookies(cookies)

            # 验证登录
            await self.context_page.goto("https://www.toutiao.com/", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            if await self.check_login_state():
                utils.logger.info("[ToutiaoLogin.login_by_cookies] Cookie登录成功")
            else:
                utils.logger.warning("[ToutiaoLogin.login_by_cookies] Cookie可能已过期")

        except Exception as e:
            utils.logger.error(f"[ToutiaoLogin.login_by_cookies] Cookie登录失败: {e}")
            raise LoginError(f"Cookie登录失败: {e}")

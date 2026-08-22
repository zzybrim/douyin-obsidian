#!/usr/bin/env python3
"""用 Playwright + 系统 Chrome 从抖音提取帖子信息（绕过 JSVM 反爬壳）

抖音 2026 年升级反爬后，无 Cookie 请求全部返回 JSVM 壳，_ROUTER_DATA 解析失效。
本脚本使用真实浏览器（系统 Chrome）建立 session 后，手动调用 aweme/detail API
（带 pc_client_type / version_code 等参数即可，无需 JS 签名），输出标准化 JSON。

用法:
  python douyin_browser_extract.py "<分享链接>" [--output <保存路径>]
"""
import argparse
import json
import re
import sys

from playwright.sync_api import sync_playwright

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

FETCH_JS = """async (vid) => {
    const params = new URLSearchParams({
        device_platform: 'webapp', aid: '6383', channel: 'channel_pc_web',
        aweme_id: vid, pc_client_type: '1', version_code: '170400',
        version_name: '17.4.0', cookie_enabled: 'true', platform: 'PC', downlink: '10'
    });
    const r = await fetch('/aweme/v1/web/aweme/detail/?' + params,
        {headers: {'Accept': 'application/json'}});
    const t = await r.text();
    return {status: r.status, body: t};
}"""


def _extract_video_id(page) -> str:
    """从当前页面 URL 或 _ROUTER_DATA 提取 video_id"""
    m = re.search(r"/video/(\d+)", page.url)
    if m:
        return m.group(1)
    try:
        rd = page.evaluate("window._ROUTER_DATA ? JSON.stringify(window._ROUTER_DATA) : null")
        if rd:
            data = json.loads(rd)
            page_data = data.get("loaderData", {}).get("video_(id)/page", {})
            if page_data.get("itemId"):
                return str(page_data["itemId"])
    except Exception:
        pass
    return ""


def extract(share_url: str, timeout_ms: int = 45000) -> dict:
    """打开分享链接建立 session，手动调用 detail API，返回标准化帖子信息"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--headless=new",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        )
        ctx = browser.new_context(
            user_agent=DESKTOP_UA,
            locale="zh-CN",
            viewport={"width": 1280, "height": 720},
        )
        # 去除自动化标记，降低被识别为爬虫的概率
        ctx.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )
        page = ctx.new_page()

        try:
            # 1) 先访问首页建立 session（关键：否则 detail API 会被风控拦截）
            page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            # 2) 访问分享链接，解析 video_id
            page.goto(share_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            video_id = _extract_video_id(page)
            if not video_id:
                return {}

            # 3) 手动调用 detail API（页面 session 内，无签名也可通过）
            #    抖音风控间歇性限流（403）或页面导航导致上下文销毁，失败后冷却重试
            result = None
            for attempt in range(4):
                try:
                    result = page.evaluate(FETCH_JS, video_id)
                    if result["status"] == 200 and '"status_code":0' in result["body"]:
                        break
                except Exception:
                    # 页面导航导致执行上下文销毁：等页面稳定后再试
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                    except Exception:
                        pass
                page.wait_for_timeout(5000 * (attempt + 1))  # 5s / 10s / 15s 冷却
            if result is None or result["status"] != 200 or '"status_code":0' not in result["body"]:
                return {}

            data = json.loads(result["body"])
            a = data.get("aweme_detail", {})
            if not a.get("aweme_id"):
                return {}

            video = a.get("video", {})
            play_urls = video.get("play_addr", {}).get("url_list", [])
            covers = video.get("cover", {}).get("url_list", [])
            images = a.get("images", [])

            base = {
                "video_id": a.get("aweme_id"),
                "desc": a.get("desc", ""),
                "author": a.get("author", {}).get("nickname", ""),
                "duration_ms": a.get("duration", 0),
                "cover_url": covers[0] if covers else "",
            }
            # 图文帖子: images 字段存在时优先（video 字段只是背景音乐）
            if images:
                base["images"] = [
                    img["url_list"][0] for img in images if img.get("url_list")
                ]
                return base
            base["play_url"] = play_urls[0] if play_urls else ""
            return base
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description="浏览器提取抖音帖子信息")
    parser.add_argument("link", help="抖音分享链接")
    parser.add_argument("--output", "-o", help="保存 JSON 到文件")
    args = parser.parse_args()

    result = extract(args.link)
    if not result:
        print("NO_DATA: 未能提取到帖子信息", file=sys.stderr)
        sys.exit(1)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已保存到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()

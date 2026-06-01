"""
保存什么值得买登录态 cookies
运行方式: python3 scripts/save_smzdm_cookies.py

流程：
1. 打开浏览器窗口，跳转到 smzdm 登录页
2. 你手动扫码/账号登录
3. 检测到登录成功（URL 变化）后自动保存 cookies
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "smzdm_cookies.json")
LOGIN_URL = "https://zhiyou.smzdm.com/user/login/"


def main():
    print("=" * 50)
    print("什么值得买 登录 Cookie 保存工具")
    print("=" * 50)
    print(f"\nCookie 将保存到: {OUTPUT}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()

        print("正在打开什么值得买登录页...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        print("\n请在浏览器中完成登录（扫码或账号密码）")
        print("检测到登录成功后会自动保存，请等待...")

        # 等待 URL 不再是登录页（登录成功后会跳转）
        try:
            page.wait_for_url(lambda url: LOGIN_URL not in url, timeout=300000)
        except Exception:
            print("超时未检测到登录，尝试直接保存当前 cookies...")

        # 等一会让 cookies 完全加载
        time.sleep(2)

        cookies = context.cookies()
        with open(OUTPUT, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Cookies 已保存 ({len(cookies)} 条)")
        print(f"   文件: {OUTPUT}")

        browser.close()


if __name__ == "__main__":
    main()

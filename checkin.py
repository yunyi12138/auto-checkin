import os
import time
import ddddocr
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ========== 配置区 ==========
# 优先从环境变量读取，若没有则使用硬编码（仅用于本地测试）
USERNAME = os.getenv('anliny', 'anliny')
PASSWORD = os.getenv('794531925zhao', '794531925zhao')

# 签到页 URL（固定）
CHECKIN_URL = 'https://www.gamemale.com/plugin.php?id=k_misign:sign'

# 最大验证码重试次数
MAX_RETRY = 5
# ============================

def login_and_checkin():
    """执行登录和签到"""
    with sync_playwright() as p:
        # 本地测试可将 headless 改为 False，并加上 slow_mo 观察
        browser = p.chromium.launch(headless=False,slow_mo=500)
        page = browser.new_page()
        
        print("🚀 开始执行签到任务...")
        
        try:
            # ---------- 1. 访问首页并打开登录框 ----------
            page.goto('https://www.gamemale.com')
            # 如果未登录，点击“登录”链接（右上角），注意Discuz!可能有多种样式
            if not page.is_visible('#ls_username'):
                page.click('text=登录')
                # 等待登录框出现
                page.wait_for_selector('#ls_username', state='visible', timeout=5000)
            
            # ---------- 2. 填写账号密码 ----------
            page.fill('#ls_username', USERNAME)
            page.fill('#ls_password', PASSWORD)
            
            # ---------- 3. 点击登录，触发验证码 ----------
            page.click('button:has-text("登录")')
            
            # ---------- 4. 等待验证码出现 ----------
            try:
                page.wait_for_selector('img[src*="seccode"]', state='visible', timeout=8000)
                print("✅ 验证码已加载")
                time.sleep(1)  # 等待图片完全渲染
            except PlaywrightTimeoutError:
                # 如果没有验证码，可能直接登录成功，直接跳转签到页
                print("ℹ️ 未检测到验证码，尝试直接签到...")
                page.goto(CHECKIN_URL)
                if page.is_visible('text=签到'):
                    page.click('text=签到')
                    print("🎉 签到成功（无验证码）")
                else:
                    print("⚠️ 可能已签到或登录失败")
                browser.close()
                return
            
            # ---------- 5. 验证码识别循环 ----------
            for attempt in range(MAX_RETRY):
                print(f"🔍 第 {attempt+1} 次识别验证码...")
                
                # 截图验证码
                captcha_element = page.query_selector('img[src*="seccode"]')
                captcha_element.screenshot(path='captcha.png')
                
                # 使用 ddddocr 识别
                ocr = ddddocr.DdddOcr(show_ad=False)
                with open('captcha.png', 'rb') as f:
                    captcha_code = ocr.classification(f.read())
                print(f"📝 识别结果: {captcha_code}")
                
                # 填入验证码
                # ---------- 填充验证码（通用选择器） ----------
                # 先等待输入框出现（多种选择器尝试）
                captcha_input = None
                selectors = [
                    
                    'input[name="seccodeverify"]',
                    'input[name="seccode"]',
                    '#seccodeverify_cSAg1tNZ15G5',
                    '#seccode',
                    '#verifycode',
                    'input[name="verifycode"]'
                ]
                for selector in selectors:
                    try:
                        # 等待最多 5 秒
                        page.wait_for_selector(selector, state='visible', timeout=5000)
                        captcha_input = selector
                        print(f"✅ 找到验证码输入框: {selector}")
                        break
                    except PlaywrightTimeoutError:
                        continue

                if not captcha_input:
                    print("❌ 未找到验证码输入框，请手动检查元素")
                    page.screenshot(path='no_input.png')
                    browser.close()
                    return

                page.fill(captcha_input, captcha_code)
                
                # 提交验证码（点击登录按钮）
                page.click('button:has-text("登录")')
                
                # 等待 2~3 秒，观察是否登录成功
                time.sleep(3)
               
              # ---------- 判断是否登录成功（稳健版） ----------
                # 等待 AJAX 响应返回（给服务器 2-3 秒处理时间）
                time.sleep(3)
                # ---------- 判断是否登录成功（适配 Discuz! 跳转页） ----------
                time.sleep(2)  # 等待页面响应

                # 1. 先检查是否有明确的错误提示（验证码错误等）
                page_content = page.content()
                error_keywords = ['验证码错误', '验证码不正确', '登录失败', '密码错误']
                has_error = any(keyword in page_content for keyword in error_keywords)

                if has_error:
                    print("❌ 登录失败：页面包含错误提示")
                    page.screenshot(path='login_error.png')
                    login_success = False
                else:
                    # 2. 检查 Discuz! 登录成功的典型特征
                    success_keywords = ['欢迎您回来', '现在将转入登录前页面', '用户中心','Anliny']
                    has_success = any(keyword in page_content for keyword in success_keywords)
                    
                    # 3. 或者检查是否已经显示用户中心/用户名
                    try:
                        page.wait_for_selector('text=Anliny', timeout=3000)
                        has_success = True
                        break
                    except:
                        pass
                    
                    if has_success:
                        login_success = True
                        print("✅ 登录成功！")
                        break
                    else:
                       
                        login_success = False
                        print("❌ 登录失败：未检测到成功标志")

                # 如果登录失败，刷新验证码并进入下一次循环
                if not login_success:
                    print("❌ 登录失败，准备重试...")
                    # 如果还没用完重试次数，点击刷新验证码
                    if attempt < MAX_RETRY - 1:
                        try:
                            # 尝试点击验证码图片刷新
                            captcha_element.click()
                            print("🔄 已刷新验证码")
                        except:
                            # 如果点击不了，直接刷新页面
                            page.reload()
                            print("🔄 已刷新页面")
                        time.sleep(1)
                        continue  # 跳到下一次循环
                    else:
                        print("💥 重试次数用完，退出")
                        browser.close()
                        return
            
            # ---------- 6. 执行签到 ----------
                        # ---------- 5. 执行签到（先强制跳转到签到页） ----------
            print("📍 登录成功，正在强制跳转到签到页...")
            page.goto(CHECKIN_URL)  # 强制跳转到签到专属页面
            page.wait_for_load_state('networkidle')  # 等待页面完全加载
            time.sleep(2)  # 额外等待按钮渲染

            # ---------- 6. 查找并点击签到按钮（稳健版） ----------
            sign_success = False

            # 策略1：匹配文本“签到”（最通用）
            try:
                # 查找所有包含“签到”文字的元素，取第一个可见的
                btn = page.locator('//*[contains(text(), "签到")]').first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    print("📅 已点击 '签到' 按钮 (文字匹配)")
                    sign_success = True
            except Exception as e:
                print(f"文字匹配失败: {e}")

            # 策略2：如果策略1失败，尝试特定类名（Discuz! 签到插件常用）
            if not sign_success:
                try:
                    # 常见签到按钮 class 或 id
                    page.click('.sign_btn, .misign_btn, #sign_button, a[onclick*="sign"]', timeout=5000)
                    print("📅 已点击 '签到' 按钮 (类名/属性匹配)")
                    sign_success = True
                except Exception as e:
                    print(f"类名匹配失败: {e}")

            # 策略3：如果都失败，检查是否已经签到
            if not sign_success:
                page_content = page.content()
                if '今日已签' in page_content or '已签到' in page_content or '您已签到' in page_content:
                    print("ℹ️ 今日已签到，无需重复签到")
                    sign_success = True  # 标记为已处理
                else:
                    # 实在找不到，保存现场供调试
                    print("⚠️ 仍未找到签到按钮，保存调试文件...")
                    with open('debug_page.html', 'w', encoding='utf-8') as f:
                        f.write(page.content())
                    page.screenshot(path='checkin_page.png')
                    print("📁 已保存 debug_page.html 和截图，请检查")

            # ---------- 7. 最终结果确认 ----------
            time.sleep(3)
            final_content = page.content()
            if '签到成功' in final_content or '今日已签' in final_content:
                print("🎉 签到任务完成！")
               
            else:
                print("❓ 签到结果未知，请手动查看网页。")
             
        except Exception as e:
            print(f"💥 发生异常: {e}")
            page.screenshot(path='error_screenshot.png')
            raise
        finally:
            browser.close()
            print("🏁 任务结束")

if __name__ == '__main__':
    login_and_checkin()

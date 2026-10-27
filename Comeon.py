import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time
import random
import glob
import json

# 导入截图处理需要的库
from PIL import Image
from io import BytesIO

# 导入图像处理与OCR库
import cv2
import numpy as np
import ddddocr

# 导入 undetected_chromedriver 以规避高强度指纹检测
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

PROXY_LIST = [
    "不使用代理",
    "192.168.1.216:25378",
    "192.168.1.233:25378",
    "192.168.1.210:8118"
]


class TaxInvoiceScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("发票查验自动化助手 (高级配置版)")
        self.root.geometry("620x490")

        self.input_folder = tk.StringVar()
        self.save_folder = tk.StringVar()
        self.selected_proxy = tk.StringVar(value=PROXY_LIST[0])
        self.orientation_mode = tk.StringVar(value="横向 (默认)")
        self.speed_mode = tk.StringVar(value="正常速度")
        self.is_running = False
        self.driver = None

        self.captcha_click_count = 0

        self.setup_ui()
        self.init_ocr()

    def setup_ui(self):
        frame_folder = tk.Frame(self.root)
        frame_folder.pack(pady=5, fill=tk.X, padx=20)
        tk.Label(frame_folder, text="读取目录:").pack(side=tk.LEFT)
        tk.Entry(frame_folder, textvariable=self.input_folder, width=35, state="readonly").pack(side=tk.LEFT, padx=10)
        tk.Button(frame_folder, text="📁 浏览", command=self.choose_folder).pack(side=tk.LEFT)

        frame_save = tk.Frame(self.root)
        frame_save.pack(pady=5, fill=tk.X, padx=20)
        tk.Label(frame_save, text="保存目录:").pack(side=tk.LEFT)
        tk.Entry(frame_save, textvariable=self.save_folder, width=35, state="readonly").pack(side=tk.LEFT, padx=10)
        tk.Button(frame_save, text="📁 浏览", command=self.choose_save_folder).pack(side=tk.LEFT)

        frame_settings = tk.Frame(self.root)
        frame_settings.pack(pady=10, fill=tk.X, padx=20)

        tk.Label(frame_settings, text="代理:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky="e")
        ttk.Combobox(frame_settings, textvariable=self.selected_proxy, values=PROXY_LIST, state="readonly",
                     width=16).grid(row=0, column=1, padx=5)

        tk.Label(frame_settings, text="方向:").grid(row=0, column=2, padx=(15, 5), pady=5, sticky="e")
        ttk.Combobox(frame_settings, textvariable=self.orientation_mode, values=["横向 (默认)", "纵向"],
                     state="readonly", width=12).grid(row=0, column=3, padx=5)

        tk.Label(frame_settings, text="模式:").grid(row=0, column=4, padx=(15, 5), pady=5, sticky="e")
        ttk.Combobox(frame_settings, textvariable=self.speed_mode, values=["正常速度", "减速运行", "稳定模式"],
                     state="readonly",
                     width=10).grid(row=0, column=5, padx=5)

        frame_controls = tk.Frame(self.root)
        frame_controls.pack(pady=10)

        self.btn_start = tk.Button(frame_controls, text="▶ 开始自动化", command=self.start_task, bg="#4CAF50",
                                   fg="white", font=("微软雅黑", 10, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=15)

        self.btn_stop = tk.Button(frame_controls, text="⏹ 停止", command=self.stop_task, state=tk.DISABLED,
                                  bg="#f44336", fg="white", font=("微软雅黑", 10, "bold"))
        self.btn_stop.pack(side=tk.LEFT, padx=15)

        tk.Label(self.root, text="运行日志:").pack(anchor=tk.W, padx=20)
        self.log_text = tk.Text(self.root, height=13, width=75, bg="#f8f9fa", font=("Consolas", 9))
        self.log_text.pack(padx=20, pady=5)

    def log(self, message):
        current_time_str = time.strftime('%H:%M:%S')
        log_str = f"[{current_time_str}] {message}\n"

        self.log_text.insert(tk.END, log_str)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

        try:
            log_file_path = os.path.join(os.getcwd(), "app_run_log.txt")
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

    def init_ocr(self):
        self.log("正在后台加载 ddddocr 模型，请稍候...")
        threading.Thread(target=self._load_ocr, daemon=True).start()

    def _load_ocr(self):
        try:
            self.ocr = ddddocr.DdddOcr(show_ad=False)
        except TypeError:
            self.ocr = ddddocr.DdddOcr()
        self.log("ddddocr 模型加载完成！")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="选择包含发票 PDF 或 XML 的文件夹")
        if folder:
            self.input_folder.set(folder)

    def choose_save_folder(self):
        folder = filedialog.askdirectory(title="选择验证后发票保存的文件夹")
        if folder:
            self.save_folder.set(folder)

    def start_task(self):
        if not hasattr(self, 'ocr'):
            messagebox.showwarning("提示", "OCR模型正在加载中，请稍等几秒钟再试！")
            return

        folder = self.input_folder.get()
        if not folder:
            messagebox.showwarning("提示", "请先选择读取文件夹！")
            return

        self.res_dir = self.save_folder.get()
        if not self.res_dir:
            messagebox.showwarning("提示", "请先选择保存目录！")
            return

        pdf_files = glob.glob(os.path.join(folder, "*.pdf"))
        xml_files = glob.glob(os.path.join(folder, "*.xml"))
        pdf_files_upper = glob.glob(os.path.join(folder, "*.PDF"))
        xml_files_upper = glob.glob(os.path.join(folder, "*.XML"))
        target_files = list(set(pdf_files + xml_files + pdf_files_upper + xml_files_upper))

        if not target_files:
            messagebox.showwarning("提示", "所选读取文件夹中没有找到 PDF 或 XML 文件！")
            return

        self.is_running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)

        self.log(f"总计找到 {len(target_files)} 个文件，准备核对断点状态...")

        self.img_dir = os.path.join(os.getcwd(), "img")
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.res_dir, exist_ok=True)

        threading.Thread(target=self.run_automation, args=(target_files,), daemon=True).start()

    def stop_task(self):
        self.is_running = False
        self.log("正在停止任务...")
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def simulate_human_delay(self, min_sec=1.0, max_sec=3.0):
        if self.speed_mode.get() in ["减速运行", "稳定模式"]:
            min_sec = min_sec * 1.15
            max_sec = max_sec * 1.20
        time.sleep(random.uniform(min_sec, max_sec))

    def check_stable_mode_limit(self):
        if self.speed_mode.get() != "稳定模式":
            return
        self.captcha_click_count += 1
        if self.captcha_click_count >= 15:
            self.log("⚠ 【稳定模式保护】获取/点击验证码已达 15 次，主动休眠 30 秒防拦截...")
            for i in range(30):
                if not self.is_running:
                    return
                time.sleep(1)
            self.captcha_click_count = 0
            self.log("✅ 30 秒强制冷却完毕，继续运行。")

    def init_browser(self):
        options = uc.ChromeOptions()
        proxy = self.selected_proxy.get()
        if proxy != "不使用代理":
            self.log(f"配置代理: {proxy}")
            options.add_argument(f'--proxy-server=http://{proxy}')

        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')

        is_landscape = True if "横向" in self.orientation_mode.get() else False

        appState = {
            "recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
            "selectedDestinationId": "Save as PDF",
            "version": 2,
            "isLandscapeEnabled": is_landscape,
            "isCssBackgroundEnabled": True
        }
        prefs = {
            'printing.print_preview_sticky_settings.appState': json.dumps(appState),
            'savefile.default_directory': self.res_dir
        }
        options.add_experimental_option('prefs', prefs)
        options.add_argument('--kiosk-printing')

        profile_path = os.path.abspath(os.path.join(os.getcwd(), "chrome_profile"))
        options.add_argument(f"--user-data-dir={profile_path}")

        try:
            import sys
            if getattr(sys, 'frozen', False):
                base_path = os.path.dirname(sys.executable)
            else:
                base_path = os.getcwd()

            driver_path = os.path.join(base_path, "chromedriver.exe")

            if os.path.exists(driver_path):
                self.log(f"🔍 检测到本地根目录有驱动，优先使用本地驱动...")
                self.driver = uc.Chrome(options=options, driver_executable_path=driver_path)
            else:
                self.log(f"🌐 未检测到本地驱动，交由程序自动联网匹配当前 Chrome 版本...")
                self.driver = uc.Chrome(options=options)

            self.driver.set_page_load_timeout(30)
            self.driver.maximize_window()
            self.log("浏览器启动成功！(纯净静默后台版已就绪)")
            return True
        except Exception as e:
            self.log(f"浏览器启动失败: {str(e)}")
            return False

    def save_element_screenshot_by_crop(self, element, save_path):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self.simulate_human_delay(0.8, 1.5)
            png = self.driver.get_screenshot_as_png()
            im = Image.open(BytesIO(png))
            rect = self.driver.execute_script("return arguments[0].getBoundingClientRect();", element)
            left = max(0, int(rect['left']))
            top = max(0, int(rect['top']))
            right = min(im.width, int(rect['right']))
            bottom = min(im.height, int(rect['bottom']))
            cropped_im = im.crop((left, top, right, bottom))
            cropped_im.save(save_path)
            return True
        except Exception as e:
            self.log(f"坐标裁剪截图失败: {e}")
            return False

    def process_color_mask(self, img_path, color):
        try:
            cv_img = cv2.imread(img_path)
            if cv_img is None:
                raise ValueError("图片加载失败")

            hsv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            if color == "blue":
                lower_bounds = np.array([100, 50, 50])
                upper_bounds = np.array([130, 255, 255])
                mask = cv2.inRange(hsv_img, lower_bounds, upper_bounds)
            elif color == "red":
                lower_red_1 = np.array([0, 50, 50])
                upper_red_1 = np.array([10, 255, 255])
                mask1 = cv2.inRange(hsv_img, lower_red_1, upper_red_1)
                lower_red_2 = np.array([170, 50, 50])
                upper_red_2 = np.array([180, 255, 255])
                mask2 = cv2.inRange(hsv_img, lower_red_2, upper_red_2)
                mask = cv2.bitwise_or(mask1, mask2)
            elif color == "yellow":
                lower_yellow = np.array([15, 50, 50])
                upper_yellow = np.array([40, 255, 255])
                mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)
            else:
                return img_path

            final_processed = cv2.bitwise_not(mask)
            processed_path = os.path.join(self.img_dir, f"yzm_processed_{color}.png")
            cv2.imwrite(processed_path, final_processed)
            return processed_path
        except Exception as e:
            self.log(f"颜色处理失败: {e}")
            return img_path

    def perform_ocr(self, img_path):
        try:
            with open(img_path, 'rb') as f:
                img_bytes = f.read()
            res = self.ocr.classification(img_bytes)
            return res
        except Exception as e:
            self.log(f"OCR识别错误: {e}")
            return ""

    def run_automation(self, target_files):
        try:
            self.log("正在扫描保存目录，智能跳过已处理的文件...")
            existing_results = os.listdir(self.res_dir) if os.path.exists(self.res_dir) else []
            pending_files = []

            for file_path in target_files:
                base_name = os.path.basename(file_path)
                name, _ = os.path.splitext(base_name)
                already_processed = any(f.endswith(f"-验-{name}.pdf") for f in existing_results)

                if already_processed:
                    self.log(f"⏭️ 断点触发，跳过已处理: {base_name}")
                else:
                    pending_files.append(file_path)

            if not pending_files:
                self.log("🎉 当前文件夹内所有发票均已处理完毕，无需重复执行！")
                self.stop_task()
                return

            self.log(f"过滤完成，即将开始处理剩余的 {len(pending_files)} 个文件。")
            self.captcha_click_count = 0

            if not self.init_browser():
                return

            wait = WebDriverWait(self.driver, 15)

            queue = [(f, 0) for f in pending_files]
            task_index = 0

            while queue:
                if not self.is_running:
                    break

                file_path, retry_count = queue.pop(0)
                task_index += 1

                try:
                    self.log(
                        f"--- 正在处理第 {task_index} 次任务 (剩余 {len(queue)}): {os.path.basename(file_path)} ---")

                    # ================== 1. 初始化访问与上传 ==================
                    self.driver.get("https://inv-veri.chinatax.gov.cn/fpcygzfw/national-invoice-check")
                    self.simulate_human_delay(2.0, 4.0)
                    file_cy_btn = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[2]/button[2]')))
                    ActionChains(self.driver).move_to_element(file_cy_btn).pause(
                        random.uniform(0.5, 1.2)).click().perform()
                    self.simulate_human_delay(0.8, 1.5)
                    try:
                        try:
                            file_input = self.driver.find_element(By.XPATH,
                                                                  '/html/body/div[6]/div[2]/div/div/div[2]/div[1]/div/div/div[1]/div')
                            if file_input.tag_name != 'input':
                                file_input = file_input.find_element(By.XPATH, './/input[@type="file"]')
                        except:
                            file_input = self.driver.find_element(By.XPATH, '//input[@type="file"]')
                        file_input.send_keys(file_path)
                    except Exception as e:
                        self.log(f"上传文件失败: {e}")
                        continue

                    self.log("文件路径已输入，正在等待系统解析 (最长30秒)...")
                    try:
                        # 0.2秒高频轮询，动态捕获包含“成功”的气泡
                        WebDriverWait(self.driver, 30, poll_frequency=0.2).until(
                            lambda d: any(
                                "成功" in p.text for p in (
                                        d.find_elements(By.XPATH, '/html/body/div[6]/div') +
                                        d.find_elements(By.XPATH, '/html/body/div[7]/div') +
                                        d.find_elements(By.XPATH, '/html/body/div[8]/div')
                                ) if p.is_displayed()
                            )
                        )
                        self.log("✅ 瞬间捕获到导入成功弹窗！准备点击确认...")
                        time.sleep(0.5)  # 稍微等待半秒让前端按钮状态刷新
                    except Exception:
                        self.log("❌ 30秒超时未检测到导入成功提示，判断为导入失败，触发重试...")
                        continue

                    try:
                        import_btns_elem = WebDriverWait(self.driver, 10).until(
                            lambda d: (d.find_elements(By.XPATH,
                                                       '/html/body/div[7]/div[2]/div/div/div[3]/div/button[2]/span') or
                                       d.find_elements(By.XPATH,
                                                       '/html/body/div[7]/div[2]/div/div/div[3]/div/button[2]') or
                                       d.find_elements(By.XPATH, '//button[span[contains(text(), "导入")]]'))
                        )
                        self.driver.execute_script("arguments[0].click();", import_btns_elem[0])
                        self.log("✅ 成功点击导入按钮！")
                    except Exception as e:
                        self.log(f"❌ 等待导入按钮超时: {e}")
                        continue

                    self.log("等待验证码生成或校验弹窗...")
                    self.simulate_human_delay(0.8, 1.5)

                    # ================== 2. 导入异常侦听 ==================
                    skip_current_file = False
                    try:
                        for _ in range(4):
                            early_popups = self.driver.find_elements(By.XPATH, '//*[@id="popup_ok"]')
                            if early_popups and early_popups[0].is_displayed():
                                early_msg_elem = self.driver.find_elements(By.XPATH, '//*[@id="popup_message"]')
                                early_msg = early_msg_elem[0].text if early_msg_elem else "未知异常"

                                if "1分钟" in early_msg or "频繁" in early_msg:
                                    self.log(f"🕒 导入阶段触发风控: '{early_msg}'，静默等待 62 秒...")
                                    for i in range(62):
                                        if not self.is_running: break
                                        time.sleep(1)
                                    self.driver.execute_script("arguments[0].click();", early_popups[0])

                                    if retry_count < 3:
                                        self.log("✅ 62秒等待结束，将当前发票移至队列尾部稍后重试...")
                                        queue.append((file_path, retry_count + 1))
                                    else:
                                        self.log(f"⚠️ {os.path.basename(file_path)} 连续重试超限，已彻底放弃。")

                                    skip_current_file = True
                                    break
                                else:
                                    self.log(f"⚠️ 拦截到真实导入异常: '{early_msg}'，点击确定并永久跳过...")
                                    self.driver.execute_script("arguments[0].click();", early_popups[0])
                                    self.simulate_human_delay(1.0, 1.5)
                                    skip_current_file = True
                                    break
                            time.sleep(0.5)
                    except Exception:
                        pass

                    if skip_current_file:
                        continue

                    # ================== 3. 验证码与查验循环 ==================
                    max_retries = 15
                    for attempt in range(max_retries):
                        if not self.is_running: break
                        self.check_stable_mode_limit()
                        if attempt > 0: self.log(f"第 {attempt + 1} 次验证码尝试...")

                        try:
                            time.sleep(0.5)
                            retry_popups = self.driver.find_elements(By.XPATH, '//*[@id="popup_ok"]')
                            if retry_popups and retry_popups[0].is_displayed():
                                retry_msg_elem = self.driver.find_elements(By.XPATH, '//*[@id="popup_message"]')
                                retry_msg = retry_msg_elem[0].text if retry_msg_elem else "未知提示"

                                if "1分钟" in retry_msg or "频繁" in retry_msg:
                                    self.log(f"🕒 刷新验证码触发风控: '{retry_msg}'，静默等待 62 秒...")
                                    for _ in range(62):
                                        if not self.is_running: break
                                        time.sleep(1)
                                    self.driver.execute_script("arguments[0].click();", retry_popups[0])
                                    self.log("✅ 62秒等待结束，已点掉频繁弹窗，继续获取验证码...")
                                    self.simulate_human_delay(1.0, 2.0)
                                else:
                                    self.log(f"⚠️ 发现遗留弹窗: '{retry_msg}'，直接点击清除...")
                                    self.driver.execute_script("arguments[0].click();", retry_popups[0])
                                    self.simulate_human_delay(0.5, 1.0)
                        except Exception:
                            pass

                        yzm_img_element = wait.until(EC.visibility_of_element_located((By.XPATH,
                                                                                       '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[6]/div/div/div/a/img')))
                        yzminfo_element = wait.until(EC.presence_of_element_located((By.XPATH,
                                                                                     '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[5]/div[2]/div/div[2]')))

                        self.simulate_human_delay(1.5, 2.5)
                        hint_text = yzminfo_element.text.strip()
                        self.log(f"检测到提示文字: {hint_text}")

                        main_captcha_path = os.path.join(self.img_dir, "yzm_img.png")
                        if self.save_element_screenshot_by_crop(yzm_img_element, main_captcha_path):
                            target_img_path = main_captcha_path
                            if "红" in hint_text:
                                self.log("准备提取红色文字...")
                                target_img_path = self.process_color_mask(main_captcha_path, "red")
                            elif "蓝" in hint_text:
                                self.log("准备提取蓝色文字...")
                                target_img_path = self.process_color_mask(main_captcha_path, "blue")
                            elif "黄" in hint_text:
                                self.log("准备提取黄色文字...")
                                target_img_path = self.process_color_mask(main_captcha_path, "yellow")
                            else:
                                self.log("普通文本识别，跳过颜色提取。")

                            self.log("正在执行 OCR 识别...")
                            ocr_result = self.perform_ocr(target_img_path)
                            self.log(f"➡ 识别结果: {ocr_result}")

                            if ocr_result:
                                yzm_input = self.driver.find_element(By.XPATH,
                                                                     '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[5]/div[2]/div/div[1]/div/input')
                                yzm_input.click()
                                time.sleep(0.1)
                                yzm_input.send_keys(Keys.CONTROL, 'a')
                                time.sleep(0.1)
                                yzm_input.send_keys(Keys.BACKSPACE)
                                time.sleep(0.1)
                                yzm_input.clear()

                                for char in ocr_result:
                                    yzm_input.send_keys(char)
                                    self.simulate_human_delay(0.1, 0.2)
                                self.log("✅ 验证码已填入，准备点击查验。")
                            else:
                                self.log("❌ OCR识别为空，正在点击图片刷新重试...")
                                self.driver.execute_script("arguments[0].click();", yzm_img_element)
                                self.simulate_human_delay(2.0, 3.0)
                                continue

                        self.simulate_human_delay(0.5, 1.0)
                        checkfp_btn = self.driver.find_element(By.XPATH,
                                                               '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[7]/div/div/button[1]/span')

                        self.driver.execute_script("arguments[0].click();", checkfp_btn)
                        self.log("已点击查验，等待网页响应...")

                        # ================== 4. 侦听响应结果 ==================
                        try:
                            # 扩大侦听范围，兼容 div[6], div[7], div[8] 各种可能的动态弹窗层级
                            WebDriverWait(self.driver, 10).until(
                                lambda d: d.find_elements(By.XPATH, '//*[@id="popup_ok"]') or \
                                          d.find_elements(By.XPATH, '/html/body/div[6]/div') or \
                                          d.find_elements(By.XPATH, '/html/body/div[7]/div') or \
                                          d.find_elements(By.XPATH, '/html/body/div[8]/div') or \
                                          d.find_elements(By.XPATH, '//*[@id="print-btn"]')
                            )
                        except:
                            self.log("等待响应超时或未检测到明确状态，继续执行...")

                        # 优先抓取 div[7] 弹窗，作为防线依次检查 6 和 8
                        new_error_popups = (self.driver.find_elements(By.XPATH, '/html/body/div[7]/div') or
                                            self.driver.find_elements(By.XPATH, '/html/body/div[8]/div') or
                                            self.driver.find_elements(By.XPATH, '/html/body/div[6]/div'))

                        if new_error_popups and new_error_popups[0].is_displayed():
                            msg = new_error_popups[0].text.strip()
                            if "验证码" in msg or "失败" in msg or "不对" in msg or "错误" in msg:
                                self.log(f"⚠ 捕获到顶部红色弹窗提示: {msg}")
                                self.log("验证码识别失败，正在点击图片刷新重试...")
                                try:
                                    yzm_img_element = self.driver.find_element(By.XPATH,
                                                                               '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[6]/div/div/div/a/img')
                                    self.driver.execute_script("arguments[0].click();", yzm_img_element)
                                    self.simulate_human_delay(2.0, 3.0)
                                except Exception as e:
                                    self.log(f"刷新验证码图片失败: {e}")
                                continue

                        # 通用弹窗侦听
                        popups = self.driver.find_elements(By.XPATH, '//*[@id="popup_ok"]')
                        if popups and popups[0].is_displayed():
                            msg_elem = self.driver.find_elements(By.XPATH, '//*[@id="popup_message"]')
                            msg = msg_elem[0].text if msg_elem else "未知提示"
                            self.log(f"⚠ 网页弹出提示: {msg}")

                            if "1分钟后再试" in msg or "频繁" in msg:
                                self.log("🕒 拦截到【频繁请求】限制弹窗，后台静默等待 62 秒...")
                                for _ in range(62):
                                    if not self.is_running: break
                                    time.sleep(1)
                                self.driver.execute_script("arguments[0].click();", popups[0])
                                self.log("✅ 62秒等待结束，已点击确定，继续操作...")
                                self.simulate_human_delay(1.0, 2.0)
                                continue

                            self.driver.execute_script("arguments[0].click();", popups[0])
                            self.simulate_human_delay(0.5, 1.0)

                            if "验证码" in msg:
                                self.log("验证码识别失败，正在点击图片刷新重试...")
                                try:
                                    yzm_img_element = self.driver.find_element(By.XPATH,
                                                                               '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[6]/div/div/div/a/img')
                                    self.driver.execute_script("arguments[0].click();", yzm_img_element)
                                    self.simulate_human_delay(2.0, 3.0)
                                except:
                                    pass
                                continue
                            else:
                                self.log("检测到非验证码异常，正在刷新网页重新导入文件...")
                                self.driver.get("https://inv-veri.chinatax.gov.cn/fpcygzfw/national-invoice-check")
                                self.simulate_human_delay(2.0, 4.0)
                                try:
                                    file_cy_btn = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(
                                        (By.XPATH, '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[2]/button[2]')))
                                    ActionChains(self.driver).move_to_element(file_cy_btn).pause(
                                        random.uniform(0.5, 1.2)).click().perform()
                                    self.simulate_human_delay(0.8, 1.5)
                                    try:
                                        file_input = self.driver.find_element(By.XPATH,
                                                                              '/html/body/div[6]/div[2]/div/div/div[2]/div[1]/div/div/div[1]/div')
                                        if file_input.tag_name != 'input':
                                            file_input = file_input.find_element(By.XPATH, './/input[@type="file"]')
                                    except:
                                        file_input = self.driver.find_element(By.XPATH, '//input[@type="file"]')
                                    file_input.send_keys(file_path)

                                    self.log("重新输入文件路径，等待系统解析 (最长30秒)...")
                                    try:
                                        WebDriverWait(self.driver, 30, poll_frequency=0.2).until(
                                            lambda d: any(
                                                "成功" in p.text for p in (
                                                        d.find_elements(By.XPATH, '/html/body/div[6]/div') +
                                                        d.find_elements(By.XPATH, '/html/body/div[7]/div') +
                                                        d.find_elements(By.XPATH, '/html/body/div[8]/div')
                                                ) if p.is_displayed()
                                            )
                                        )
                                        self.log("✅ 重新导入成功！准备点击确认...")
                                        time.sleep(0.5)
                                    except Exception:
                                        self.log("❌ 重新导入超过30秒未响应，判断为导入失败，抛弃此次尝试...")
                                        continue

                                    import_btn = WebDriverWait(self.driver, 10).until(
                                        lambda d: (d.find_elements(By.XPATH,
                                                                   '/html/body/div[7]/div[2]/div/div/div[3]/div/button[2]/span') or
                                                   d.find_elements(By.XPATH,
                                                                   '/html/body/div[7]/div[2]/div/div/div[3]/div/button[2]') or
                                                   d.find_elements(By.XPATH, '//button[span[contains(text(), "导入")]]'))
                                    )
                                    self.driver.execute_script("arguments[0].click();", import_btn[0])
                                    self.log("重新导入点击完成，等待验证码生成...")
                                    self.simulate_human_delay(2.0, 3.5)
                                except Exception as e:
                                    self.log(f"重新导入时发生错误: {e}")
                                continue

                        # ================== 5. 处理查验成功并打印 ==================
                        print_btns = self.driver.find_elements(By.XPATH, '//*[@id="print-btn"]')
                        if print_btns:
                            self.log("✅ 查验成功！已找到打印按钮，准备触发原生静默打印保存...")
                            self.simulate_human_delay(1.5, 2.5)

                            # 接收保存结果，如果保存成功才 break
                            is_saved = self._execute_print_and_save(file_path, print_btns[0])
                            if is_saved:
                                break
                            else:
                                raise Exception("静默打印未生成文件，主动抛出异常交由重试机制处理")
                        else:
                            self.log("⚠ 未获取到查验结果 (可能是验证码识别错误)，自动刷新验证码重试...")
                            try:
                                yzm_img_element = self.driver.find_element(By.XPATH,
                                                                           '/html/body/div[1]/div[2]/div/div[1]/div[1]/div[3]/form/div[6]/div/div/div/a/img')
                                self.driver.execute_script("arguments[0].click();", yzm_img_element)
                                self.simulate_human_delay(2.0, 3.0)
                            except:
                                pass
                            continue

                    self.simulate_human_delay(1.0, 2.0)

                except Exception as inner_e:
                    self.log(f"❌ 捕获到网页异常/加载超时: {str(inner_e)[:100]}...")
                    if retry_count < 3:
                        self.log(f"➡ 强制休眠 30 秒防封，随后将该文件移至队列尾部 (当前重试 {retry_count + 1}/3)...")
                        for _ in range(30):
                            if not self.is_running: break
                            time.sleep(1)
                        queue.append((file_path, retry_count + 1))
                    else:
                        self.log(f"⚠️ {os.path.basename(file_path)} 连续 3 次处理失败，已永久放弃该文件。")
                    continue

            self.log("🎉 所有文件处理完毕！")

        except Exception as e:
            self.log(f"运行发生致命级错误: {str(e)}")
        finally:
            self.stop_task()

    # 提取公共保存方法以复用代码
    def _execute_print_and_save(self, file_path, print_btn_element):
        files_before = set(os.listdir(self.res_dir))
        base_name = os.path.basename(file_path)
        name, _ = os.path.splitext(base_name)
        current_time = time.strftime("%Y%m%d%H%M%S")
        new_filename = f"{current_time}-验-{name}.pdf"
        save_path = os.path.abspath(os.path.join(self.res_dir, new_filename))

        css_orientation = "landscape" if "横向" in self.orientation_mode.get() else "portrait"

        try:
            self.driver.execute_script(f"""
                var style = document.createElement('style');
                style.innerHTML = '@media print {{ @page {{ size: {css_orientation} !important; }} * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }} }}';
                document.head.appendChild(style);
            """)
            self.log("等待发票组件(印章/底纹)渲染...")
            time.sleep(2.0)
            # 这里是容易断连的地方，我们将其保护起来
            self.driver.execute_script("arguments[0].click();", print_btn_element)
        except Exception as e:
            self.log(f"⚠ 触发打印时断开连接(Chrome静默打印常见现象)，不影响后台下载，尝试继续侦听...")

        self.log("正在后台静默下载并更名...")

        success_flag = False
        for i in range(20):
            time.sleep(1)
            files_after = set(os.listdir(self.res_dir))
            new_files = files_after - files_before

            if new_files:
                for nf in new_files:
                    if nf.lower().endswith(".pdf"):
                        if nf != new_filename:
                            old_path = os.path.join(self.res_dir, nf)
                            rename_success = False

                            for attempt in range(10):
                                try:
                                    os.rename(old_path, save_path)
                                    self.log(f"✅ 检测到新文件并成功更名: {new_filename}")
                                    rename_success = True
                                    break
                                except PermissionError:
                                    time.sleep(1)
                                except Exception as e:
                                    self.log(f"❌ 更名过程中发生其他错误: {e}")
                                    break

                            if not rename_success:
                                self.log(f"❌ 经过多次尝试，更名依然失败: {nf}")
                        else:
                            self.log(f"✅ 文件已按正确名称保存: {nf}")
                        success_flag = True
                        break
            if success_flag:
                break

        if not success_flag:
            self.log("⚠️ 侦听超时，未检测到新生成的 PDF 文件。")
        else:
            self.simulate_human_delay(1.5, 2.5)
            self.log(f"🎉 成功！文件已静默保存至: {save_path}")

        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.driver.switch_to.window(handles[-1])
                self.driver.close()
                self.driver.switch_to.window(handles[0])
        except Exception:
            pass

        return success_flag


if __name__ == "__main__":
    root = tk.Tk()
    app = TaxInvoiceScraperApp(root)
    root.mainloop()
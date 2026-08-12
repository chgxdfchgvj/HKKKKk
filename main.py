import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import ddddocr


class CaptchaTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("本地验证码测试器 (ddddocr驱动)")
        self.root.geometry("400x450")
        self.root.resizable(False, False)

        # 初始化 ddddocr 引擎 (show_ad=False 用于关闭启动时的广告字符)
        print("正在加载 ddddocr 模型，请稍候...")
        try:
            self.ocr = ddddocr.DdddOcr(show_ad=False)
        except TypeError:
            # 兼容老版本 ddddocr
            self.ocr = ddddocr.DdddOcr()
        print("模型加载完成！")

        self.image_path = None

        # --- UI 组件搭建 ---

        # 1. 顶部提示标签
        self.lbl_title = tk.Label(root, text="上传验证码图片进行本地识别测试", font=("微软雅黑", 12, "bold"))
        self.lbl_title.pack(pady=15)

        # 2. 图片预览区域
        self.canvas = tk.Canvas(root, width=200, height=100, bg="#f0f0f0", relief="sunken", bd=2)
        self.canvas.pack(pady=10)
        self.canvas.create_text(100, 50, text="暂无图片\n点击下方按钮上传", justify="center", fill="#888888")

        # 3. 上传按钮
        self.btn_upload = tk.Button(root, text="📁 选择验证码图片", command=self.upload_image, width=20,
                                    font=("微软雅黑", 10))
        self.btn_upload.pack(pady=10)

        # 4. 识别按钮
        self.btn_recognize = tk.Button(root, text="⚡ 开始识别", command=self.recognize_captcha, width=20,
                                       font=("微软雅黑", 10, "bold"), bg="#4CAF50", fg="white")
        self.btn_recognize.pack(pady=10)

        # 5. 结果显示区域
        self.lbl_result_title = tk.Label(root, text="识别结果：", font=("微软雅黑", 10))
        self.lbl_result_title.pack(pady=5)

        self.txt_result = tk.Text(root, height=2, width=25, font=("微软雅黑", 14, "bold"), fg="red")
        self.txt_result.pack()

    def upload_image(self):
        """处理图片上传与预览"""
        file_path = filedialog.askopenfilename(
            title="选择验证码图片",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if file_path:
            self.image_path = file_path
            self.show_image(file_path)
            # 清空上次的识别结果
            self.txt_result.delete(1.0, tk.END)

    def show_image(self, path):
        """在 Canvas 中渲染图片"""
        try:
            img = Image.open(path)
            # 缩放图片以适应预览框 (保持比例)
            img.thumbnail((190, 90))
            self.tk_img = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            # 将图片居中放置
            self.canvas.create_image(100, 50, anchor="center", image=self.tk_img)
        except Exception as e:
            messagebox.showerror("错误", f"图片加载失败: {e}")

    def recognize_captcha(self):
        """调用 ddddocr 进行识别"""
        if not self.image_path:
            messagebox.showwarning("提示", "请先上传一张验证码图片！")
            return

        self.btn_recognize.config(text="识别中...", state=tk.DISABLED)
        self.root.update()

        try:
            # 读取图片字节流
            with open(self.image_path, 'rb') as f:
                img_bytes = f.read()

            # 核心打码逻辑
            res = self.ocr.classification(img_bytes)

            # 显示结果
            self.txt_result.delete(1.0, tk.END)
            self.txt_result.insert(tk.END, res)

        except Exception as e:
            messagebox.showerror("识别错误", f"发生错误: {e}")
        finally:
            self.btn_recognize.config(text="⚡ 开始识别", state=tk.NORMAL)


if __name__ == "__main__":
    # 创建主窗口
    root = tk.Tk()
    # 将窗口置于屏幕中央的简单计算
    window_width = 400
    window_height = 450
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    app = CaptchaTesterApp(root)
    root.mainloop()
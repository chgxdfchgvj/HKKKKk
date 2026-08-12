import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk
import os


class ColorTextMaskExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("特定颜色文字区域提取工具 (图像处理版)")
        self.root.geometry("1000x700")

        # 内部变量存储 OpenCV 格式图像 (BGR)
        self.original_cv_image = None
        self.processed_cv_image = None
        self.color_var = tk.StringVar(value="blue")  # 默认选择蓝色

        self.setup_ui()

    def setup_ui(self):
        # --- 顶部控制面板 ---
        control_frame = tk.Frame(self.root, pady=15, bg="#f0f0f0")
        control_frame.pack(side=tk.TOP, fill=tk.X)

        # 1. 导入按钮
        btn_load = tk.Button(control_frame, text="📂 导入原图", command=self.load_image, font=("Microsoft YaHei", 10))
        btn_load.pack(side=tk.LEFT, padx=20)

        # 2. 颜色选择区域
        tk.Label(control_frame, text="目标文字颜色:", bg="#f0f0f0", font=("Microsoft YaHei", 10, "bold")).pack(
            side=tk.LEFT, padx=(30, 10))

        rb_blue = tk.Radiobutton(control_frame, text="蓝色 (Blue)", variable=self.color_var, value="blue", bg="#f0f0f0",
                                 font=("Microsoft YaHei", 10))
        rb_blue.pack(side=tk.LEFT)

        rb_red = tk.Radiobutton(control_frame, text="红色 (Red)", variable=self.color_var, value="red", bg="#f0f0f0",
                                font=("Microsoft YaHei", 10))
        rb_red.pack(side=tk.LEFT)

        # 3. 处理按钮
        btn_process = tk.Button(control_frame, text="⚙️ 提取颜色区域", command=self.process_image, bg="#aed6f1",
                                font=("Microsoft YaHei", 10, "bold"))
        btn_process.pack(side=tk.LEFT, padx=40)

        # 4. 保存按钮
        btn_save = tk.Button(control_frame, text="💾 保存处理结果", command=self.save_image, bg="#f9e79f",
                             font=("Microsoft YaHei", 10))
        btn_save.pack(side=tk.LEFT, padx=10)

        # --- 中间图像显示面板 (左右对比) ---
        display_frame = tk.Frame(self.root, bg="white")
        display_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 固定最大显示尺寸以防撑爆窗口
        self.max_display_size = (480, 600)

        # 左侧：原图显示区
        left_frame = tk.Frame(display_frame, bg="white")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(left_frame, text="原始图像", font=("Microsoft YaHei", 12, "bold"), bg="white").pack(pady=5)

        self.canvas_orig = tk.Canvas(left_frame, bg="#e0e0e0", highlightthickness=1, highlightbackground="gray")
        self.canvas_orig.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_orig_handle = None  # 保持引用，防止垃圾回收

        # 右侧：处理结果显示区
        right_frame = tk.Frame(display_frame, bg="white")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        tk.Label(right_frame, text="提取结果蒙版 (二值化)", font=("Microsoft YaHei", 12, "bold"), bg="white").pack(
            pady=5)

        self.canvas_processed = tk.Canvas(right_frame, bg="#e0e0e0", highlightthickness=1, highlightbackground="gray")
        self.canvas_processed.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.image_processed_handle = None  # 保持引用

    def load_image(self):
        """导入图片并显示"""
        file_path = filedialog.askopenfilename(
            title="选择要处理的图片",
            filetypes=[("图像文件", "*.jpg *.jpeg *.png *.bmp *.webp")]
        )
        if not file_path:
            return

        # 使用 OpenCV 读取 BGR 图像
        self.original_cv_image = cv2.imread(file_path)

        if self.original_cv_image is None:
            messagebox.showerror("错误", "无法读取该图片文件。")
            return

        # 清空之前的处理结果
        self.processed_cv_image = None
        self.canvas_processed.delete("all")

        # 将 OpenCV 格式转换为 UI 可显示格式并展示
        self.set_display_image(self.original_cv_image, self.canvas_orig, "image_orig_handle")

    def process_image(self):
        """核心处理逻辑：根据颜色提取文字区域蒙版"""
        if self.original_cv_image is None:
            messagebox.showwarning("提示", "请先导入一张原图！")
            return

        selected_color = self.color_var.get()

        # 1. 转换到 HSV 色彩空间 (对颜色分量更敏感)
        hsv_img = cv2.cvtColor(self.original_cv_image, cv2.COLOR_BGR2HSV)

        # 2. 定义颜色阈值范围 (HSV 空间中的上下限)
        # OpenCV 的 HSV 范围: H[0-179], S[0-255], V[0-255]
        if selected_color == "blue":
            # 蓝色大致范围 (需根据实际图片调整，这里给出一个通用范围)
            lower_bounds = np.array([100, 50, 50])  # Hue~200, 中等饱和度, 中等亮度
            upper_bounds = np.array([130, 255, 255])
            mask = cv2.inRange(hsv_img, lower_bounds, upper_bounds)

        elif selected_color == "red":
            # 红色在 HSV 空间中跨越 0 度，需要合并两个区间
            # 区间 1 (低 Hue)
            lower_red_1 = np.array([0, 50, 50])
            upper_red_1 = np.array([10, 255, 255])
            mask1 = cv2.inRange(hsv_img, lower_red_1, upper_red_1)

            # 区间 2 (高 Hue)
            lower_red_2 = np.array([170, 50, 50])
            upper_red_2 = np.array([180, 255, 255])
            mask2 = cv2.inRange(hsv_img, lower_red_2, upper_red_2)

            # 合并两个掩码
            mask = cv2.bitwise_or(mask1, mask2)

        # 3. 处理结果说明：
        # 此时 mask 是一个二值图像：
        # 只有符合该颜色的区域是白色的 (255)，其他区域全黑 (0)。

        # 通常提取出的文本为了方便观察或 OCR，更习惯“白底黑字”。
        # 我们在这里进行黑白反转。
        final_processed = cv2.bitwise_not(mask)

        # 存储 OpenCV 结果
        self.processed_cv_image = final_processed

        # 在 UI 中显示处理结果 (灰度图转换格式)
        self.set_display_image(self.processed_cv_image, self.canvas_processed, "image_processed_handle", is_gray=True)

    def save_image(self):
        """保存处理后的结果"""
        if self.processed_cv_image is None:
            messagebox.showwarning("提示", "没有可保存的处理结果，请先执行提取！")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 图像", "*.png"), ("JPEG 图像", "*.jpg")],
            title="保存提取结果蒙版"
        )
        if not file_path:
            return

        # 使用 OpenCV 保存图像
        success = cv2.imwrite(file_path, self.processed_cv_image)
        if success:
            messagebox.showinfo("成功", f"结果已保存至:\n{file_path}")
        else:
            messagebox.showerror("错误", "图片保存失败。")

    def set_display_image(self, cv_img, target_canvas, handle_attr_name, is_gray=False):
        """将 OpenCV 图像适配并在 Tkinter Canvas 中显示"""

        # 1. 适配色彩空间
        if is_gray:
            # 灰度图无需颜色转换
            pil_img_orig = Image.fromarray(cv_img)
        else:
            # 转换为 RGB 供 Pillow 使用
            img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            pil_img_orig = Image.fromarray(img_rgb)

        # 2. 缩放适配 UI
        # 获取原图尺寸
        w, h = pil_img_orig.size
        # 计算缩放比例
        ratio = min(self.max_display_size[0] / w, self.max_display_size[1] / h)
        if ratio < 1.0:
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            pil_img_res = pil_img_orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            pil_img_res = pil_img_orig

        # 3. 转换为 Tkinter 可显示格式
        tk_img = ImageTk.PhotoImage(image=pil_img_res)

        # 4. 更新 Canvas 显示，并保留引用防止垃圾回收
        target_canvas.delete("all")  # 清空旧内容
        # 将图像居中放置在 Canvas
        target_canvas.create_image(
            self.max_display_size[0] // 2,
            self.max_display_size[1] // 2,
            anchor=tk.CENTER,
            image=tk_img
        )

        # 在类的特定属性中存储引用，非常重要！
        setattr(self, handle_attr_name, tk_img)


if __name__ == "__main__":
    # 创建 Tkinter 主窗口
    root = tk.Tk()
    # 实例化应用程序
    app = ColorTextMaskExtractorApp(root)
    # 进入主事件循环
    root.mainloop()
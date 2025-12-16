from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

# 1. 初始化 OCR 引擎
# use_textline_orientation=True: 自动处理文字倾斜
# lang='ch': 设置为中文模式
ocr = PaddleOCR(use_textline_orientation=True, lang="ch")


def recognize_skills(image_path: Path, output_dir: Path):
    # 2. 读取图片
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"图片读取失败: {image_path}")
        return []

    # 获取图片文件名（不含路径）
    image_name = image_path.name
    image_name_no_ext = image_path.stem

    h, w, _ = img.shape

    # 3. 定义 ROI (感兴趣区域) - 这一步很关键
    # 这里根据你的截图做了估算，你需要根据实际情况微调
    # 目标是：涵盖 "力量提升", "攻击提升", "流转" 这几行
    x_start = int(w * 0.76)  # 约在右侧 3/4 处
    y_start = int(h * 0.36)  # 约在上方 1/3 处
    roi_w = int(w * 0.15)  # 宽度不用太大，刚好包住字
    roi_h = int(h * 0.20)  # 高度包住三行字

    # 裁剪图片
    roi = img[y_start : y_start + roi_h, x_start : x_start + roi_w]

    # --- 图像预处理 (优化识别率) ---
    # 游戏字体有时较小，放大图片通常能显著提高准确率
    roi = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # 转为灰度图 (PaddleOCR 其实可以直接吃彩色图，但灰度通常更稳)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 二值化 (可选，如果背景干扰太大才用，终末地这个UI很干净，通常不需要)
    # _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # 4. 进行识别
    # 将灰度图转换为3通道图像（PaddleOCR需要3通道输入）
    gray_3channel = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    result = ocr.predict(gray_3channel)

    # 5. 输出结果
    print(f"\n--- 处理图片: {image_name} ---")
    print(f"--- 识别区域: x={x_start}, y={y_start}, w={roi_w}, h={roi_h} ---")

    found_texts = []
    result_text = []
    if result:
        for ocr_result in result:
            # 获取识别到的文本和对应的置信度
            texts = ocr_result.get("rec_texts", [])
            scores = ocr_result.get("rec_scores", [])

            if texts and scores:
                for text, score in zip(texts, scores):
                    print(f"识别到: {text} (置信度: {score:.2f})")
                    found_texts.append(text)
                    result_text.append(f"{text} (置信度: {score:.2f})")
            else:
                print("未识别到文字，请调整坐标范围。")
                result_text.append("未识别到文字，请调整坐标范围。")
    else:
        print("未识别到文字，请调整坐标范围。")
        result_text.append("未识别到文字，请调整坐标范围。")

    # 调试：保存裁剪出来的图片看看对不对
    debug_image_path = output_dir / f"debug_roi_{image_name_no_ext}.jpg"
    cv2.imwrite(str(debug_image_path), gray)
    print(f"已保存调试图片: {debug_image_path}")

    # 保存识别结果到文本文件
    result_file_path = output_dir / f"result_{image_name_no_ext}.txt"
    with open(result_file_path, "w", encoding="utf-8") as f:
        f.write(f"图片: {image_name}\n")
        f.write(f"识别区域: x={x_start}, y={y_start}, w={roi_w}, h={roi_h}\n")
        f.write("\n识别结果:\n")
        for text in result_text:
            f.write(f"{text}\n")
    print(f"已保存识别结果: {result_file_path}")

    return found_texts


# 运行批量处理
if __name__ == "__main__":
    # 设置输出文件夹名称
    output_dir = Path("ocr_results")

    # 创建输出文件夹（如果不存在）
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"创建输出文件夹: {output_dir}")
    else:
        print(f"使用现有输出文件夹: {output_dir}")

    # 获取根目录内的所有图片文件
    # 支持的图片格式：jpg, jpeg, png, bmp
    image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp"]
    image_files: list[Path] = []

    for ext in image_extensions:
        image_files.extend(Path().glob(ext))
    if not image_files:
        print("在根目录下未找到图片文件")
    else:
        print(f"找到 {len(image_files)} 个图片文件，开始批量处理...")

        # 为每个图片执行OCR识别
        for image_path in image_files:
            recognize_skills(image_path, output_dir)

        print(f"\n批量处理完成！所有结果已保存到: {output_dir}")

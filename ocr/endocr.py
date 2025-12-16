import cv2
from paddleocr import PaddleOCR
import numpy as np
import os
import glob
import re
import paddle

# 1. 初始化 OCR 引擎
# Check if GPU is available and use it


# Initialize OCR with optimized settings
ocr = PaddleOCR(use_textline_orientation=True, lang="ch", cpu_threads=4)

def recognize_skills(image_path, roi_coords=None):
    """
    识别图片中的技能数值

    参数:
    image_path (str): 图片文件路径
    roi_coords (tuple, optional): 区域-of-interest 坐标 (x_start, y_start, roi_w, roi_h)

    返回:
    dict: 包含技能名称和对应数值的字典
    """
    # 1. 读取图片
    img = cv2.imread(image_path)
    if img is None:
        return {} # Return empty dict on error

    # 2. 定义 ROI
    if roi_coords:
        x_start, y_start, roi_w, roi_h = roi_coords
    else:
        # Default hardcoded ROI
        x_start = 1482
        y_start = 357
        roi_w = 388
        roi_h = 178

    # 裁剪图片
    roi = img[y_start:y_start+roi_h, x_start:x_start+roi_w]

    # --- 图像预处理 ---
    roi = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray_3channel = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    
    # --- OCR 识别 ---
    result = ocr.predict(gray_3channel)

    # --- 结果处理 ---
    found_texts = []
    if result and isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict):
        ocr_output_dict = result[0]
        texts = ocr_output_dict.get('rec_texts', [])
        scores = ocr_output_dict.get('rec_scores', [])
        polys = ocr_output_dict.get('rec_polys', [])

        if texts and scores and polys:
            combined_results = sorted(zip(polys, texts, scores), key=lambda item: item[0][0][1])
            for poly, text, score in combined_results:
                cleaned_text = text.replace('|', '')
                found_texts.append(cleaned_text)

    # --- 技能提取 ---
    skill_values = {}
    temp_skill_values = {}
    for i, text in enumerate(found_texts):
        is_value = re.fullmatch(r'[+-]?\d+', text)
        if is_value and i + 1 < len(found_texts):
            next_text = found_texts[i+1]
            if not re.fullmatch(r'[+-]?\d+', next_text):
                temp_skill_values[next_text] = is_value.group(0)

    for i, text in enumerate(found_texts):
        if not re.fullmatch(r'[+-]?\d+', text):
            if i + 1 < len(found_texts):
                next_text = found_texts[i+1]
                if re.fullmatch(r'[+-]?\d+', next_text):
                    skill_values[text] = next_text

    for keyword, value in temp_skill_values.items():
        if keyword not in skill_values:
            skill_values[keyword] = value
            
    return skill_values
import streamlit as st
import requests
import base64
import json
import time
from PIL import Image
from io import BytesIO

# --- 页面基础配置 ---
st.set_page_config(
    page_title="WUHU AI Studio",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 全局常量与映射 ---
MODEL_MAP = {
    "标准画质 (2K) - Gemini 3 Pro": "gemini-3-pro-image-preview-2k",
    "超高清 (4K) - Gemini 3 Pro": "gemini-3-pro-image-preview-4k",
    "极速版 (Flash) - Gemini 2.5": "gemini-2.5-flash-image"
}

RATIO_MAP = {
    "16:9 (横屏 Landscape)": "16:9",
    "4:3 (横屏 Landscape)": "4:3",
    "1:1 (方形 Square)": "1:1",
    "3:4 (竖屏 Portrait)": "3:4",
    "9:16 (竖屏 Portrait)": "9:16"
}

# --- 核心功能函数 ---

def process_uploaded_images(uploaded_files):
    """处理上传图片：转RGB -> 压缩JPEG -> Base64"""
    processed_images = []
    
    if not uploaded_files:
        return []

    # 限制最多4张
    files_to_process = uploaded_files[:4]
    
    for uploaded_file in files_to_process:
        try:
            image = Image.open(uploaded_file)
            
            # 修正模式 (RGBA -> RGB)
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            
            # 缩放限制
            image.thumbnail((1024, 1024))
            
            # 转字节流 (JPEG 压缩)
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            
            # Base64 编码
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            full_b64 = f"data:image/jpeg;base64,{img_str}"
            
            processed_images.append(full_b64)
            
        except Exception as e:
            st.error(f"图片处理失败 {uploaded_file.name}: {e}")
            
    return processed_images

def call_translation_api(api_key, text):
    """调用 API 进行翻译"""
    url = "https://newapi.pockgo.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    payload = {
        "model": "gemini-2.5-flash", 
        "messages": [
            {
                "role": "system", 
                "content": "You are a professional prompt engineer translator. Translate the following Chinese text into detailed English image generation prompts. Only output the translated English text, no explanations."
            },
            {"role": "user", "content": text}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        else:
            st.error(f"翻译失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"翻译出错: {e}")
        return None

def generate_image(api_key, prompt, base64_imgs, model_id, ratio):
    """调用生图 API"""
    url = "https://newapi.pockgo.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    content_list = [{"type": 'text', "text": prompt}]
    for b64_img in base64_imgs:
        content_list.append({"type": 'image_url', "image_url": {"url": b64_img}})

    payload = {
        "extra_body": {"imageConfig": {"aspectRatio": ratio}},
        "model": model_id,
        "messages": [
            {"role": "system", "content": json.dumps({"imageConfig": {"aspectRatio": ratio}})},
            {"role": "user", "content": content_list}
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # 提取 URL (Markdown 或 纯链接)
            import re
            match = re.search(r'!\[.*?\]\((.*?)\)', content)
            if match:
                return match.group(1)
            elif content.startswith("http"):
                return content.split()[0]
            else:
                return None
        else:
            return f"Error {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return f"Exception: {str(e)}"

# --- 侧边栏 UI ---
with st.sidebar:
    st.title("🎛️ 设置面板")
    
    st.markdown("### 1. 连接设置")
    api_key = st.text_input("API Key", type="password", placeholder="sk-...", help="请输入您的 API Key")
    
    st.markdown("---")
    st.markdown("### 2. 参考图片")
    uploaded_files = st.file_uploader(
        "上传参考图 (最多4张)", 
        type=['png', 'jpg', 'jpeg', 'webp'], 
        accept_multiple_files=True
    )
    
    # 预览上传的图片
    if uploaded_files:
        st.caption(f"已选择 {len(uploaded_files)}/4 张")
        cols = st.columns(2)
        for i, file in enumerate(uploaded_files[:4]):
            cols[i % 2].image(file, use_container_width=True)
            
    st.markdown("---")
    st.markdown("### 3. 模型参数")
    
    model_name = st.selectbox("选择模型", list(MODEL_MAP.keys()))
    ratio_name = st.selectbox("图片比例", list(RATIO_MAP.keys()))
    image_count = st.slider("生成张数", min_value=1, max_value=8, value=1)

# --- 主界面 UI ---
st.title("WUHU AI Studio 🎨")
st.markdown("专业的 AI 绘图工作台")

# 初始化 session state 用于存储提示词
if 'prompt_text' not in st.session_state:
    st.session_state.prompt_text = "一只在太空中吃香蕉的纳米猴子"

# 提示词区域
col1, col2 = st.columns([4, 1])
with col1:
    prompt_input = st.text_area("提示词 / Prompt", value=st.session_state.prompt_text, height=150, key="input_prompt")
with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    if st.button("🌐 翻译成英文", use_container_width=True):
        if not api_key:
            st.warning("请先在左侧输入 API Key")
        else:
            with st.spinner("正在翻译..."):
                trans_text = call_translation_api(api_key, prompt_input)
                if trans_text:
                    st.session_state.prompt_text = trans_text
                    st.rerun() # 刷新页面以更新文本框

# 生成按钮
if st.button("✨ 开始生成 / Generate", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ 错误：请在左侧侧边栏输入 API Key")
    elif not uploaded_files:
        st.error("❌ 错误：请至少上传一张参考图片")
    else:
        # 准备数据
        base64_imgs = process_uploaded_images(uploaded_files)
        selected_model = MODEL_MAP[model_name]
        selected_ratio = RATIO_MAP[ratio_name]
        
        # 创建结果展示区
        result_container = st.container()
        
        with result_container:
            st.divider()
            st.subheader("生成结果")
            
            # 使用列来展示结果，每行显示2张
            result_cols = st.columns(2)
            
            # 进度指示器
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(image_count):
                status_text.text(f"正在生成第 {i+1} / {image_count} 张图片... (排队中)")
                
                # 延时策略
                if i > 0:
                    time.sleep(2)
                
                # 调用 API
                img_result = generate_image(api_key, prompt_input, base64_imgs, selected_model, selected_ratio)
                
                # 显示结果
                target_col = result_cols[i % 2] # 左右交替显示
                
                if img_result and img_result.startswith("http"):
                    target_col.success(f"图片 #{i+1} 生成成功")
                    target_col.image(img_result, use_container_width=True)
                    # 提供下载链接模拟
                    target_col.markdown(f"[📥 点击下载原图]({img_result})")
                else:
                    target_col.error(f"图片 #{i+1} 生成失败")
                    target_col.code(img_result)
                
                # 更新进度条
                progress_bar.progress((i + 1) / image_count)

            status_text.text("✅ 所有任务已完成！")
            progress_bar.empty()

# 页脚
st.markdown("---")
st.markdown("© 2025 WUHU AI Studio | Powered by Gemini Pro Vision")
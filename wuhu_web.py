import streamlit as st
import streamlit.components.v1 as components
import requests
import base64
import json
import time
from PIL import Image
from io import BytesIO
from datetime import datetime

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

# --- 初始化 Session State ---
if 'prompt_text' not in st.session_state:
    st.session_state.prompt_text = "一只在太空中吃香蕉的纳米猴子"

if 'history' not in st.session_state:
    st.session_state.history = []

# --- 核心功能函数 ---

def process_uploaded_images(uploaded_files):
    """处理上传图片：转RGB -> 压缩JPEG -> Base64"""
    processed_images = []
    
    if not uploaded_files:
        return []

    files_to_process = uploaded_files[:4]
    
    for uploaded_file in files_to_process:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            image.thumbnail((1024, 1024))
            buffered = BytesIO()
            image.save(buffered, format="JPEG", quality=85)
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
                "content": "You are a precise translator. Translate the following Chinese text directly into English. Do not add, omit, or modify any meaning. Do not expand into a detailed prompt. Only output the translated English text."
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
            return None
    except Exception as e:
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

def trigger_auto_download(image_url, index):
    """后台下载图片并触发浏览器自动下载"""
    try:
        r = requests.get(image_url)
        if r.status_code == 200:
            b64_data = base64.b64encode(r.content).decode()
            filename = f"wuhu_gen_{int(time.time())}_{index+1}.png"
            js_code = f"""
                <script>
                (function() {{
                    var a = document.createElement('a');
                    a.href = "data:image/png;base64,{b64_data}";
                    a.download = "{filename}";
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }})();
                </script>
            """
            components.html(js_code, height=0)
    except Exception as e:
        st.toast(f"自动下载失败: {e}", icon="⚠️")

# --- 回调函数 (修复报错的关键) ---
def handle_translation():
    # 从 Session State 获取输入框的值
    current_key = st.session_state.get("sidebar_api_key")
    current_text = st.session_state.get("input_prompt")
    
    if not current_key:
        st.toast("请先在左侧输入 API Key", icon="⚠️")
        return
        
    if not current_text:
        st.toast("提示词为空", icon="⚠️")
        return

    # 执行翻译
    trans_text = call_translation_api(current_key, current_text)
    
    if trans_text:
        # 在回调中直接修改 Session State 是安全的，因为组件还没重新渲染
        st.session_state.input_prompt = trans_text
        st.session_state.prompt_text = trans_text
        st.toast("翻译成功！", icon="✅")
    else:
        st.toast("翻译失败，请检查网络或 Key", icon="❌")

# --- 侧边栏 UI ---
with st.sidebar:
    st.title("🎛️ 设置面板")
    
    st.markdown("### 1. 连接设置")
    # 给 API Key 加上 key 参数，方便在回调中获取
    api_key = st.text_input("API Key", type="password", placeholder="sk-...", help="请输入您的 API Key", key="sidebar_api_key")
    
    st.markdown("---")
    st.markdown("### 2. 参考图片")
    uploaded_files = st.file_uploader(
        "上传参考图 (最多4张)", 
        type=['png', 'jpg', 'jpeg', 'webp'], 
        accept_multiple_files=True
    )
    
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
    
    auto_dl = st.checkbox("生成后自动下载图片", value=True)
    
    st.markdown("---")
    if st.button("🗑️ 清除历史记录"):
        st.session_state.history = []
        st.rerun()

# --- 主界面 UI ---
st.title("WUHU AI Studio 🎨")
st.markdown("专业的 AI 绘图工作台")

col1, col2 = st.columns([4, 1])
with col1:
    # 绑定 input_prompt 到 session_state
    prompt_input = st.text_area("提示词 / Prompt", value=st.session_state.prompt_text, height=150, key="input_prompt")
with col2:
    st.write("") 
    st.write("") 
    # 使用回调函数 on_click
    st.button("🌐 翻译成英文", use_container_width=True, on_click=handle_translation)

# 生成按钮
if st.button("✨ 开始生成 / Generate", type="primary", use_container_width=True):
    if not api_key:
        st.error("❌ 错误：请在左侧侧边栏输入 API Key")
    elif not uploaded_files:
        st.error("❌ 错误：请至少上传一张参考图片")
    else:
        base64_imgs = process_uploaded_images(uploaded_files)
        selected_model = MODEL_MAP[model_name]
        selected_ratio = RATIO_MAP[ratio_name]
        
        result_container = st.container()
        
        with result_container:
            st.divider()
            st.subheader("🚀 正在生成...")
            result_cols = st.columns(2)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i in range(image_count):
                status_text.text(f"正在生成第 {i+1} / {image_count} 张图片... (排队中)")
                if i > 0:
                    time.sleep(2)
                
                img_result = generate_image(api_key, prompt_input, base64_imgs, selected_model, selected_ratio)
                target_col = result_cols[i % 2]
                
                if img_result and img_result.startswith("http"):
                    target_col.success(f"图片 #{i+1} 生成成功")
                    target_col.image(img_result, use_container_width=True)
                    target_col.markdown(f"[📥 手动下载]({img_result})")
                    
                    if auto_dl:
                        trigger_auto_download(img_result, i)
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    st.session_state.history.append({
                        "url": img_result,
                        "prompt": prompt_input,
                        "time": timestamp,
                        "model": model_name,
                        "ratio": ratio_name
                    })
                else:
                    target_col.error(f"图片 #{i+1} 生成失败")
                    target_col.code(img_result)
                
                progress_bar.progress((i + 1) / image_count)

            status_text.text("✅ 所有任务已完成！")
            progress_bar.empty()
            time.sleep(1)

# --- 历史记录展示区 ---
if st.session_state.history:
    st.divider()
    st.subheader(f"🕒 历史记录 (本次会话: {len(st.session_state.history)} 张)")
    st.caption("注意：刷新网页后历史记录将会清空，请及时保存图片。")
    
    reversed_history = st.session_state.history[::-1]
    hist_cols = st.columns(3)
    for i, item in enumerate(reversed_history):
        col = hist_cols[i % 3]
        with col:
            with st.container(border=True):
                st.image(item['url'], use_container_width=True)
                st.markdown(f"**时间**: {item['time']}")
                with st.expander("查看详情"):
                    st.text(f"模型: {item['model']}")
                    st.text(f"比例: {item['ratio']}")
                    st.text_area("提示词", item['prompt'], height=70, disabled=True)
                st.markdown(f"[📥 下载]({item['url']})")

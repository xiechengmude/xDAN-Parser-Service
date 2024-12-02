import os
import time
import argparse
from typing import List, Dict
import PyPDF2
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting

def setup_vertex_ai():
    """初始化 Vertex AI"""
    project_id = "elated-bison-417808"
    location = "us-central1"
    vertexai.init(project=project_id, location=location)

def read_pdf_pages(pdf_path: str) -> Dict[int, str]:
    """
    读取PDF文件并按页提取文本
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        Dict[int, str]: 页码和对应的文本内容的字典
    """
    try:
        pages_content = {}
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            print(f"PDF总页数: {total_pages}")
            
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text.strip():  # 只保存非空页面
                    pages_content[page_num + 1] = text
                    
        return pages_content
    except Exception as e:
        print(f"读取PDF文件时出错: {e}")
        return {}

def analyze_text_with_gemini(text: str, page_num: int) -> str:
    """
    使用 Gemini Pro 模型分析文本
    
    Args:
        text: 要分析的文本
        page_num: 页码
    
    Returns:
        str: 分析结果
    """
    try:
        # 配置安全设置
        safety_settings = [
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
            SafetySetting(
                category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=SafetySetting.HarmBlockThreshold.OFF
            ),
        ]

        # 配置生成参数
        generation_config = {
            "max_output_tokens": 2048,  # 减小token数以避免限制
            "temperature": 0.8,
            "top_p": 0.8,
        }

        # 初始化模型
        model = GenerativeModel(
            "gemini-1.5-flash-002",
            safety_settings=safety_settings,
            generation_config=generation_config
        )

        # 启动对话
        chat = model.start_chat()
        
        prompt = f"""
        请分析以下文本内容（第{page_num}页），提供主要内容的摘要：
        
        {text}
        """
        
        response = chat.send_message(prompt)
        return response.text

    except Exception as e:
        print(f"使用 Gemini 分析时出错: {e}")
        return f"第{page_num}页分析失败: {str(e)}"

def analyze_pdf_with_gemini(pdf_path: str) -> Dict[int, str]:
    """
    逐页分析PDF文档
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        Dict[int, str]: 每页的分析结果
    """
    # 读取PDF内容
    pages_content = read_pdf_pages(pdf_path)
    if not pages_content:
        return {"error": "无法读取PDF文件或文件为空"}

    # 存储每页的分析结果
    analysis_results = {}
    
    # 逐页分析
    for page_num, content in pages_content.items():
        print(f"\n正在分析第 {page_num} 页...")
        
        # 添加延迟以避免触发限制
        if page_num > 1:
            time.sleep(2)  # 每页之间添加2秒延迟
            
        result = analyze_text_with_gemini(content, page_num)
        analysis_results[page_num] = result

    return analysis_results

def main():
    parser = argparse.ArgumentParser(description='PDF文档分析工具')
    parser.add_argument('--pdf_path', default='docs/pdf/example.pdf', help='PDF文件路径')
    args = parser.parse_args()
    
    # 初始化 Vertex AI
    setup_vertex_ai()
    
    # 分析PDF
    print("开始分析PDF文件...")
    results = analyze_pdf_with_gemini(args.pdf_path)
    
    # 输出结果
    if results:
        if "error" in results:
            print(f"\n错误: {results['error']}")
        else:
            print("\n分析结果:")
            for page_num, analysis in sorted(results.items()):
                print(f"\n=== 第 {page_num} 页分析结果 ===")
                print(analysis)
    else:
        print("分析过程中出现错误")

if __name__ == "__main__":
    main()

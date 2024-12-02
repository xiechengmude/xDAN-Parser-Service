import os
import json
import argparse
from typing import Dict, List, Optional
from pathlib import Path
import tempfile

# Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig, Image as VertexImage, SafetySetting

# PDF处理
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.text import partition_text
from unstructured.documents.elements import (
    Text, Title, NarrativeText, ListItem, Table, Image
)

# 图像处理
from pdf2image import convert_from_path
from PIL import Image as PILImage
import pytesseract

def setup_vertex_ai():
    """初始化 Vertex AI"""
    project_id = "elated-bison-417808"
    location = "us-central1"
    vertexai.init(project=project_id, location=location)

def process_with_unstructured(pdf_path: str) -> List[Dict]:
    """
    使用 unstructured 处理 PDF，保留布局信息
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        List[Dict]: 每页的结构化内容
    """
    elements = partition_pdf(
        pdf_path,
        include_page_breaks=True,
        include_metadata=True,
        strategy="hi_res"
    )
    
    pages_content = []
    current_page = []
    current_page_num = 1
    
    for element in elements:
        # 检查是否是新页面
        if hasattr(element, 'metadata'):
            page_num = element.metadata.get('page_number', current_page_num)
            if page_num > current_page_num and current_page:
                pages_content.append({
                    'page_number': current_page_num,
                    'content': current_page
                })
                current_page = []
                current_page_num = page_num
        
        # 处理不同类型的元素
        element_data = {
            'type': element.__class__.__name__,
            'text': str(element),
            'metadata': {}
        }
        
        # 提取元数据
        if hasattr(element, 'metadata'):
            element_data['metadata'] = {
                'coordinates': element.metadata.get('coordinates', None),
                'page_number': element.metadata.get('page_number', None),
                'font_info': element.metadata.get('font_info', None)
            }
        
        # 特殊处理表格
        if isinstance(element, Table):
            element_data['table_data'] = {
                'rows': len(element.metadata.get('text_as_html', '').split('</tr>')),
                'html': element.metadata.get('text_as_html', '')
            }
        
        # 特殊处理图片
        if isinstance(element, Image):
            element_data['image_data'] = {
                'size': element.metadata.get('image_size', None),
                'format': element.metadata.get('image_format', None)
            }
        
        current_page.append(element_data)
    
    # 添加最后一页
    if current_page:
        pages_content.append({
            'page_number': current_page_num,
            'content': current_page
        })
    
    return pages_content

def process_with_pdf2image(pdf_path: str, output_dir: str) -> List[Dict]:
    """
    将 PDF 转换为图片并进行处理
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
    
    Returns:
        List[Dict]: 每页的处理结果
    """
    # 创建临时目录存储图片
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # 转换PDF为图片
    images = convert_from_path(pdf_path)
    pages_content = []
    
    for i, image in enumerate(images, start=1):
        # 保存图片
        image_path = os.path.join(images_dir, f'page_{i}.png')
        image.save(image_path, 'PNG')
        
        # 获取图片尺寸
        width, height = image.size
        
        # OCR提取文本
        text = pytesseract.image_to_string(image, lang='chi_sim+eng')
        
        # 获取详细布局信息
        layout_data = pytesseract.image_to_data(image, lang='chi_sim+eng', output_type=pytesseract.Output.DICT)
        
        # 整理OCR结果
        text_elements = []
        for j in range(len(layout_data['text'])):
            if layout_data['text'][j].strip():
                text_elements.append({
                    'text': layout_data['text'][j],
                    'confidence': layout_data['conf'][j],
                    'position': {
                        'x': layout_data['left'][j],
                        'y': layout_data['top'][j],
                        'width': layout_data['width'][j],
                        'height': layout_data['height'][j]
                    }
                })
        
        page_content = {
            'page_number': i,
            'image_path': image_path,
            'size': {'width': width, 'height': height},
            'text_elements': text_elements,
            'full_text': text
        }
        
        pages_content.append(page_content)
    
    return pages_content

def process_with_vllm(pdf_path: str, output_dir: str) -> List[Dict]:
    """
    将 PDF 转换为图片并使用 Vertex AI Vision 进行分析
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
    
    Returns:
        List[Dict]: 每页的处理结果
    """
    # 创建临时目录存储图片
    images_dir = os.path.join(output_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # 转换PDF为图片
    images = convert_from_path(pdf_path)
    pages_content = []
    
    # 初始化 Gemini Pro Vision 模型
    model = GenerativeModel("gemini-1.5pro-vision")
    config = GenerationConfig(
        temperature=0.1,
        top_p=1,
        top_k=32,
        candidate_count=1,
    )
    
    for i, image in enumerate(images, start=1):
        # 保存图片
        image_path = os.path.join(images_dir, f'page_{i}.png')
        image.save(image_path, 'PNG')
        
        # 获取图片尺寸
        width, height = image.size
        
        try:
            # 读取图片用于 Vertex AI
            image_part = Part.from_image(VertexImage.load_from_file(image_path))
            
            # 使用 Gemini 模型分析图片
            prompt = """请分析这个图片并提取以下信息：
1. 所有可见的文本内容
2. 文档的结构和布局（标题、段落、列表等）
3. 如果有表格，描述表格的内容
4. 如果有图片，描述图片的内容
请以结构化的方式返回这些信息。
"""
            
            response = model.generate_content(
                [prompt, image_part],
                generation_config=config,
            )
            
            # 整理分析结果
            page_content = {
                'page_number': i,
                'image_path': image_path,
                'size': {'width': width, 'height': height},
                'gemini_analysis': {
                    'text': response.text,
                    'safety_ratings': [
                        {
                            'category': rating.category,
                            'probability': rating.probability
                        }
                        for rating in response.safety_ratings
                    ] if hasattr(response, 'safety_ratings') else []
                }
            }
            
            pages_content.append(page_content)
            print(f"已完成第 {i} 页的分析")
            
        except Exception as e:
            print(f"处理第 {i} 页时出错: {e}")
            # 继续处理下一页
            continue
    
    return pages_content

def create_markdown_output(content: Dict, method: str) -> str:
    """
    生成Markdown格式的输出
    
    Args:
        content: 页面内容
        method: 处理方法 ('unstructured' 或 'pdf2image' 或 'vllm')
    
    Returns:
        str: Markdown格式的内容
    """
    markdown = f"# 第 {content['page_number']} 页\n\n"
    
    if method == 'unstructured':
        for element in content['content']:
            element_type = element['type']
            if element_type in ['Text', 'NarrativeText']:
                markdown += f"{element['text']}\n\n"
            elif element_type == 'Title':
                markdown += f"## {element['text']}\n\n"
            elif element_type == 'Table':
                markdown += "### 表格\n```json\n"
                markdown += json.dumps(element['table_data'], ensure_ascii=False, indent=2)
                markdown += "\n```\n\n"
            elif element_type == 'Image':
                markdown += "### 图片\n```json\n"
                markdown += json.dumps(element['image_data'], ensure_ascii=False, indent=2)
                markdown += "\n```\n\n"
    
    elif method == 'pdf2image':
        markdown += f"![页面图片]({content['image_path']})\n\n"
        markdown += "## 文本内容\n\n"
        for elem in content['text_elements']:
            pos = elem['position']
            markdown += f"[位置: ({pos['x']}, {pos['y']})] {elem['text']}\n"
        markdown += "\n"
    
    else:  # vllm
        markdown += f"![页面图片]({content['image_path']})\n\n"
        markdown += "## Gemini 分析结果\n\n"
        markdown += content['gemini_analysis']['text']
        markdown += "\n\n"
        
        if content['gemini_analysis']['safety_ratings']:
            markdown += "### 安全评级\n\n"
            for rating in content['gemini_analysis']['safety_ratings']:
                markdown += f"- {rating['category']}: {rating['probability']}\n"
            markdown += "\n"
    
    return markdown

def process_pdf(pdf_path: str, output_dir: str = "output", method: str = "unstructured") -> None:
    """
    处理PDF文件
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录路径
        method: 处理方法 ('unstructured' 或 'pdf2image' 或 'vllm')
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        # 根据选择的方法处理PDF
        if method == "unstructured":
            pages_content = process_with_unstructured(pdf_path)
        elif method == "pdf2image":
            pages_content = process_with_pdf2image(pdf_path, output_dir)
        else:  # vllm
            pages_content = process_with_vllm(pdf_path, output_dir)
        
        # 处理每一页
        for page_content in pages_content:
            page_num = page_content['page_number']
            
            # 生成Markdown
            markdown_content = create_markdown_output(page_content, method)
            output_file = os.path.join(output_dir, f"page_{page_num}.md")
            with open(output_file, 'w', encoding='utf-8') as md_file:
                md_file.write(markdown_content)
            print(f"已保存Markdown到: {output_file}")
            
            # 保存JSON
            json_file = os.path.join(output_dir, f"page_{page_num}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(page_content, f, ensure_ascii=False, indent=2)
            print(f"已保存JSON到: {json_file}")

    except Exception as e:
        print(f"处理PDF文件时出错: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='PDF文档处理工具')
    parser.add_argument('--pdf_path', default='docs/pdf/example.pdf', help='PDF文件路径')
    parser.add_argument('--output_dir', default='output', help='输出目录路径')
    parser.add_argument('--method', choices=['unstructured', 'pdf2image', 'vllm'], 
                       default='unstructured', help='PDF处理方法')
    args = parser.parse_args()
    
    # 初始化 Vertex AI
    setup_vertex_ai()
    
    # 处理PDF
    process_pdf(args.pdf_path, args.output_dir, args.method)
    print("\n处理完成！")

if __name__ == "__main__":
    main()

from typing import Dict, Any, Optional
from .base import BasePrompt

class PDFExtractionPrompt(BasePrompt):
    """PDF文本提取提示词"""
    
    def get_prompt(self, **kwargs) -> str:
        """
        获取PDF文本提取的提示词
        
        参数:
            page_number: 当前页码
            total_pages: 总页数
            document_type: 文档类型（可选）
            language: 语言（可选）
        """
        page_info = ""
        if 'page_number' in kwargs and 'total_pages' in kwargs:
            page_info = f"\n当前是第 {kwargs['page_number']} 页，共 {kwargs['total_pages']} 页。"
            
        language_info = f"\n文档语言：{kwargs.get('language', '未指定')}"
        doc_type_info = f"\n文档类型：{kwargs.get('document_type', '未指定')}"
        
        base_prompt = """请仔细分析这个图片，它是一个PDF文档的页面。请提取所有可见的文本内容，保持原有的格式和结构。

任务要求：
1. 保持段落的原有结构和格式
2. 保留标题、子标题的层级关系
3. 正确识别和保留列表项的格式和缩进
4. 保持表格的结构（如果有）
5. 注意保留页码、页眉、页脚等信息
6. 保持文本的原始顺序和布局

输出要求：
1. 以纯文本格式返回
2. 不要添加任何HTML或markdown标记
3. 使用换行来表示段落分隔
4. 使用适当的空格来保持文本对齐
5. 对于表格，使用空格或制表符来对齐列

特殊元素处理：
1. 图片：标注 [图片] 并简要描述图片内容
2. 公式：尽可能准确地转录数学公式
3. 图表：描述图表类型和主要内容
4. 页眉页脚：单独一行标注
5. 水印：忽略处理"""
        
        return base_prompt + page_info + language_info + doc_type_info
    
    def get_generation_config(self) -> Dict[str, Any]:
        """获取生成配置"""
        return {
            "max_output_tokens": 2048,
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 40
        }
    
    def get_stop_sequences(self) -> Optional[list]:
        """获取停止序列"""
        return None
    
    def get_safety_settings(self) -> Optional[list]:
        """获取安全设置"""
        return None


class PDFTableExtractionPrompt(BasePrompt):
    """PDF表格提取提示词"""
    
    def get_prompt(self, **kwargs) -> str:
        """
        获取PDF表格提取的提示词
        
        参数:
            table_context: 表格上下文信息
            expected_columns: 预期的列名列表
        """
        context = kwargs.get('table_context', '')
        columns = kwargs.get('expected_columns', [])
        columns_info = f"\n预期列名: {', '.join(columns)}" if columns else ""
        
        return f"""请分析图片中的表格，并提取其中的数据。{context}{columns_info}

任务要求：
1. 识别表格的结构（行数、列数）
2. 提取表头信息
3. 提取每个单元格的内容
4. 保持单元格数据的对齐方式
5. 处理合并的单元格
6. 保持数字的格式（如货币、百分比等）

输出格式：
1. 使用制表符分隔的文本格式
2. 第一行为表头
3. 每行数据独占一行
4. 保持数据的对齐
5. 对于空单元格，使用 [空] 标记
6. 对于合并单元格，在合并范围内重复内容

注意事项：
1. 确保所有列都对齐
2. 保持数据的原始格式
3. 标注任何无法识别的内容
4. 处理表格中的特殊字符"""
    
    def get_generation_config(self) -> Dict[str, Any]:
        """获取生成配置"""
        return {
            "max_output_tokens": 2048,
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 40
        }

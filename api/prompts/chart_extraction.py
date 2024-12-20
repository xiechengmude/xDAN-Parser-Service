from typing import Dict, Any, Optional, List
from .base import BasePrompt

class ChartExtractionPrompt(BasePrompt):
    """复杂图表和数据提取提示词"""
    
    def __init__(self):
        # 预定义的图表类型及其特定提示词
        self.chart_type_prompts = {
            "饼图": """
            - 提取各个扇区的具体数值和百分比
            - 识别扇区的标签和说明
            - 注意扇区的颜色编码
            - 计算并验证总和是否为100%
            """,
            "时间线": """
            - 按时间顺序提取所有事件
            - 保留具体的日期和时间点
            - 注意事件之间的间隔和关系
            - 提取每个时间点的关键信息
            """,
            "柱状图": """
            - 提取每个柱子的具体数值
            - 识别X轴和Y轴的标签
            - 注意数值单位和比例
            - 对比不同柱子之间的关系
            """
        }
        
        # 预定义的结构化输出格式
        self.output_formats = {
            "json": """
            以JSON格式输出，包含以下结构：
            {
                "title": "图表标题",
                "type": "图表类型",
                "data": {
                    // 具体数据
                },
                "metadata": {
                    // 额外信息
                }
            }
            """,
            "table": """
            以表格形式输出，包含以下列：
            - 类别/时间
            - 数值
            - 占比
            - 说明
            """
        }
    
    def _get_chart_specific_prompt(self, chart_type: str) -> str:
        """获取特定图表类型的提示词"""
        prompts = []
        if "+" in chart_type:
            # 处理复合图表
            chart_types = [t.strip() for t in chart_type.replace("（", "").replace("）", "").split("+")]
            for ct in chart_types:
                if ct in self.chart_type_prompts:
                    prompts.append(self.chart_type_prompts[ct])
        else:
            # 单一图表类型
            if chart_type in self.chart_type_prompts:
                prompts.append(self.chart_type_prompts[chart_type])
        
        return "\n".join(prompts) if prompts else ""
    
    def _get_output_format_prompt(self, format_type: str) -> str:
        """获取输出格式的提示词"""
        return self.output_formats.get(format_type, self.output_formats["json"])
    
    def get_prompt(self, **kwargs) -> str:
        """
        获取图表提取的提示词
        
        参数:
            chart_type: 图表类型（如：饼图、时间线等）
            language: 语言（默认中文）
            structure_format: 输出结构格式（json, table等）
            focus_points: 需要特别关注的点（列表）
            additional_instructions: 额外的具体说明
        """
        chart_type = kwargs.get('chart_type', '未指定')
        language = kwargs.get('language', '中文')
        structure_format = kwargs.get('structure_format', 'json')
        focus_points = kwargs.get('focus_points', [])
        additional_instructions = kwargs.get('additional_instructions', '')
        
        # 获取图表特定的提示词
        chart_specific_prompt = self._get_chart_specific_prompt(chart_type)
        
        # 获取输出格式提示词
        output_format_prompt = self._get_output_format_prompt(structure_format)
        
        # 构建重点关注提示词
        focus_points_prompt = ""
        if focus_points:
            focus_points_prompt = "特别注意提取以下内容：\n" + "\n".join(f"- {point}" for point in focus_points)
        
        base_prompt = f"""请仔细分析这张图片，它包含了复杂的图表、文字和数据信息。请按照以下要求提取所有内容：

1. 标题和主题：
   - 提取主标题和副标题
   - 识别图片的主要主题和内容领域

2. 文字内容：
   - 提取所有文字说明和描述
   - 保持原有的层级结构和格式
   - 注意保留重点标记和强调内容

3. 数据和图表：
{chart_specific_prompt}

4. 结构化输出要求：
{output_format_prompt}

5. 数据完整性要求：
   - 保持所有数值的精确性
   - 维持原始的层级关系
   - 保留所有标签和说明
   - 注意数据之间的关联性

{focus_points_prompt}

{additional_instructions}

语言要求：{language}"""

        return base_prompt
    
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

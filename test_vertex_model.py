import unittest
import os
import asyncio
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Optional
import time
import random

import vertexai
from vertexai.generative_models import GenerativeModel, Part
from pdf2image import convert_from_path
from PIL import Image
import io

class TestVertexModelParsing(unittest.TestCase):
    def setUp(self):
        """测试初始化"""
        self.pdf_path = "docs/pdf/ari_vr_2024.pdf"
        self.output_dir = "test_output/vertex_test"
        self.project_id = "elated-bison-417808"
        self.location = "us-central1"
        self.model_name = "gemini-1.5-pro-002"
        self.max_retries = 5  # 增加重试次数
        self.initial_retry_delay = 2  # 增加初始重试延迟
        self.max_concurrent = 3  # 限制并发数
        
        # 创建输出目录
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # 初始化 Vertex AI
        try:
            vertexai.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel(self.model_name)
            print(f"Vertex AI 初始化成功: project={self.project_id}, location={self.location}")
        except Exception as e:
            print(f"Vertex AI 初始化失败: {str(e)}")
            raise

    def convert_pdf_to_images(self) -> List[Image.Image]:
        """将PDF转换为图片列表"""
        try:
            images = convert_from_path(self.pdf_path)
            print(f"PDF转换成功，共 {len(images)} 页")
            return images
        except Exception as e:
            print(f"PDF转换失败: {str(e)}")
            raise

    async def process_single_page_with_retry(self, page_num: int, image: Image.Image) -> Optional[Dict]:
        """带重试机制的单页处理"""
        for attempt in range(self.max_retries):
            try:
                # 保存图片到临时文件
                image_path = os.path.join(self.output_dir, f"page_{page_num + 1}.png")
                image.save(image_path)
                print(f"第 {page_num + 1} 页图片已保存到: {image_path}")

                # 转换为字节流
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                print(f"第 {page_num + 1} 页图片已转换为字节流")

                # 创建提示词
                prompt = """请仔细分析这个图片，它是一个PDF文档的页面。请提取所有可见的文本内容，保持原有的格式和结构。
                特别注意：
                1. 保持段落的原有结构
                2. 保留标题、子标题的层级关系
                3. 正确识别和保留列表项
                4. 保持表格的结构（如果有）
                5. 注意保留页码、页眉、页脚等信息

                请以纯文本格式返回，不要添加任何HTML或markdown标记。
                """

                # 调用模型
                print(f"第 {page_num + 1} 页开始调用 Gemini API... (尝试 {attempt + 1}/{self.max_retries})")
                response = await self.model.generate_content_async(
                    [prompt, Part.from_data(img_byte_arr, mime_type="image/png")],
                    generation_config={
                        "max_output_tokens": 2048,
                        "temperature": 0.1,
                        "top_p": 0.8,
                        "top_k": 40
                    }
                )
                
                content = response.text
                print(f"第 {page_num + 1} 页处理完成，内容长度: {len(content)} 字符")

                return {
                    "page_number": page_num + 1,
                    "content": content,
                    "image_path": image_path,
                    "attempts": attempt + 1
                }

            except Exception as e:
                print(f"处理第 {page_num + 1} 页时出错 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    delay = self.initial_retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"等待 {delay:.2f} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    print(f"第 {page_num + 1} 页处理失败，已达到最大重试次数")
                    return None

    async def process_pages_in_batches(self, images: List[Image.Image]) -> List[Optional[Dict]]:
        """分批处理页面"""
        results = [None] * len(images)
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(i: int, image: Image.Image):
            async with semaphore:
                results[i] = await self.process_single_page_with_retry(i, image)
        
        tasks = [process_with_semaphore(i, image) for i, image in enumerate(images)]
        await asyncio.gather(*tasks)
        return results

    def save_results(self, results: List[Dict]):
        """保存处理结果"""
        # 保存为JSON
        json_path = os.path.join(self.output_dir, "results.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {json_path}")

        # 保存为Markdown
        markdown_path = os.path.join(self.output_dir, "results.md")
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(f"# PDF解析结果\n\n")
            f.write(f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for result in results:
                if result:
                    f.write(f"## 第 {result['page_number']} 页\n\n")
                    f.write(f"处理尝试次数: {result['attempts']}\n\n")
                    f.write(result['content'])
                    f.write("\n\n---\n\n")
        print(f"结果已保存到: {markdown_path}")

    def analyze_results(self, results: List[Dict]) -> Dict:
        """分析处理结果"""
        analysis = {
            "total_pages": len(results),
            "successful_pages": sum(1 for r in results if r is not None),
            "failed_pages": sum(1 for r in results if r is None),
            "avg_content_length": 0,
            "min_content_length": float('inf'),
            "max_content_length": 0,
            "total_attempts": sum(r['attempts'] for r in results if r is not None),
            "avg_attempts": 0
        }

        content_lengths = []
        for result in results:
            if result and result['content']:
                length = len(result['content'])
                content_lengths.append(length)
                analysis['min_content_length'] = min(analysis['min_content_length'], length)
                analysis['max_content_length'] = max(analysis['max_content_length'], length)

        if content_lengths:
            analysis['avg_content_length'] = sum(content_lengths) / len(content_lengths)
        else:
            analysis['min_content_length'] = 0

        if analysis['successful_pages'] > 0:
            analysis['avg_attempts'] = analysis['total_attempts'] / analysis['successful_pages']

        return analysis

    def test_vertex_model_processing(self):
        """测试Vertex AI模型处理PDF"""
        try:
            # 1. 转换PDF为图片
            images = self.convert_pdf_to_images()
            self.assertGreater(len(images), 0, "PDF应该至少包含一页")

            # 2. 分批处理每一页
            results = asyncio.run(self.process_pages_in_batches(images))

            # 3. 验证结果
            self.assertIsNotNone(results, "处理结果不应为空")
            self.assertEqual(len(results), len(images), "处理结果数量应该与页数相同")

            # 4. 分析结果
            analysis = self.analyze_results(results)
            print("\n处理结果分析:")
            print(f"总页数: {analysis['total_pages']}")
            print(f"成功页数: {analysis['successful_pages']}")
            print(f"失败页数: {analysis['failed_pages']}")
            print(f"平均内容长度: {analysis['avg_content_length']:.2f} 字符")
            print(f"最短内容长度: {analysis['min_content_length']} 字符")
            print(f"最长内容长度: {analysis['max_content_length']} 字符")
            print(f"总重试次数: {analysis['total_attempts']}")
            print(f"平均重试次数: {analysis['avg_attempts']:.2f}")

            # 5. 保存结果
            self.save_results(results)

            # 6. 验证处理质量
            for result in results:
                if result:
                    self.assertIn('page_number', result, "结果应包含页码")
                    self.assertIn('content', result, "结果应包含内容")
                    self.assertGreater(len(result['content']), 50, 
                                     f"第 {result['page_number']} 页内容过短")

        except Exception as e:
            self.fail(f"测试过程中出错: {str(e)}")

if __name__ == '__main__':
    unittest.main()

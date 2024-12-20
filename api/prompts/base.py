from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BasePrompt(ABC):
    """提示词基类"""
    
    @abstractmethod
    def get_prompt(self, **kwargs) -> str:
        """获取提示词"""
        pass
    
    @abstractmethod
    def get_generation_config(self) -> Dict[str, Any]:
        """获取生成配置"""
        pass
    
    def get_stop_sequences(self) -> Optional[list]:
        """获取停止序列"""
        return None
    
    def get_safety_settings(self) -> Optional[list]:
        """获取安全设置"""
        return None

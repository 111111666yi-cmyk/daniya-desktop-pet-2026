import requests
from typing import Any

class LocalModelManager:
    """
    负责本地大模型服务连接测试和模型列表获取 (Ollama / LM Studio / llama.cpp / Custom)。
    不直接负责聊天 (聊天由 src/llm/boundaries/ 的边界模块负责)，仅处理服务探测和配置辅助。
    """

    @classmethod
    def test_connection(cls, service_type: str, base_url: str, timeout: int = 5) -> tuple[bool, str]:
        if not base_url:
            return False, "Base URL 不能为空"
        
        base_url = base_url.rstrip("/")
        
        try:
            if service_type.lower() == "ollama":
                # Ollama 标准探活
                resp = requests.get(base_url, timeout=timeout)
                if resp.status_code == 200 and "Ollama is running" in resp.text:
                    return True, "Ollama 服务连接成功"
                elif resp.status_code == 200:
                    return True, "Ollama API 连通，但返回结果非预期"
                else:
                    return False, f"Ollama HTTP {resp.status_code}"
            
            elif service_type.lower() in ["lm_studio", "openai_compatible", "openai-compatible local"]:
                # 标准 OpenAI 探测，通常测 /v1/models
                resp = requests.get(f"{base_url}/models", timeout=timeout)
                if resp.status_code == 200:
                    return True, "OpenAI-Compatible 服务连接成功"
                else:
                    return False, f"OpenAI-Compatible HTTP {resp.status_code}"

            elif service_type.lower() == "llama.cpp server":
                # llama.cpp 探测
                resp = requests.get(f"{base_url}/health", timeout=timeout)
                if resp.status_code == 200:
                    return True, "llama.cpp server 连接成功"
                else:
                    # 也可能 /v1/models 可用
                    return cls.test_connection("openai_compatible", base_url, timeout)

            else:
                # Custom 或未知
                resp = requests.get(base_url, timeout=timeout)
                return True, f"自定义服务连通 (HTTP {resp.status_code})"

        except requests.RequestException as e:
            return False, f"服务连接失败: {str(e)}"

    @classmethod
    def fetch_model_list(cls, service_type: str, base_url: str, timeout: int = 5) -> list[str]:
        """
        根据不同的服务类型解析对应 API 获取模型列表。
        返回可用的模型名字符串列表。
        """
        if not base_url:
            return []
            
        base_url = base_url.rstrip("/")
        models = []
        
        try:
            if service_type.lower() == "ollama":
                resp = requests.get(f"{base_url}/api/tags", timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
            else:
                # 默认走 OpenAI-Compatible
                resp = requests.get(f"{base_url}/models", timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id") for m in data.get("data", [])]
        except Exception:
            pass
            
        return [m for m in models if m]

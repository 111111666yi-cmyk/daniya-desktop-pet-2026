import pytest
from unittest.mock import patch, Mock
import requests
from src.local_model_manager import LocalModelManager

def test_test_connection_ollama_success():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.text = "Ollama is running"
        mock_get.return_value = mock_resp
        
        ok, msg = LocalModelManager.test_connection("ollama", "http://localhost:11434")
        assert ok is True
        assert "Ollama 服务连接成功" in msg

def test_test_connection_lmstudio_success():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        
        ok, msg = LocalModelManager.test_connection("lm_studio", "http://localhost:1234/v1")
        assert ok is True
        assert "OpenAI-Compatible 服务连接成功" in msg

def test_test_connection_failure():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.RequestException("Connection refused")
        
        ok, msg = LocalModelManager.test_connection("ollama", "http://localhost:11434")
        assert ok is False
        assert "服务连接失败" in msg

def test_fetch_model_list_ollama():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]
        }
        mock_get.return_value = mock_resp
        
        models = LocalModelManager.fetch_model_list("ollama", "http://localhost:11434")
        assert "qwen2.5:7b" in models
        assert "llama3:8b" in models
        assert len(models) == 2

def test_fetch_model_list_openai_compatible():
    with patch('requests.get') as mock_get:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [{"id": "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"}, {"id": "custom-model"}]
        }
        mock_get.return_value = mock_resp
        
        models = LocalModelManager.fetch_model_list("lm_studio", "http://localhost:1234/v1")
        assert "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF" in models
        assert len(models) == 2

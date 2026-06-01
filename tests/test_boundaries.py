"""边界模块单元测试。

覆盖：
- _retry_request() 重试/退避/错误分类
- openai_api.chat() / test_connection() 成功/失败路径
- ollama_api.chat() / test_connection() 成功/失败路径
- anthropic_api.chat() 成功/失败路径
- ModelNotFoundError 继承链
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, Mock

import requests

from src.llm.boundaries import (
    AuthError,
    BoundaryError,
    MalformedResponse,
    NetworkError,
    RateLimitError,
    ServerError,
    _retry_request,
)
from src.llm.boundaries import openai_api, ollama_api, anthropic_api
from src.llm.boundaries.ollama_api import ModelNotFoundError


# ═══════════════════════════════════════════════════════════════════
# _retry_request 测试
# ═══════════════════════════════════════════════════════════════════

class TestRetryRequest:
    """测试 _retry_request 退避重试逻辑。"""

    def test_success_on_first_attempt(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        fn = Mock(return_value=mock_resp)
        result = _retry_request(fn)
        assert result is mock_resp
        assert fn.call_count == 1

    def test_retry_on_502_then_success(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 502
        ok = Mock(spec=requests.Response)
        ok.status_code = 200
        fn = Mock(side_effect=[fail, ok])
        result = _retry_request(fn, max_retries=3, backoff_base=0.01)
        assert result is ok
        assert fn.call_count == 2

    def test_retry_on_503_then_success(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 503
        ok = Mock(spec=requests.Response)
        ok.status_code = 200
        fn = Mock(side_effect=[fail, ok])
        result = _retry_request(fn, max_retries=3, backoff_base=0.01)
        assert result is ok
        assert fn.call_count == 2

    def test_retry_on_504_then_success(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 504
        ok = Mock(spec=requests.Response)
        ok.status_code = 200
        fn = Mock(side_effect=[fail, ok])
        result = _retry_request(fn, max_retries=3, backoff_base=0.01)
        assert result is ok

    def test_server_error_exhausted_retries(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 502
        fn = Mock(return_value=fail)
        with pytest.raises(ServerError):
            _retry_request(fn, max_retries=1, backoff_base=0.01)
        assert fn.call_count == 2  # 1 initial + 1 retry

    def test_401_raises_auth_error_immediately(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 401
        fn = Mock(return_value=fail)
        with pytest.raises(AuthError):
            _retry_request(fn, max_retries=3, backoff_base=0.01)
        # 401 不重试，直接抛
        assert fn.call_count == 1

    def test_429_with_retry_after_header(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 429
        fail.headers = {"Retry-After": "1"}
        ok = Mock(spec=requests.Response)
        ok.status_code = 200
        fn = Mock(side_effect=[fail, ok])
        result = _retry_request(fn, max_retries=3, backoff_base=0.01)
        assert result is ok

    def test_429_exhausted_retries(self) -> None:
        fail = Mock(spec=requests.Response)
        fail.status_code = 429
        fail.headers = {"Retry-After": "0"}
        fn = Mock(return_value=fail)
        with pytest.raises(RateLimitError):
            _retry_request(fn, max_retries=1, backoff_base=0.01)

    def test_connection_error_retry_then_success(self) -> None:
        ok = Mock(spec=requests.Response)
        ok.status_code = 200
        fn = Mock(side_effect=[requests.ConnectionError("refused"), ok])
        result = _retry_request(fn, max_retries=3, backoff_base=0.01)
        assert result is ok

    def test_connection_error_exhausted(self) -> None:
        fn = Mock(side_effect=requests.ConnectionError("refused"))
        with pytest.raises(NetworkError):
            _retry_request(fn, max_retries=1, backoff_base=0.01)

    def test_timeout_exhausted(self) -> None:
        fn = Mock(side_effect=requests.Timeout("timed out"))
        with pytest.raises(NetworkError):
            _retry_request(fn, max_retries=1, backoff_base=0.01)

    def test_http_400_raises_boundary_error(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)
        fn = Mock(return_value=mock_resp)
        with pytest.raises(BoundaryError, match="Client error"):
            _retry_request(fn)


# ═══════════════════════════════════════════════════════════════════
# openai_api 测试
# ═══════════════════════════════════════════════════════════════════

class TestOpenAIAPI:
    """测试 OpenAI-compatible 边界（含 DeepSeek）。"""

    def test_chat_success(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}]
        }

        with patch("requests.post", return_value=mock_resp):
            result = openai_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-test",
                base_url="https://api.test.com/v1",
                model="test-model",
            )
            assert result == "Hello, world!"

    def test_chat_sends_bearer_auth_when_key_provided(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            openai_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-test-key",
                base_url="https://api.test.com/v1",
                model="m",
            )
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["Authorization"] == "Bearer sk-test-key"

    def test_chat_sends_api_key_auth_when_requested(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            openai_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-test-key",
                base_url="https://api.test.com/v1",
                model="m",
                auth_header="api-key",
            )
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["api-key"] == "sk-test-key"
            assert "Authorization" not in headers

    def test_chat_skips_auth_when_key_empty(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            openai_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="",
                base_url="http://localhost:1234/v1",
                model="local-model",
            )
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert "Authorization" not in headers

    def test_chat_raises_malformed_on_empty_content(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": ""}}]
        }

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MalformedResponse, match="empty"):
                openai_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key="sk-test",
                    base_url="https://api.test.com/v1",
                    model="m",
                )

    def test_chat_raises_malformed_on_bad_json(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"unexpected": "format"}

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MalformedResponse, match="parse"):
                openai_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key="sk-test",
                    base_url="https://api.test.com/v1",
                    model="m",
                )

    def test_chat_raises_auth_error_on_401(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(AuthError):
                openai_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key="bad-key",
                    base_url="https://api.test.com/v1",
                    model="m",
                )

    def test_test_connection_success(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "pong"}}]
        }
        with patch("requests.post", return_value=mock_resp):
            assert openai_api.test_connection(
                "sk-test", base_url="https://api.test.com/v1", model="m"
            ) is True

    def test_test_connection_failure(self) -> None:
        with patch("requests.post", side_effect=requests.ConnectionError("no")):
            assert openai_api.test_connection(
                "sk-test", base_url="https://api.test.com/v1", model="m"
            ) is False


# ═══════════════════════════════════════════════════════════════════
# ollama_api 测试
# ═══════════════════════════════════════════════════════════════════

class TestOllamaAPI:
    """测试 Ollama 边界。"""

    def test_chat_success(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Ollama says hi"}
        }

        with patch("requests.post", return_value=mock_resp):
            result = ollama_api.chat(
                [{"role": "user", "content": "Hi"}],
                model="qwen2.5:0.5b",
            )
            assert result == "Ollama says hi"

    def test_model_not_found_raises(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": "not found"}

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ModelNotFoundError):
                ollama_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    model="nonexistent-model",
                )

    def test_model_not_found_inherits_boundary_error(self) -> None:
        """确保 ModelNotFoundError 是 BoundaryError 的子类。"""
        assert issubclass(ModelNotFoundError, BoundaryError)

    def test_empty_content_raises_malformed(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": ""}}

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MalformedResponse, match="empty"):
                ollama_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    model="test",
                )

    def test_test_connection_success(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp):
            assert ollama_api.test_connection() is True

    def test_test_connection_failure(self) -> None:
        with patch("requests.get", side_effect=requests.ConnectionError("no")):
            assert ollama_api.test_connection() is False

    def test_sends_to_correct_endpoint(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "ok"}}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ollama_api.chat(
                [{"role": "user", "content": "Hi"}],
                base_url="http://localhost:11434",
                model="test",
            )
            url = mock_post.call_args[0][0]
            assert url == "http://localhost:11434/api/chat"


# ═══════════════════════════════════════════════════════════════════
# anthropic_api 测试
# ═══════════════════════════════════════════════════════════════════

class TestAnthropicAPI:
    """测试 Anthropic Claude 边界。"""

    def test_chat_success(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "Bonjour"}]
        }

        with patch("requests.post", return_value=mock_resp):
            result = anthropic_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-ant-test",
            )
            assert result == "Bonjour"

    def test_system_message_separated(self) -> None:
        """Anthropic 的 system 消息应放在 payload["system"] 而非 messages 数组里。"""
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            anthropic_api.chat(
                [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ],
                api_key="sk-ant-test",
            )
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            assert "system" in payload
            assert len(payload["system"]) == 1
            assert payload["system"][0]["text"] == "You are helpful."
            # system 不在 messages 里
            roles_in_messages = [m["role"] for m in payload["messages"]]
            assert "system" not in roles_in_messages

    def test_sends_x_api_key_header(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            anthropic_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-ant-test-123",
            )
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["x-api-key"] == "sk-ant-test-123"
            assert headers["anthropic-version"] == "2023-06-01"

    def test_empty_content_raises_malformed(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": []}

        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MalformedResponse, match="empty"):
                anthropic_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key="sk-ant-test",
                )

    def test_auth_error_on_401(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(AuthError):
                anthropic_api.chat(
                    [{"role": "user", "content": "Hi"}],
                    api_key="bad-key",
                )

    def test_correct_endpoint(self) -> None:
        mock_resp = Mock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "ok"}]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            anthropic_api.chat(
                [{"role": "user", "content": "Hi"}],
                api_key="sk-ant-test",
                base_url="https://api.anthropic.com/v1",
            )
            url = mock_post.call_args[0][0]
            assert url == "https://api.anthropic.com/v1/messages"


# ═══════════════════════════════════════════════════════════════════
# Error 继承链
# ═══════════════════════════════════════════════════════════════════

class TestErrorHierarchy:
    """验证所有边界异常正确继承 BoundaryError。"""

    def test_auth_error_is_boundary(self) -> None:
        assert issubclass(AuthError, BoundaryError)

    def test_rate_limit_error_is_boundary(self) -> None:
        assert issubclass(RateLimitError, BoundaryError)

    def test_server_error_is_boundary(self) -> None:
        assert issubclass(ServerError, BoundaryError)

    def test_network_error_is_boundary(self) -> None:
        assert issubclass(NetworkError, BoundaryError)

    def test_malformed_response_is_boundary(self) -> None:
        assert issubclass(MalformedResponse, BoundaryError)

    def test_model_not_found_is_boundary(self) -> None:
        assert issubclass(ModelNotFoundError, BoundaryError)

    def test_boundary_error_can_be_caught_generically(self) -> None:
        """确保所有子类异常都可以被 `except BoundaryError` 捕获。"""
        for exc_cls in [AuthError, RateLimitError, ServerError, NetworkError, MalformedResponse, ModelNotFoundError]:
            try:
                raise exc_cls("test")
            except BoundaryError:
                pass  # expected
            else:
                pytest.fail(f"{exc_cls.__name__} not caught by BoundaryError")

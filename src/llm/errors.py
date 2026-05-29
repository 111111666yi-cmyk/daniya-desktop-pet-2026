class ProviderError(Exception):
    """基类：Provider 执行异常"""
    pass


class ProviderConnectionError(ProviderError):
    """网络连接、超时或服务器无响应"""
    pass


class ProviderAuthError(ProviderError):
    """API Key 缺失或无效"""
    pass


class ProviderFormatError(ProviderError):
    """响应格式错误或解析失败"""
    pass


class ProviderConfigError(ProviderError):
    """配置项缺失或错误（如必填项为空）"""
    pass

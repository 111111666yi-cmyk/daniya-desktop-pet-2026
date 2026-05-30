# 自定义云端 Provider 配置指南

达妮娅桌宠支持**任意 OpenAI 兼容 API**，包括冷门/国产/自部署服务。

---

## 一、在达妮娅中配置

1. 打开设置中心 → 模型与引擎 → 云端 API 配置
2. Provider 选择下拉最后一项：「**自定义云端 (Custom)**」
3. 填入：

| 字段 | 含义 | 示例 |
|---|---|---|
| Base URL | API 端点地址（不含 `/chat/completions`） | `https://open.bigmodel.cn/api/paas/v4` |
| Model | 模型 ID | `glm-4-flash` |
| API Key | 你的密钥 | 从平台后台获取 |

4. 点「测试连接」→ 通过后点「设为当前模型」→ 生效

### 已验证可用的三方 API 端点

| 厂商 | Base URL | 模型示例 |
|---|---|---|
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`, `glm-4-plus` |
| 百度千帆 | `https://qianfan.baidubce.com/v2` | `ernie-4.0-turbo-8k` |
| 讯飞星火 | `https://spark-api-open.xf-yun.com/v1` | `4.0Ultra` |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` |
| Together AI | `https://api.together.xyz/v1` | `mistralai/Mixtral-8x7B` |
| Fireworks | `https://api.fireworks.ai/inference/v1` | `accounts/fireworks/models/llama-v3p1-70b` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Moonshot/Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 零一万物 | `https://api.lingyiwanwu.com/v1` | `yi-large` |
| MiniMax | `https://api.minimax.chat/v1` | `abab6.5s-chat` |
| 腾讯混元 | `https://api.hunyuan.cloud.tencent.com/v1` | `hunyuan-lite` |
| 字节豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `ep-xxx` (需 endpoint ID) |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o` |

---

## 二、CC Switch — 本地 API 代理

### 是什么

**CC Switch** 是一款免费开源的跨平台桌面应用，核心功能是启动一个本地 HTTP 代理服务器（默认 `127.0.0.1:15721`），统一拦截、管理和转发 AI CLI 工具（Claude Code、Codex、Gemini CLI 等）的 API 请求。

- **GitHub**：[farion1231/cc-switch](https://github.com/farion1231/cc-switch)
- **官网**：ccswitch.io
- **完全免费**，Windows / macOS / Linux 均有安装包

### 为什么用

| 痛点 | CC Switch 解决方案 |
|---|---|
| 切换模型需手动改 JSON | 图形界面一键切换 |
| 多工具配置分散 | 统一代理入口，一个地址覆盖所有工具 |
| 主供应商挂了 | 自动故障转移 + 熔断 |
| 用国内模型需折腾 BASE_URL | 自动协议格式转换 |
| 看不到用量 | 实时日志 + Token 统计 |

### 工作原理

```
达妮娅桌宠
    │
    ▼
127.0.0.1:15721  (CC Switch 本地代理)
    │
    ├──▶ GLM (智谱)
    ├──▶ DeepSeek
    ├──▶ Kimi
    ├──▶ Claude 官方
    ├──▶ 自定义端点...
    │
    ▼
支持 50+ 预设供应商
```

### 在达妮娅中接入 CC Switch

CC Switch 启动代理后，在达妮娅中配置：

| 字段 | 值 |
|---|---|
| Provider | 自定义云端 (Custom) |
| Base URL | `http://127.0.0.1:15721/v1` |
| Model | 在 CC Switch 中选择的模型名 |
| API Key | `cc-switch` 或任意非空字符串（代理不校验） |

之后在 CC Switch 界面切换模型，**达妮娅无需任何改动，立即生效**。

### 协议转换能力

CC Switch 自动完成以下格式互转：
- **Anthropic Messages** ↔ **OpenAI Chat/Responses** ↔ **Gemini Native**

所以即使达妮娅发的是 OpenAI 格式请求，也能通过 CC Switch 访问 Gemini 原生端点、Claude 端点等。

---

## 三、自部署 API 代理

如果你想自己搭建而非用 CC Switch，以下开源方案可选：

### 1. one-api（songquanpeng/one-api）

最成熟的中文社区 OpenAI 代理管理面板。

- **GitHub**：[songquanpeng/one-api](https://github.com/songquanpeng/one-api)
- **部署**：`docker run -d -p 3000:3000 justsong/one-api`
- **功能**：多供应商管理、Key 池、额度控制、用量统计、Web 管理面板
- **支持的供应商**：OpenAI / Claude / Gemini / DeepSeek / 智谱 / 讯飞 / 百度 / 阿里 / 腾讯 / 字节 等 30+

### 2. new-api（Calcium-Ion/new-api）

one-api 的增强分支，界面更现代。

- **GitHub**：[Calcium-Ion/new-api](https://github.com/Calcium-Ion/new-api)
- **部署**：`docker run -d -p 3000:3000 calciumion/new-api`
- **额外功能**：马甲包、RPM/TPM 精细化控制、数据看板

### 3. AI Worker Proxy（zxcloli666）

基于 Cloudflare Workers 的免费方案，零服务器成本。

- **GitHub**：[zxcloli666/AI-Worker-Proxy](https://github.com/zxcloli666/AI-Worker-Proxy)
- **部署**：复制代码到 Cloudflare Workers → 1 分钟上线
- **功能**：自动故障转移、Token 轮换、免费托管
- **缺点**：Cloudflare 在国内访问可能较慢

### 4. Proxify（poixeai）

轻量级 Go 实现，适合低配 VPS。

- **GitHub**：[poixeai/proxify](https://github.com/poixeai/proxify)
- **部署**：单二进制文件，10MB 以内

---

## 四、接入达妮娅的通用公式

无论你用什么代理方案，接入达妮娅只需填 3 个值：

```
Base URL  = <你的代理地址>/v1
Model     = <代理转发的模型名>
API Key   = <代理要求的 Key，没有就随意填>
```

达妮娅的 `openai_api.chat()` 只做 `POST {Base URL}/chat/completions` + Bearer Auth。**不区分厂商、不校验来源、不做白名单**。能通的都通。

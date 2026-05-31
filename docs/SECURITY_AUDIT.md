# SECURITY_AUDIT

审计阶段：第一阶段，只读静态审计

## 1. API Key 是否硬编码

结论：未发现真实 API Key 硬编码。

证据：

- tracked secret scan 命中的是 `.env.example`、README 示例、docs 示例和测试 fixture。
- `ProviderManager` 从 `.env` 或环境变量读取 key。
- `SettingsManager.save_api_settings()` 将 key 写入 `.env`，并从 JSON 中移除 `api_key`/`api_key_masked`。

注意：

- 测试中存在 `sk-test`、`secret-key`、`secret-api-key-123` 等 fixture，不是真实 key。

## 2. API Key 是否进日志

静态结论：未发现直接打印完整 key 的代码路径。

证据：

- `src/chat_client.py` 提供 `mask_key()`
- `SettingsWindow` password 输入框使用 `QLineEdit.EchoMode.Password`
- `diagnostics` 测试检查不暴露 full key

第二阶段动态结果：

- 无 `.env`、空 Key、错 Key 均 fallback 到 `local`。
- 错 Key 日志未包含完整错误 Key。
- 正确 Key 动态验证 source=`api`，fallback=false。

## 3. API Key 是否进 Git

结论：未发现。

证据：

- `.env` 被 `.gitignore` 忽略。
- `git ls-files .env config/api_config.json` 无输出。
- tracked scan 未发现真实 key。

## 4. `.env` 是否被忽略

结论：是。

证据：

- `.gitignore` 行 2-4：`.env`, `.env.*`, `!.env.example`
- `git check-ignore -v .env` 命中 `.gitignore:2`

## 5. `assets/private` 是否被忽略

结论：是。

证据：

- `.gitignore` 行 11：`assets/private/`
- `git check-ignore -v assets\private` 命中该规则

## 6. `data` 是否被忽略

结论：是。

证据：

- `.gitignore` 行 7-8：`data/`, `data/daniya_relation/`
- `git ls-files data` 无输出

## 7. `models` 是否被忽略

结论：是。

证据：

- `.gitignore` 行 14：`models/`
- `git check-ignore -v models` 命中该规则

## 8. 发布包是否包含敏感文件

第二阶段结论：通过。

已修复的静态风险：

- FA-PKG-001：`pack.bat` 复制整个 `config/`，可能包含 ignored 本地配置。
- FA-PKG-002：`pack.bat` 复制整个 `docs/`，可能包含 ignored 本地截图目录。

最终扫描：

| 检查项 | release | dist | zip |
|---|---|---|---|
| `.env` | 不包含 | 不包含 | 不包含 |
| `config/api_config.json` | 不包含 | 不包含 | 不包含 |
| `config/multimodal_config.json` | 不包含 | 不包含 | 不包含 |
| `data/` | 不包含 | 不包含 | 不包含 |
| `assets/private/` | 不包含 | 不包含 | 不包含 |
| `models/` | 不包含 | 不包含 | 不包含 |
| `docs/v0.51_patch_audit/` | 不包含 | 不包含 | 不包含 |
| 真实 API Key | 未发现 | 未发现 | 未发现 |

## 9. 本地模型许可证提示是否存在

静态结论：存在相关字段。

证据：

- `config/model_profiles.json` 中 Ollama profile 含 `"license_required": true`。
- `docs/local_models.md` 存在。

后续需要：

- 设置中心本地模型 UI 是否展示许可证提示，需 GUI 动态验证。

## 10. 用户聊天记录是否被打包

第二阶段结论：不被打包。

证据：

- `pack.bat` robocopy 排除 `data`
- cleanup 删除 release `data`
- `.gitignore` 忽略 `data/`

## 11. 私有角色素材是否被打包

第二阶段结论：不被打包。

证据：

- `characters/daniya` release copy 使用 `/XD "assets"`
- `characters/*/assets/` 被忽略
- `characters/template/assets/` 是公开 fallback 例外

## 总体结论

Git 安全：通过。

打包安全：第二阶段通过。

已关闭安全项：

- FA-PKG-001
- FA-PKG-002

备注：第二阶段临时自动化脚本曾误删 ignored `data/` 和 `config/api_config.json`，随后已重新生成安全默认文件。该事故属于本地审计执行副作用，不是发布包泄露；但它说明后续动态脚本必须避免删除 ignored 用户态数据，优先使用外部临时 runtime root。

# Destructive Test Policy

更新日期：2026-06-03
适用范围：本地破坏性回归测试、缺文件测试、坏配置测试、打包安全检查和运行态恢复测试。

## 禁止直接删除的路径

以下路径可能包含用户运行态、密钥、私有素材或本地模型文件，测试脚本不得直接删除、清空或覆盖：

- `data/`
- `.env`
- `config/api_config.json`
- `config/multimodal_config.json`
- `assets/private/`
- `models/`
- `backups/`

## 必须使用的测试方式

缺文件、坏 JSON/YAML、坏 window state、缺 manifest、缺角色包等测试只能使用以下方式之一：

1. 在临时沙盒目录中复制最小 fixture 后测试。
2. 先运行 `python tools/backup_runtime_state.py`，再执行测试，最后运行 `python tools/restore_runtime_state.py backups/runtime_backup_YYYYMMDD_HHMMSS`。
3. 对单个文件使用临时改名，并在 `finally` 或等价清理逻辑中恢复。

如果测试中断，必须能通过明确指定的 `backups/runtime_backup_YYYYMMDD_HHMMSS/` 备份目录恢复。不要伪造恢复成功；恢复失败时必须报告失败路径和原因。

## 工具和发布包规则

- `backups/` 必须保持在 `.gitignore` 中。
- `tools/backup_runtime_state.py` 和 `tools/restore_runtime_state.py` 只用于开发审计，不进入 release 包。
- `pack.bat` 不复制 `tools/`，release 和 zip 中不得包含 runtime backup 或 restore 工具。
- 打包后仍需扫描 `.env`、`data/`、`assets/private/`、`models/`、`backups/`、`config/api_config.json`、`config/multimodal_config.json`。

## 事故记录要求

若测试误删或覆盖 ignored 运行态文件，必须记录到：

- `docs/KNOWN_ISSUES.md`
- 对应版本的维护记录或回归记录

记录必须明确说明 Git 和 release 是否受影响、旧本地运行态历史是否可以通过 Git 恢复，以及已经采取的防复发措施。

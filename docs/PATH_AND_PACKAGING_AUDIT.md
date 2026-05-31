# PATH_AND_PACKAGING_AUDIT

审计阶段：第一阶段，只读静态审计

## 路径工具

| 函数 | 文件 | 用途 |
|---|---|---|
| `bundled_root()` | `src/utils.py` | PyInstaller `_MEIPASS` 或源码根 |
| `runtime_root()` | `src/utils.py` | exe 所在目录或源码根 |
| `resource_path()` | `src/utils.py` | 资源路径 |
| `ensure_dir()` | `src/utils.py` | 创建目录 |

## 开发环境路径

静态观察：

- `main.py` 位于根目录。
- `config/`, `characters/`, `assets/`, `docs/`, `data/` 均位于根目录。
- `data/` 是运行态路径，Git 忽略。

## PyInstaller 环境路径

静态观察：

- `pack.bat` 使用 PyInstaller `--windowed --name DaniyaSummerPet`。
- `src/utils.py` 通过 `sys._MEIPASS` 处理 bundled root。
- `runtime_root()` 在 frozen 时使用 `Path(sys.executable).resolve().parent`。

## assets 路径

静态观察：

- `assets/private/` 被 Git 忽略。
- `characters/*/assets/` 被 Git 忽略。
- `characters/template/assets/` 被显式允许并已跟踪。
- `pack.bat` 加入 `assets\placeholder` 和 `assets\icons`。

风险：

- `characters/daniya/assets/` 不入 Git 且不应入 release。
- 动态缺图/坏图 fallback 尚未在第一阶段测试。

## characters 路径

静态观察：

- `pack.bat` 对 daniya 只添加 YAML/lore 文件，不添加 daniya assets。
- `pack.bat` 添加整个 `characters\template`，包含公开 placeholder assets。
- release copy 对 `characters\daniya` 使用 `/XD "assets"`。

风险：

- `characters/test_dummy/` 本地存在但不进入 release。

## config 路径

第一阶段 P1 风险：

- `pack.bat` 使用 `--add-data "config;config"`。
- `pack.bat` 使用 `robocopy "config" "release\%PACKAGE_NAME%\config" /E`。
- 本地 ignored `config/api_config.json`、`config/multimodal_config.json` 会被目录级复制。

第二阶段修复：

- 已改成 `%TEMP%` 临时白名单 package input。
- `config/app_config.example.json` 复制为 release 的 `config/app_config.json`。
- release 只包含公开默认配置：`api_config.example.json`, `app_config.json`, `bookmarks.json`, `model_catalog.json`, `model_profiles.json`, `profile.json`, `provider_capabilities.json`, `setup_config.json`, `system_prompt.txt`。
- `config/api_config.json` 与 `config/multimodal_config.json` 不进入 dist/release/zip。

## data 路径

静态观察：

- `data/` 被 Git 忽略。
- `pack.bat` robocopy 排除 `data`。
- `pack.bat` cleanup 删除 release 中 `data`。

后续测试：

- 打包后首次运行是否自动创建 `data/`。
- 损坏 data 文件是否恢复。

## docs 路径

第一阶段 P2 风险：

- `pack.bat` 复制整个 `docs`。
- `.gitignore` 忽略 `docs/v0.51_patch_audit/`，但 `pack.bat` 不读取 `.gitignore`。
- 本地截图/模拟脚本可能进入 release。

第二阶段修复：

- 已改成临时 docs 白名单 package input。
- `robocopy` 排除：`v0.51_patch_audit`, `screenshots`, `debug`, `debug_logs`, `tmp`, `__pycache__`。
- 文件排除：`*.tmp`, `*.log`, `debug_*`。

## .env 路径

静态观察：

- `.env` 被 Git 忽略。
- `.env.example` 被允许。
- `pack.bat` 拷贝 `.env.example`。
- `pack.bat` cleanup 删除 release `.env`。

结论：Git 与 release 脚本对 `.env` 有显式保护。

## private / models 路径

静态观察：

- `.gitignore` 覆盖 `assets/private/`、`models/`。
- `pack.bat` robocopy 排除 private/data/models/backups。
- `pack.bat` cleanup 删除 private/data/models/backups。

结论：静态规则存在；需要动态 zip 检查确认。

## Release zip 结构

第二阶段已执行 `pack.bat`，zip 结构状态为 `PASS`。

最终扫描：

| 路径 | release | dist | zip |
|---|---|---|---|
| `.env` | 不存在 | 不存在 | 不存在 |
| `config/api_config.json` | 不存在 | 不存在 | 不存在 |
| `config/multimodal_config.json` | 不存在 | 不存在 | 不存在 |
| `data/` | 不存在 | 不存在 | 不存在 |
| `assets/private/` | 不存在 | 不存在 | 不存在 |
| `models/` | 不存在 | 不存在 | 不存在 |
| `docs/v0.51_patch_audit/` | 不存在 | 不存在 | 不存在 |

zip entry count：427

本地发现：

- `release/` 下有旧 `DaniyaSummerPet-v0.44-win-x64` 产物。
- 该目录被 `.gitignore` 覆盖。

风险：

- 人工审计时必须不要把旧 v0.44 产物当成当前 v0.55.2 结果。

第二阶段备注：

- release exe 冒烟会在 release 目录生成运行态文件；冒烟后已重新执行 `pack.bat`，确保最终 release/zip 干净。

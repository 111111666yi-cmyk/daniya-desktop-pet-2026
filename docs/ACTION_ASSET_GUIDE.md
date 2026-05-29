# 动作素材包制作与使用指南 (Action Asset Pack Guide)

达妮娅桌宠的动作引擎由基于 JSON 配置的 `manifest.json` 驱动，允许您完全自定义角色的视觉呈现与交互动画。

## 1. 动作素材目录结构

动作素材包必须存放在工程下的 `assets/private/` 目录。我们强烈建议使用子文件夹（例如 `daniya_summer/`）来收纳序列帧图片。

典型的合规目录结构如下：
```text
assets/private/
├── normal1.png                # 必须存在：用于全局保底静止帧
├── normal2.png                # 必须存在：用于全局保底交互帧
├── manifest.json              # 必须存在：驱动动作配置
└── daniya_summer/             # 推荐的素材归纳目录
    ├── idle/
    │   ├── idle_01.png
    │   ├── idle_02.png
    │   └── ...
    ├── talk/
    ├── clicked/
    ├── drag/
    ├── sleep/
    ├── happy/
    └── remind/
```

## 2. manifest.json 格式

`manifest.json` 用于映射动作与对应的图片文件。以下是一个规范的配置文件示例：

```json
{
  "pet_name": "Daniya Summer",
  "default_scale": 1.0,
  "anchor": "bottom_center",
  "actions": {
    "idle": {
      "frames": ["daniya_summer/idle/idle_01.png", "daniya_summer/idle/idle_02.png"],
      "loop": true,
      "duration_ms": 700,
      "fallback": ["normal1.png"]
    },
    "talk": {
      "frames": ["daniya_summer/talk/talk_01.png", "daniya_summer/talk/talk_02.png"],
      "loop": true,
      "duration_ms": 180,
      "fallback": ["normal1.png", "normal2.png"]
    }
  }
}
```

**关键规则：**
1. 所有路径必须是相对 `assets/private/` 的相对路径，不要写绝对路径，路径分隔符建议使用 `/`。
2. 每一个动作必须包含 `fallback` 配置，保证在帧丢失时程序不会崩溃。

## 3. 核心动作组含义

- `idle`：桌面待机时的循环呼吸动画（推荐 2 帧以上）。
- `talk`：接收大模型回复时的说话动作，注意设计自然的口型开合（推荐 3 帧以上）。
- `clicked`：用户鼠标左键点击桌宠时触发的瞬间动作（可 1 帧）。
- `drag`：鼠标左键按住拖动桌宠时保持的动作（可 1 帧）。
- `sleep`：休眠或长时间无互动时的动作（推荐 1-2 帧循环）。
- `happy`：收到“抱抱”或好感度提升等开心事件时的动作。
- `remind`：定时提醒事件触发时的动作。

## 4. 素材制作规范

为了防止视觉突变或跳位，请遵循以下规范：

- **格式要求**：必须是 PNG 格式，并且必须包含 **透明背景 (Alpha 通道)**。没有透明通道会出现白底方框。
- **分辨率与画布**：同一动作组内所有帧的分辨率**必须绝对一致**。强烈建议所有 `idle`、`talk` 等核心动作组的图片也使用相同的总画布大小，这能极大避免状态切换时出现画面闪动。
- **人物中心 / 锚点**：系统默认采用 `bottom_center`（底部居中）对齐。请确保角色在每张图片中的底部中心（通常是双脚所站立的地面位置）在像素级坐标上保持一致，否则人物会发生左右或上下漂移跳动。

## 5. 素材检查工具

我们提供了一个资产检查器，可以用来扫描您的素材是否存在缺失或尺寸不一致问题。
在命令行中执行：
```bash
python tools/validate_assets.py assets/private
```
它会报告：
- 是否存在缺少 Alpha 透明通道的图片。
- 各组动作是否包含无效路径。
- 各组帧尺寸是否发生变异。

## 6. 在设置中心重载资源

当您在运行中更新了 `assets/private/` 下的图片或修改了 `manifest.json` 后，您不需要重启桌宠。
1. 右键桌宠打开“设置中心”。
2. 切换至 **“动作资源”** 选项卡。
3. 点击 **“重载动作资源”** 按钮即可即时生效。
4. 您也可以在该页面使用“动作测试”按钮，单独预览每一个动作的连贯性。

## 7. 打包与开源协议注意事项

- **不要将私有素材加入 Git 版本库**：`.gitignore` 已经配置了排除 `assets/private/`。请不要强制 `git add` 私有素材包，以免引发版权风险或仓库体积膨胀。
- **默认打包过滤**：在执行 `pack.bat` 生成发行版 zip 时，私有素材将自动被过滤，以保障默认 Release 是轻量且不侵权的占位符版本。
- **缺失时的保底 (Fallback)**：如果您将程序发送给朋友，且没有附带 `assets/private/` 文件夹，系统会自动退回加载 `assets/placeholder/` 中的极简测试图片，保证程序安全启动。

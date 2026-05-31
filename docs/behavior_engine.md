# 桌宠行为引擎 (PetBehaviorEngine) 设计与接口文档 (v0.55)

桌宠行为引擎负责管理和协调达妮娅桌面宠物的所有物理和交互行为。它封装了对鼠标点击、双击、长按、拖拽的分流检测，控制边缘吸附、防止移出屏幕、回弹动画、位置状态持久化，以及轻量级空闲行为触发。

---

## 1. 架构组成

行为引擎的源代码位于 `src/behavior/` 目录下，包含以下职责单一的子组件：

- **`behavior_config.py` (BehaviorConfig)**:
  读取并解析 `config/app_config.json` 中的行为层配置（如吸附阈值、长按时间、空闲延迟等）。

- **`interaction_detector.py` (InteractionDetector)**:
  交互类型分类器。负责在低级鼠标事件流中利用定时器区分以下事件：
  - **单击 (Single Click)**: 在松手后 300ms 内未收到第二次点击，则判定为单击。
  - **双击 (Double Click)**: 300ms 内连续两次点击释放，则取消单击并判定为双击。
  - **长按 (Long Press)**: 按下按钮 600ms 内未产生超过 8 像素的位移且未释放，判定为长按。
  - **拖拽 (Drag)**: 按下后任意位移超过 8 像素，立即取消点击/长按计时，强制转入拖动状态。

- **`drag_controller.py` (DragController)**:
  管理拖拽期间的位移计算与瞬时拖拽速度（velocity）记录。拖动时将触发 `"dragging"` 状态，控制桌宠播放拉扯 (`"drag"`) 动画。

- **`snap_controller.py` (SnapController)**:
  负责吸附与限制：
  - **边缘吸附**: 当释放位置距屏幕左边缘、右边缘或底边缘在配置像素（默认 24px）内时，自动吸附对齐。
  - **屏幕局限性**: 无论如何拖动，确保桌宠在可见范围内至少留有 32px 宽度/高度，防止丢失。
  - **回弹效果**: 若需进行修正或对齐，通过 `QPropertyAnimation` 提供平滑回弹。
  - **位置持久化**: 保存最新位置至 `data/window_state.json`。

- **`idle_behavior.py` (IdleBehavior)**:
  无操作检测。每隔 2 秒检测最后活动时间，若超出 `idle_behavior_seconds`（默认 90s），触发小幅度随机动作或气泡文本。
  - **打断规避**: 如果 LLM 对话中、打字机打字中、设置中心打开中或提醒框显示中，则不触发。

- **`behavior_engine.py` (PetBehaviorEngine)**:
  行为层的总线与外观（Facade），提供统一接口与 `PetWindow` 联动。

---

## 2. 配置项参数说明

在 `config/app_config.json` 中配置以下行为层参数：

```json
{
  "behavior_enabled": true,          // 是否启用行为引擎
  "snap_to_edge_enabled": true,      // 是否开启边缘吸附
  "snap_margin_px": 24,              // 吸附检测阈值（像素）
  "keep_on_screen_enabled": true,    // 强制保留在屏幕可见区
  "drag_return_enabled": true,       // 允许松手后自动平滑回弹
  "idle_behavior_enabled": true,     // 是否开启空闲阶段小动作
  "idle_behavior_seconds": 90,       // 判定为空闲的秒数
  "double_click_enabled": true,      // 是否启用双击互动
  "long_press_ms": 600               // 长按判定毫秒数
}
```

---

## 3. 位置保存规范

桌宠位置持久化保存在 `data/window_state.json` 中。
- **格式示例**:
  ```json
  {
    "x": 1200,
    "y": 680,
    "snap": "right",
    "updated_at": "2026-05-30 22:30:00"
  }
  ```
- **读取与安全恢复**:
  启动时，若读取到该文件且验证在有效屏幕边界内（且至少有 32px 可见），则在配置位置显示；如果文件损坏或不可用，将自动使用默认右下角对齐位置并重构文件，不影响正常启动。
- **保存时机**:
  1. 每次拖动释放结束，吸附回弹动画完成后。
  2. 窗口正常关闭事件 (`closeEvent`) 触发时。

---

## 4. 调试与验证方法

运行 `run.bat` 并进行以下测试：
1. **拖拽测试**: 鼠标左键按住立绘拖走，桌宠应立即换为拉扯动作，且在松手时换回 idle 状态。
2. **吸附测试**: 将桌宠拖至屏幕左/右/底边界（24px内），应自动平滑靠边。
3. **出界拉回**: 尝试将桌宠暴力拖出屏幕，松手后桌宠应优雅弹回并保持至少 32px 在屏幕内。
4. **单/双击测试**:
   - 快速单击立绘：触发 clicked 动画和常规互动语音。
   - 快速双击立绘：直接触发 happy 动画和亲近短语，且不会误判为单击或打开设置。

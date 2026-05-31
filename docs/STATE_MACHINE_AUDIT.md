# STATE_MACHINE_AUDIT

审计阶段：第一阶段，只读静态审计

## 状态参与者

| 参与者 | 文件 | 职责 | 风险 |
|---|---|---|---|
| `StateManager` | `src/state_manager.py` | 动作状态映射 | 静态上是局部状态，不是全局 arbiter |
| `AnimationManager` | `src/animation_manager.py` | 播放 action frames，回 idle | 可能被多来源调用 |
| `PetBehaviorEngine` | `src/behavior/behavior_engine.py` | 点击/拖拽/idle 行为 | 与 AppController/PetWindow 双向信号 |
| `InteractionDetector` | `src/behavior/interaction_detector.py` | 单击/双击/长按/拖拽识别 | 误判风险 |
| `SnapController` | `src/behavior/snap_controller.py` | 吸附与 window_state | 动画和状态保存交叉 |
| `Typewriter` | `src/typewriter.py` | talking/text queue | idle/behavior 需避让 |
| `IdleManager` | `src/idle_manager.py` | 旧 idle 陪伴 | 与 v0.55 IdleBehavior 并存 |
| `IdleBehavior` | `src/behavior/idle_behavior.py` | 新 idle 行为 | 与旧 IdleManager 并存 |
| `ReminderManager` | `src/reminder_manager.py` | 提醒到期 | remind 与 idle/talking 冲突风险 |
| `TimeEventManager` | `src/time_event_manager.py` | 整点报时 | 可能打断当前状态 |
| `DialogueEngine` | `core/dialogue_engine.py` | 返回 action/event | 与 UI 行为动作竞争 |

## 状态项审计

| 状态 | 当前静态来源 | 风险 |
|---|---|---|
| `base_state` | 未见单一显式字段 | 需要后续建立状态术语 |
| `temporary_state` | `StateManager`/Animation action 隐式承担 | 缺少统一生命周期描述 |
| `talking` | `PetWindow.speak`, `Typewriter`, `AnimationManager` | idle 行为应避让 typing |
| `idle` | `AnimationManager.play_idle`, `IdleManager`, `IdleBehavior` | 双 idle 系统并存 |
| `clicked` | `PetBehaviorEngine._handle_single_click`, `AppController.on_pet_clicked` | 需确认不会重复触发点击逻辑 |
| `dragging` | `InteractionDetector`, `DragController`, `AnimationManager.set_dragging` | 拖拽中事件/idle 需屏蔽 |
| `sleep` | `DayNightManager`, hidden command, special response | sleep 不应锁死技术问题 |
| `happy` | double click, affinity upgrade, special response | 需检查 cooldown 与重复加好感 |
| `remind` | reminder due, event action | 需检查是否被 idle 覆盖 |
| `random_event` | 事件/idle 相关 | 第一阶段未见完整 pending queue 验证 |
| `API responding` | `AppController.worker` | `is_idle_behavior_allowed()` 有保护 |
| `settings_open` | `AppController.settings_window` | `is_idle_behavior_allowed()` 有保护 |
| `reminder_showing` | `AppController.reminder_boxes` | `is_idle_behavior_allowed()` 有保护 |

## QTimer / Animation 矩阵

| Timer | 文件 | 间隔/触发 | 停止条件静态观察 |
|---|---|---|---|
| `animation_timer` | `src/animation_manager.py` | action frame duration | action loop/return idle |
| `char_timer` | `src/typewriter.py` | char interval | typewriter 完成 |
| `mouth_timer` | `src/typewriter.py` | mouth interval | typewriter 完成 |
| `auto_timer` | `src/typewriter.py` | auto next/hide | queue/hide |
| `IdleManager.timer` | `src/idle_manager.py` | 30s | 常驻 |
| `IdleBehavior.timer` | `src/behavior/idle_behavior.py` | 2s | 常驻 |
| `InteractionDetector.long_press_timer` | `src/behavior/interaction_detector.py` | long press ms | release/drag |
| `InteractionDetector.click_delay_timer` | `src/behavior/interaction_detector.py` | 300ms | double click/timeout |
| `ReminderManager.timer` | `src/reminder_manager.py` | 30s | 常驻 |
| `TimeEventManager.timer` | `src/time_event_manager.py` | 60s | 常驻 |
| `_drag_debounce` | `src/app.py` | 500ms | singleShot |
| `_anim` | `src/behavior/snap_controller.py` | 300ms | finished |

## 信号连接风险

静态关键连接：

- `PetWindow.message_submitted` -> `AppController.send_message`
- `PetWindow.pet_clicked` -> `AppController.on_pet_clicked`
- `PetWindow.activity_detected` -> `IdleManager.mark_activity`
- `PetWindow.activity_detected` -> `BehaviorEngine.mark_activity`
- `ReminderManager.reminder_due` -> `AppController.on_reminder_due`
- `IdleBehavior.idle_action_triggered` -> `PetBehaviorEngine._handle_idle_action`
- `SettingsWindow` 多个 worker finished signals

风险：

- `reload_character()` 更新 settings window 和 behavior config，但未在第一阶段动态验证是否重复连接。
- GUI 连续打开/关闭设置中心需要动态确认 `settings_window.finished` 清理。

## 是否存在永久卡状态

第一阶段结论：未能证明存在永久卡状态；状态为 `Needs dynamic verification`。

必须后续测试：

- API 回复中 idle 是否打断 talking。
- 拖拽过程中是否触发 idle/random/remind。
- sleep 后技术问题是否回答。
- typewriter 长文本是否能回 idle。
- snap 动画中再次拖拽是否正常。

## 第二阶段动态结果

结论：未稳定复现永久卡状态或 Timer 冲突；本阶段不修改状态机或 Timer。

动态证据：

| 场景 | base/current state | temporary/动作 | 触发模块 | 最终状态 | 结果 |
|---|---|---|---|---|---|
| 单击 | idle | clicked | `InteractionDetector` / `PetBehaviorEngine` | clicked 后回 idle | PASS |
| 双击 | idle | happy | `InteractionDetector` | 未触发两次 clicked | PASS |
| 长按 | idle | none | `InteractionDetector.long_press_timer` | idle | PASS |
| 大拖拽 | dragging | drag -> idle | `DragController` / `SnapController` | idle | PASS |
| 左/右边缘 | edge_peek_left/right | drag -> idle -> edge peek | `SnapController` / edge peek | edge peek 可见 | PASS |
| 拖出屏幕 | edge_peek_right | drag -> idle -> edge peek | `SnapController` | 保持可见区域 | PASS |
| API 回复中 idle | worker running | no idle action | `AppController.is_idle_behavior_allowed` | no change | PASS |
| 设置中心打开 idle | settings visible | no idle action | `AppController.is_idle_behavior_allowed` | no change | PASS |
| 拖拽中 idle/random | dragging | drag -> idle | `IdleBehavior` / detector | idle | PASS |
| typewriter 长文本 | talking | mouth/talk frames | `Typewriter` | idle, bubble hidden | PASS |
| sleep 后技术问题 | sleep -> task | model route | `DialogueEngine` | model response/action | PASS |
| reload 3 次 | idle | manifest reload | `AppController.reload_character` | no crash | PASS |

备注：

- 一次早期脚本运行曾观察到拖拽中额外 idle action，但修正误判条件后复跑未复现；当前记录为 transient observation，不作为 confirmed bug。
- 90 秒 wall-clock 等待未逐项完整执行；第二阶段使用时间戳回拨直接触发 idle 检查，以验证 guard 条件。后续若要做 soak test，可单独开长时运行监视。

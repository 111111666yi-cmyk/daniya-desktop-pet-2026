# 角色包制作指南 (Character Pack Guide)

本指南介绍如何在桌宠框架中制作、配置和测试一个新的角色包。

---

## 1. 快速开始：复制模板创建新角色

角色包统一存放在项目根目录下的 `characters/` 目录中。要新建一个角色，请直接复制 `characters/template` 模板文件夹。

假设你的新角色 ID 为 `my_character`：
1. 复制整个 `characters/template` 目录，并重命名为 `characters/my_character`。
2. 修改 `characters/my_character/character.yaml` 中的 `id` 字段为 `my_character`，并自定义 `display_name`（显示名称）。
3. 修改 `characters/my_character/relationship.yaml` 中的 `initial_state.character_id` 字段为 `my_character`。

---

## 2. 配置文件说明 (YAML)

每个角色包目录下包含以下核心配置文件：

| 文件名 | 用途 | 缺失时的 Fallback 行为 |
| :--- | :--- | :--- |
| `character.yaml` | 角色的核心人设信息、核心设定、禁止行为等。 | 回退到 `template/character.yaml` |
| `speech.yaml` | 对话风格、长短句限制和固定关键词回复（special_responses）。 | 回退到 `template/speech.yaml` |
| `relationship.yaml` | 初始好感度/熟悉度指标，以及 4 个阶段（初识、熟悉、亲近、依赖）的判定分值和文案。 | 回退到 `template/relationship.yaml` |
| `events.yaml` | 事件判定机制和特定触发条件。 | 回退到 `template/events.yaml` |
| `actions.yaml` | 本地行为映射定义，动作关联文本和兜底图。 | 回退到 `template/actions.yaml` |
| `lore.md` | 角色的背景百科/知识库（可选）。 | 视为无 lore，不报错。 |
| `lore_index.yaml` | lore 部分的片段索引和关联关键词（可选）。 | 视为无 lore 索引，不报错。 |
| `story.yaml` | 设置中心和右键菜单中的逐章剧情阅读内容（可选）。 | 显示“剧情未配置”安全占位，不影响对话。 |

---

## 3. 图片资源管理 (Assets)

每个角色的图片和动画配置文件应放置在 `characters/{character_id}/assets/` 目录下。

### 图片命名规范
- **默认立绘 1** (`normal1.png`): 基础静止状态（如睁眼、闭口）。
- **默认立绘 2** (`normal2.png`): 互动状态或张嘴对话状态。
- 如果需要更丰富的姿势/情绪，可以在 `assets/` 下划分子目录，例如 `idle/`、`talk/`、`happy/` 等，然后在 `manifest.json` 中配置引用。

---

## 4. 动画清单配置 (`manifest.json`)

`manifest.json` 用于指定角色在各种动作状态下播放的图片帧。它的基本结构如下：

```json
{
  "name": "my_character",
  "display_name": "我的新角色",
  "default_height": 96,
  "animations": {
    "idle": ["normal1.png"],
    "talk": ["normal1.png", "normal2.png"],
    "clicked": ["normal2.png"],
    "drag": ["normal2.png"],
    "sleep": ["normal1.png"],
    "happy": ["normal2.png"],
    "remind": ["normal2.png"]
  }
}
```

### 动画组 (Animation Groups)

若想实现更丰富的动态效果（例如概率触发动作、不同动作包分支），可以在 `animation_groups` 中定义帧序列、权重（weight）和动作包归属。具体可参考 `characters/daniya/assets/manifest.json` 的高级写法。

---

## 5. 无完整素材时的测试方法

当你还没有为新角色绘制好成套的表情包图时，可以通过以下步骤先用占位图验证逻辑：

1. **直接复用占位图**:
   在 `characters/{character_id}/assets/` 下只需放入两个通用的占位图 `normal1.png` 和 `normal2.png` 即可。

2. **触发全局兜底**:
   如果你的角色包目录没有放置任何 assets，程序会按照以下优先级自动进行图片 Fallback，**绝不会发生闪退**：
   - 1. 使用当前角色包 `assets/` 中的对应图片（如有）。
   - 2. 使用 `characters/template/assets/` 中的占位图片。
   - 3. 使用项目根目录 `assets/placeholder/` 中的通用占位图片（`normal1.png` / `normal2.png`）。

3. **缺失 Manifest 兜底**:
   如果新角色包缺 `manifest.json`，程序会自动继承 `template/assets/manifest.json` 的动作结构，如果 template 也没有，会自动生成默认映射：
   - `idle` / `sleep` -> `normal1.png`
   - `talk` -> `normal1.png` + `normal2.png`（循环播放）
   - `clicked` / `drag` / `happy` / `remind` -> `normal2.png`

4. **角色切换与运行态数据**:
   - Daniya 的关系状态继续保存在 `data/daniya_relation/relationship_state.json`，兼容旧版本。
   - 其他角色使用 `relationship_state.{character_id}.json`，切换角色不会把上一角色的关系数值套到新角色。
   - 用户记忆和事件日志仍在本地运行态目录中，并通过记录内的 `character_id` 区分来源。

---

## 6. 安全策略：如何避免将私有素材提交至 Git

为了防止私有的商用或个人画师素材被提交到公共代码仓库，我们已经在项目根目录的 `.gitignore` 中配置了通用过滤规则：

```gitignore
characters/*/assets/
!characters/template/assets/
```

### 规则解释：
- `characters/*/assets/`: **自动忽略**所有角色目录下的 `assets/` 文件夹（包括你的原画、子帧图和 `manifest.json`）。
- `!characters/template/assets/`: **保留特例**，允许提交模板角色的公开占位图，以便其他人克隆项目时能成功启动。

### 提示：
在创建新角色包时，只要图片保存在 `characters/{character_id}/assets/` 下，它们就会被 Git 自动忽略，无需手动修改 `.gitignore`。

---

## 7. 本地测试包策略

`characters/test_dummy/` 是本地占位测试包，只用于开发机上临时验证角色加载、fallback、动作 manifest 兼容性。

仓库正式回归测试不依赖 `test_dummy`，clean clone 不要求它存在，发布包也不包含它。公开示例角色请使用 `characters/daniya/`，正式 fallback 与新角色起点请依赖 `characters/template/`。

如果开发者需要本地 dummy 角色，可以复制 `characters/template/` 到 `characters/test_dummy/` 后自行改名测试；该目录默认仍保持 ignored/local-only。

如果未来需要把 `test_dummy` 作为公开 fixture，需要单独确认：

- 只提交非私有人设 metadata。
- assets 必须使用公开 placeholder。
- 不得包含私有素材、用户数据或真实项目 lore。
- 同步更新 `.gitignore` 例外规则和回归测试说明。

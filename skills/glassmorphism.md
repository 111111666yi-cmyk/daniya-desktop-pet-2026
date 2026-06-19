# Glassmorphism / Liquid Glass — 设计系统 Skill

> **禁止 AI slop。** 不要生成看起来"像那么回事"但经不起推敲的玻璃效果。每一个数值
> 都必须有明确来源（本文档、已验证的实现、或用户指定）。如果不确定，问，不要编。

---

## 0. 术语

| 术语 | 含义 |
|------|------|
| **Liquid Glass** | Apple iOS 26 引入的视觉语言：半透明材质+光线折射(lensing) |
| **Glassmorphism** | 泛指毛玻璃/磨砂玻璃 UI 风格，Liquid Glass 是其最新演化 |
| **Lensing** | 光线弯曲/聚焦，≠ 传统 blur 的散射。表现为低模糊+高饱和+光斑集中 |
| **Backdrop blur** | 模糊控件下方的背景内容 |
| **Frosted tint** | 模糊层之上的半透明着色层 |
| **Specular highlight** | 模拟光源的高光渐变 |
| **Rim** | 边缘发光描边（hairline border），制造厚度感 |

---

## 1. 核心原则（不可违反）

1. **玻璃只用在导航/工具层**，永远不要放在内容区或可滚动区域上
2. **禁止玻璃叠玻璃** — 一个视觉层级只能有一层玻璃
3. **透明度范围 20%–80%** — 低于 20% 看不出效果，高于 80% 失去"透"感
4. **深色背景优先** — 玻璃在深色/图片背景上效果最好，纯白背景上无意义
5. **不要在纯色背景上用 backdrop-filter** — 没有东西可以"透"过来，白费性能
6. **圆角一致** — 同一层级的玻璃组件圆角半径必须统一
7. **不要滥用** — 一个界面里最多 2-3 个玻璃组件。越少越高级

---

## 2. 两档玻璃参数

### 2.1 轻透 (liquid-glass)

用于：标签页、小卡片、badge、tag pill

| 属性 | 值 | 说明 |
|------|------|------|
| backdrop-filter blur | 6px | 轻微模糊，保留背景可辨识度 |
| saturate | 1.2 | 微增饱和 |
| background alpha | 0.02 (白) | 几乎全透，仅靠 blur 造型 |
| blend-mode | luminosity | 去色倾向，避免背景色干扰 |
| inset box-shadow (上) | 0 1px 1px rgba(255,255,255,0.12) | 顶部内阴影 → 厚度感 |
| inset box-shadow (下) | 0 -1px 1px rgba(255,255,255,0.04) | 底部内阴影 → 立体 |
| outer shadow | 0 2px 12px rgba(0,0,0,0.15) | 悬浮感 |
| border gradient | 170deg, 白0.5→0.15→0→0→0.12→0.4 | mask-composite: exclude 实现的渐变边框 |
| specular glow | radial-gradient at 30% 20%, 白0.04→transparent | 模拟顶部光源 |

### 2.2 厚磨砂 (liquid-glass-strong)

用于：导航栏、主 CTA 按钮、模态底座

| 属性 | 值 | 说明 |
|------|------|------|
| backdrop-filter blur | 60px | 完全看不清背景，纯质感 |
| saturate | 1.3 | 饱和更高 |
| background alpha | 0.04 (白) | 略重于轻透 |
| inset box-shadow (上) | 0 1px 2px rgba(255,255,255,0.18) | |
| inset box-shadow (下) | 0 -1px 1px rgba(255,255,255,0.06) | |
| outer shadow | 0 8px 32px rgba(0,0,0,0.2) | 更强悬浮 |
| border gradient | 同上但白色 alpha 略高 (0.55/0.2/0.18/0.5) | |
| specular glow | at 25% 15%, 白0.06→transparent | |

---

## 3. PySide6 / Qt 实现映射

Web CSS 没有直接对应 Qt API，以下是逐层映射：

### 3.1 Backdrop Blur

Qt 没有 `backdrop-filter`。实现方法：

```
1. 父窗口/对话框启动时，将完整背景渲染到一张 QPixmap
2. 对该 pixmap 施加 QGraphicsBlurEffect（或手动 box-blur）生成 _bg_blur
3. 玻璃子组件 paintEvent 中：
   a. mapTo(dialog, QPoint(0,0)) 算出自己在对话框坐标系的位置
   b. 从 _bg_blur 裁剪对应区域绘制
   c. 叠加 frosted tint / specular / rim
```

已有实现参考：`src/story_window.py` 的 `_GlassBar` class。

### 3.2 Frosted Tint

```python
fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
fill.setColorAt(0.0, QColor(255, 255, 255, top_alpha))
fill.setColorAt(1.0, QColor(255, 255, 255, bot_alpha))
painter.fillPath(clipped_path, fill)
```

alpha 值根据 glass_tint 滑块动态计算：
- 轻透: top = 10 + tint * 62, bot = 5 + tint * 42
- 厚磨砂: top = 20 + tint * 80, bot = 10 + tint * 60

### 3.3 Specular Highlight

```python
spec = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.6))
spec.setColorAt(0.0, QColor(255, 255, 255, spec_alpha))
spec.setColorAt(1.0, QColor(255, 255, 255, 0))
painter.fillPath(clipped_path, spec)
```

### 3.4 Rim (Edge Glow)

```python
rim = QLinearGradient(rect.topLeft(), rect.bottomLeft())
rim.setColorAt(0.0, QColor(255, 255, 255, rim_top))
rim.setColorAt(0.5, QColor(255, 255, 255, rim_mid))
rim.setColorAt(1.0, QColor(255, 255, 255, rim_bot))
painter.setPen(QPen(QBrush(rim), 1.0))
painter.drawPath(path)
```

### 3.5 鼠标跟随高光 (Mouse Glow)

```python
def mouseMoveEvent(self, event):
    self._glow_pos = event.position()
    self.update()

# 在 paintEvent 中：
glow = QRadialGradient(self._glow_pos, 180)
glow.setColorAt(0.0, QColor(255, 255, 255, 20))
glow.setColorAt(0.7, QColor(255, 255, 255, 0))
painter.fillPath(path, glow)
```

---

## 4. iOS 26 Liquid Glass 特有约束

来源：Apple WWDC25 / developer.apple.com/design

1. **Lensing 不是 blur** — 真正的 Liquid Glass 会聚焦（弯曲）背景光线，
   而不是像传统毛玻璃那样散射。在 Qt 中近似方法：
   - 低 blur radius（6-12px 而非 40-60px）
   - 背景区域微量放大（scale 1.02-1.05）模拟折射
   - 更高饱和度（saturate 1.2-1.4）
   
2. **GlassEffectContainer** — 多个玻璃元素应共享一个容器，而非各自独立模糊。
   Qt 实现：父 widget 持有 `_bg_blur` pixmap，所有子 glass widget 共用它

3. **尺寸响应** — 玻璃组件大小变化时，模糊强度不应改变（不要 blur = width * factor）

4. **暗色模式优先** — Liquid Glass 在暗色主题下表现最佳。
   亮色主题下降级为 tinted card（有背景色但不模糊）

5. **动画帧率** — 玻璃区域的动画必须保持 60fps。
   如果 blur 导致卡顿，缓存 blur pixmap 而非每帧重算

---

## 5. 动画规范

### 5.1 入场动画：fadeInUp

```
属性: y 偏移 28px → 0, opacity 0 → 1, blur 6px → 0
时长: 0.7s
缓动: ease-out
```

Qt 映射：QPropertyAnimation 组合（pos + opacity via QGraphicsOpacityEffect + blur via QGraphicsBlurEffect）

### 5.2 入场动画：blurWord（逐词模糊入场）

```
每个字/词拆成独立 QLabel
阶段 1 (0%):   blur(10px), opacity(0), y(+40px)
阶段 2 (50%):  blur(4px),  opacity(0.6), y(-3px)
阶段 3 (100%): blur(0),    opacity(1),   y(0)
时长: 0.7s per word
缓动: ease-out
stagger: delay = index * 0.1s
```

### 5.3 鼠标悬停：卡片抬升

```
transform: translateY(-6px) scale(1.015)
box-shadow 加深
transition: 0.35s cubic-bezier(0.22, 0.68, 0, 1.1)
```

Qt：QPropertyAnimation on pos + 动态修改 QGraphicsDropShadowEffect

---

## 6. 配色约束

- 背景色: `#0a0a14` → `#10101f` → `#0c0a18` (135deg 渐变)
- 主强调色: 金色系 `#d9bd7e` / `#c4a35a` / `rgba(196,163,90,*)`
- 文字白: `rgba(255,255,255,0.85)` (正文), `rgba(255,255,255,0.5)` (次要)
- **禁止**: 白字放在白色/浅色/绿色背景上
- **禁止**: 视频/图片背景上加彩色遮罩（对比度由玻璃组件自身处理）

---

## 7. 字体系统

| 用途 | 字体 | 备选 |
|------|------|------|
| 标题 | Instrument Serif (italic) | Georgia, 宋体 |
| 正文 | Barlow 300/400/500/600 | Segoe UI, 微软雅黑 |

Qt 中如果不捆绑字体，回退到系统字体。标题用 serif + italic，正文用 sans-serif。

---

## 8. 清单：实现前自查

- [ ] 背景是深色/图片吗？（纯色不用玻璃）
- [ ] 这一层有没有已经存在的玻璃？（禁止叠加）
- [ ] 这个组件是导航/工具层吗？（内容区不用）
- [ ] 透明度在 20%-80% 范围内吗？
- [ ] 圆角和同层其他组件一致吗？
- [ ] blur pixmap 是缓存的还是每帧重算的？（必须缓存）
- [ ] 60fps 能跑住吗？（不能就降级去掉 blur）
- [ ] 有没有写出 AI slop？（模糊的、不可验证的、堆砌的效果描述 = slop）

---

## 9. 反模式（禁止）

| 做法 | 为什么是 slop |
|------|------|
| blur radius > 80px | 变成磨砂墙，失去"玻璃"感 |
| 玻璃叠玻璃 | 视觉混乱，性能灾难 |
| 给每个 widget 独立算 blur | 应该共享父级的 _bg_blur pixmap |
| 在 QScrollArea 内容上放玻璃 | 滚动时需要每帧重算 blur 区域，卡死 |
| "加个玻璃效果看起来更高级" | 没有功能目的的装饰 = slop |
| opacity: 0.01 的"玻璃" | 看不见 = 没有意义 |
| 用 QGraphicsBlurEffect 作为 backdrop | 这个 effect 作用于 widget 自身，不是背景 |
| 每帧 grabWindow / render 做实时 blur | CPU 自杀。缓存 + 只在背景变化时更新 |

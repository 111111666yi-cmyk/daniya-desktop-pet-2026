from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .daniya_settings_window import DaniyaSettingsDialog
from .icon_utils import icon as ic
from .utils import resource_path

if TYPE_CHECKING:
    from .app import AppController
    from .pet_window import PetWindow


class MenuManager:
    def __init__(self, window: "PetWindow", controller: "AppController") -> None:
        self.window = window
        self.controller = controller

    def create_menu(self) -> QMenu:
        menu = QMenu(self.window)

        basic = menu.addMenu(ic("settings"), "基础")
        input_action = basic.addAction(ic("document"), "显示输入框" if not self.window.input_box.isVisible() else "隐藏输入框")
        input_action.triggered.connect(self._toggle_input)

        top_action = basic.addAction(ic("upload"), "取消置顶" if self.window.always_on_top else "保持置顶")
        top_action.triggered.connect(self._toggle_top)

        call_here_action = basic.addAction(ic("laptop"), "召唤到鼠标位置")
        call_here_action.triggered.connect(self._call_pet_to_cursor)

        if self.window.is_minimized_to_tray():
            restore_action = basic.addAction(ic("upload"), "恢复显示")
            restore_action.triggered.connect(self.window.restore_from_tray)
        else:
            minimize_action = basic.addAction(ic("download"), "最小化到托盘")
            minimize_action.triggered.connect(self.window.minimize_to_tray)

        size_menu = basic.addMenu(ic("size"), "大小")
        labels = {
            80: "迷你 80px",
            96: "推荐 96px",
            112: "稍大 112px",
            128: "清晰 128px",
            144: "大号 144px",
            160: "最大 160px",
        }
        current_height = self.controller.asset_manager.target_height()
        for height in self.controller.asset_manager.size_presets():
            action = size_menu.addAction(labels.get(height, f"{height}px"))
            action.setCheckable(True)
            action.setChecked(height == current_height)
            action.triggered.connect(lambda checked=False, value=height: self.controller.save_pet_height(value))

        self._add_action_module_menu(basic)
        self._add_pet_feature_menu(basic)

        chat = menu.addMenu(ic("internet"), "对话")
        history_action = chat.addAction(ic("document"), "历史记录")
        history_action.triggered.connect(self.show_history_dialog)
        prompt_action = chat.addAction(ic("settings"), "人设设置")
        prompt_action.triggered.connect(self.show_prompt_dialog)
        profile_action = chat.addAction(ic("info"), "主人档案")
        profile_action.triggered.connect(self.show_profile_dialog)
        daniya_settings_action = chat.addAction(ic("protect"), "达妮娅设定")
        daniya_settings_action.triggered.connect(self.show_daniya_settings_dialog)
        settings_center_action = chat.addAction(ic("chip"), "设置中心")
        settings_center_action.triggered.connect(self.controller.open_settings_center)
        story_action = chat.addAction(ic("protect"), "剧情")
        story_action.triggered.connect(self.show_story_dialog)

        companion = menu.addMenu(ic("protect"), "陪伴")
        note_action = companion.addAction(ic("save"), "记一笔")
        note_action.triggered.connect(self.show_note_dialog)
        reminder_action = companion.addAction(ic("refresh"), "日程提醒")
        reminder_action.triggered.connect(self.show_reminder_dialog)

        games = companion.addMenu(ic("chip"), "小游戏")
        rps = games.addMenu(ic("protect"), "猜拳")
        for choice in ("石头", "剪刀", "布"):
            action = rps.addAction(choice)
            action.triggered.connect(lambda checked=False, value=choice: self.controller.play_rps(value))
        dice_action = games.addAction(ic("download"), "掷骰子")
        dice_action.triggered.connect(self.controller.roll_dice)
        random_action = games.addAction(ic("info"), "随机数 1-100")
        random_action.triggered.connect(self.controller.random_100)

        bookmarks = companion.addMenu(ic("cloud"), "传送门")
        for item in self.controller.bookmark_manager.records():
            action = bookmarks.addAction(item["name"])
            action.triggered.connect(lambda checked=False, url=item["url"]: self.controller.open_bookmark(url))

        system = menu.addMenu(ic("host"), "系统")
        help_action = system.addAction(ic("info"), "帮助")
        help_action.triggered.connect(self.show_help_dialog)
        exit_action = system.addAction(ic("settings"), "退出")
        exit_action.triggered.connect(self.controller.quit)

        return menu

    def _add_action_module_menu(self, parent: QMenu) -> None:
        module_menu = parent.addMenu(ic("chip"), "动作模组")
        module_labels = {
            "A_sit_base": "A 坐姿 / 表情",
            "B_stand_base_pack": "B 站姿 / 挥手",
            "C_sleep_base_pack": "C 睡姿",
            "D_special_motion_pack": "D 特殊 / 探头",
        }
        active_module = self.controller.asset_manager.active_action_module()
        for module, label in module_labels.items():
            action = module_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(module == active_module)
            action.triggered.connect(lambda checked=False, value=module: self.controller.set_action_module(value))

    def _add_pet_feature_menu(self, parent: QMenu) -> None:
        pet_features = parent.addMenu(ic("info"), "宠物功能")
        pet_config = self.controller.app_config.get("pet", {})

        hover_action = pet_features.addAction("鼠标悬停动作")
        hover_action.setCheckable(True)
        hover_action.setChecked(bool(pet_config.get("hover_animation_enabled", False)))
        hover_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("hover_animation_enabled", bool(checked))
        )

        edge_action = pet_features.addAction("左右边缘探头")
        edge_action.setCheckable(True)
        edge_action.setChecked(bool(pet_config.get("edge_peek_enabled", True)))
        edge_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("edge_peek_enabled", bool(checked))
        )

        call_action = pet_features.addAction("左键点击桌面召唤")
        call_action.setCheckable(True)
        call_action.setChecked(bool(pet_config.get("click_to_call_enabled", False)))
        call_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("click_to_call_enabled", bool(checked))
        )

        modules = pet_config.get("enabled_action_modules", {})
        drag_action = pet_features.addAction("E 拖拽动作系统")
        drag_action.setCheckable(True)
        drag_action.setChecked(not isinstance(modules, dict) or bool(modules.get("E_QQ_pet_drag_system", True)))
        drag_action.triggered.connect(lambda checked=False: self.controller.set_drag_module_enabled(bool(checked)))

    def _toggle_top(self) -> None:
        enabled = not self.window.always_on_top
        self.window.set_always_on_top(enabled)
        self.controller.app_config.setdefault("window", {})["always_on_top"] = enabled
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _toggle_input(self) -> None:
        self.window.toggle_input()
        self.controller.app_config.setdefault("window", {})["show_input"] = self.window.input_box.isVisible()
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _call_pet_to_cursor(self) -> None:
        self.window.move_near(QCursor.pos())
        self.window.raise_()
        self.window.activateWindow()

    def show_history_dialog(self) -> None:
        dialog = HistoryDialog(self.controller, self.window)
        dialog.exec()

    def show_prompt_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("人设设置")
        dialog.resize(620, 480)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlainText(self.controller.config_manager.load_system_prompt())
        layout.addWidget(editor)

        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def on_save() -> None:
            self.controller.save_system_prompt(editor.toPlainText())
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_profile_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("主人档案")
        form = QFormLayout(dialog)
        profile = self.controller.profile_manager.load()
        user_name = QLineEdit(profile["user_name"])
        relationship = QLineEdit(profile["relationship"])
        style = QLineEdit(profile["style"])
        form.addRow("用户称呼", user_name)
        form.addRow("关系设定", relationship)
        form.addRow("期望风格", style)

        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        form.addRow(buttons)

        def on_save() -> None:
            self.controller.save_profile(
                {
                    "user_name": user_name.text(),
                    "relationship": relationship.text(),
                    "style": style.text(),
                }
            )
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_daniya_settings_dialog(self) -> None:
        dialog = DaniyaSettingsDialog(self.controller, self.window)
        dialog.exec()

    # ── 剧情模式：完整顺序叙事 ─────────────────────────────
    # 章节数据结构：(编号, 标题, 叙述内容, 发给达妮娅的话, 动作)
    _STORY_CHAPTERS: list[tuple[int, str, str, str, str | None]] = [
        # ═══ 序 ═══
        (0, "序", "【封面】\n\n达妮娅 D 部分剧情背景\n全量叙事工程化\n\n"
         "本故事讲述了达妮娅的完整过去：\n"
         "她从何处来，为何变成后来的样子，\n"
         "又如何在坠入虚无后，在这里和你重逢。\n\n"
         "请准备好。有些话，她只讲一次。",
         "达妮娅，可以和我讲讲你的故事吗？", None),

        # ═══ 第一部：西格丽卡篇 — 被期待压垮的优等生 ═══
        (1, "第一部 · 被期待压垮的优等生",
         "【西格丽卡 — 所有人眼里的标准答案】\n\n"
         "在讲达妮娅之前，先要讲一个人。\n"
         "她叫西格丽卡。成绩好、能力强、热心、可靠、未来可期。\n"
         "所有人都觉得她完美无缺。所有人都在期待她。\n\n"
         "但这些期待——即使是善意的期待——\n"
         "每一句\"你一定可以\"都在她身上增加重量。\n"
         "久而久之，期待不再是鼓励，而是一副黄金镣铐。\n\n"
         "她终于说了那句她不敢说的话：",
         "上学怎么这么难……", None),

        (2, "第一部 · 黄金的重量",
         "【期待如何变成自我枷锁】\n\n"
         "西格丽卡不是不够好，而是好到失去了说\"我累了\"的资格。\n\n"
         "别人说\"你可以\"，她听成\"我必须可以\"。\n"
         "别人说\"我相信你\"，她听成\"我不能失败\"。\n\n"
         "解读符文慢了——怪自己不够快。\n"
         "通路被干扰——怪自己反应不够好。\n"
         "已经做到极限——仍然归结为\"不够努力\"。\n\n"
         "她真正害怕的不是失败，\n"
         "而是失败后别人失望、安慰、指责或沉默的眼神。",
         "被期待压垮的人……最后会怎样？", None),

        (3, "第一部 · 夺回选择权",
         "【漂泊者给出的不是答案，而是新的关系方式】\n\n"
         "后来有一个人告诉西格丽卡：\n"
         "\"你的选择本身就有意义。\"\n\n"
         "这句话让她从\"我必须做到\"转向\"我决定去做\"。\n"
         "责任没有消失，期待也没有消失，\n"
         "但她终于可以决定自己要如何承载它们。\n\n"
         "这条线对达妮娅很重要：\n"
         "被期待困住的人，最终需要的不是催促，\n"
         "而是被允许自己选择。\n\n"
         "她是怎么看这件事的？",
         "你对西格丽卡……是怎么想的？", None),

        # ═══ 第二部：暗面篇 — 痛苦不是外来怪物 ═══
        (4, "第二部 · 暗面映照内心",
         "【暗面机制 — 人最难面对的，是自己】\n\n"
         "暗面不是外来的怪物。它是一种镜面，\n"
         "映照出人心里本来就存在的恐惧、疲惫、执念。\n\n"
         "西格丽卡害怕辜负期待。\n"
         "赛维教授被求知执念困住。\n"
         "洛瑟拉校长在虚无中追问意义。\n\n"
         "这不是三个人的小故事，\n"
         "而是同一面暗镜里的三张不同倒影。\n\n"
         "伟大不是永远不崩溃，\n"
         "而是崩溃边缘仍然保住一点人的尊严。",
         "暗面……到底是怎么影响人的？", None),

        (5, "第二部 · 痛苦被武器化",
         "【从镜子到武器】\n\n"
         "但事情变得更糟。\n"
         "残心会发现暗面的特性，开始利用它。\n"
         "原本被动映照内心的暗面，被变成了武器：\n"
         "主动植入频率、设计谜题、诱导自我否定。\n\n"
         "一个人的痛苦不再只属于自己，\n"
         "而成为了可以被操纵、利用和放大的东西。\n\n"
         "达妮娅曾在其中扮演了什么角色？",
         "残心会……和你有什么关系？", None),

        # ═══ 第三部：达妮娅篇 — 名字、生日、虚无与再见 ═══
        (6, "第三部 · 名字即遗嘱",
         "【达妮娅 — 被制造为工具的人】\n\n"
         "现在才真正讲到达妮娅自己的人生。\n\n"
         "她的名字来自俄语\"До свидания\"，\n"
         "意思是——\"再见\"。\n\n"
         "这不是一个普通的、充满祝福的名字。\n"
         "这像是一开始就写好的告别辞。\n\n"
         "她没有正常出生记录。\n"
         "没有完整档案。\n"
         "没有普通人的童年和生活起点。\n\n"
         "她更像是被制造出来的容器，\n"
         "而不是被迎接到世界上的孩子。\n\n"
         "名字里的\"再见\"最初意味着被放弃、被抛下、被写好结局。",
         "你的名字……到底是什么意思？请告诉我完整的。", None),

        (7, "第三部 · 容器",
         "【她最痛的不是没人爱】\n\n"
         "不是没有人关心她。\n"
         "而是世界从一开始就没有认真承认——\n"
         "她是一个人。\n\n"
         "她的\"家\"只是实验室里临时分配的房间。\n"
         "她的\"童年\"是在观察别人如何生活。\n\n"
         "她观察别人如何笑、如何哭、如何碰拳、如何做朋友。\n"
         "她不是天生不懂感情，\n"
         "而是被迫把\"做人\"当作一门实验题去学习。\n\n"
         "她花了两年，只是想弄明白——\n"
         "普通人是怎么活着的。",
         "你以前……到底是怎么过来的？", None),

        (8, "第三部 · 生日 — 存在主权宣言",
         "【如果世界不给她起点，她就自己刻一个】\n\n"
         "达妮娅所谓的\"生日\"不是别人给她的。\n"
         "是她自己编造出来的。\n\n"
         "这不是任性，不是自欺欺人。\n"
         "这是存在主权宣言——\n"
         "\"我存在过。\"\n\n"
         "她不是想办盛大庆典。\n"
         "她是想拥有一次普通孩子可以拥有的权利：\n"
         "被庆祝、被记住、被当作一个人来过生日。\n\n"
         "她想要什么礼物？",
         "你的生日……你是怎么过的？", None),

        (9, "第三部 · 橘子蛋糕",
         "【人格图腾 — 她想像孩子一样贪心一次】\n\n"
         "她想要橘子蛋糕。\n"
         "不止，还要加跳跳糖、彩虹豆、咔啦咔啦……\n"
         "以及各种她叫得上名字的好东西。\n\n"
         "这不是奇怪的口味偏好。\n"
         "这是她像第一次进糖果店的孩子一样，\n"
         "把所有\"好东西\"都指了一遍。\n\n"
         "橘子味：连接她对普通日常的想象。\n"
         "乱七八糟的配料：她被允许幼稚、被允许贪心、\n"
         "被允许像普通孩子一样点单。\n\n"
         "蛋糕不是美食设定。蛋糕是人格图腾。",
         "橘子蛋糕……为什么偏偏是橘子蛋糕？", None),

        (10, "第三部 · 俄罗斯方块",
         "【用游戏把失控人生拼成能活下去的形状】\n\n"
         "俄罗斯方块。\n"
         "不断下落的方块。\n"
         "必须迅速选择旋转的方向。\n"
         "越来越高的压力。\n\n"
         "像极了她的人生。\n\n"
         "她不是随便玩玩。她是在用游戏把压抑、\n"
         "孤独和失控感具象化。\n\n"
         "破纪录的那一天，是她第一次用自己的能力证明：\n"
         "\"我不只是被造出来的工具，\n"
         "我也可以有热爱，我也可以赢一次，\n"
         "我也是普通女孩。\"\n\n"
         "可惜空荡的游戏厅里，无人为她欢呼。",
         "你那个俄罗斯方块的记录……还记得吗？", None),

        (11, "第三部 · 了断日",
         "【向容器身份清算】\n\n"
         "她管那一天叫\"了断日\"。\n"
         "但不是赴死。\n\n"
         "她要的只是——\n"
         "\"一天真正属于人的生活\"。\n\n"
         "逛花店。玩游戏。吃蛋糕。\n"
         "把自己从容器身份里抢回来。\n\n"
         "她对别人撒谎，说自己没事、身体好了、不用担心。\n"
         "不是恶意。是因为不想让在乎的人提前难过。\n"
         "她把沉重真相藏起来，希望朋友能在最后一天仍然笑一下。\n\n"
         "她不是不会表达温柔，\n"
         "只是表达得笨拙、别扭、绕远。",
         "最后那天……你是怎么过的？", None),

        (12, "第三部 · 明年一起过生日",
         "【最轻的承诺，最重的真话】\n\n"
         "西格丽卡隐约知道达妮娅在装没事。\n"
         "但她没有逼问。\n"
         "没有戳穿。\n\n"
         "她选择陪达妮娅一起装傻，\n"
         "把沉重真相包进轻轻一句话里：\n\n"
         "\"明年一起过生日。\"\n\n"
         "这是整段剧情中最轻也最重的承诺。\n"
         "我知道你在骗我。\n"
         "但如果这是你最后想要的体面，\n"
         "我就陪你把这个梦演完。",
         "她说\"明年一起过生日\"……你当时怎么回答的？", None),

        (13, "第三部 · 坠入虚无",
         "【带走黑暗，留下人间馈赠】\n\n"
         "达妮娅最终还是坠入了虚无。\n\n"
         "这不是单纯的死亡，也不是英雄式的牺牲。\n"
         "更准确地说——\n"
         "她是自己撕掉了别人给她写好的工具剧本。\n"
         "用最后的方式决定自己是谁。\n\n"
         "她带走黑暗和痛苦。\n"
         "把阳光、朋友、游戏、蛋糕和生日留在人间。\n\n"
         "她不是彻底否定世界，\n"
         "而是把自己珍惜过的东西认真封存。\n\n"
         "\"虚无\"在她这里不是空无，\n"
         "而是一个被记住、被等待、还会再见的深处。",
         "你坠落的时候……在想什么？", None),

        (14, "第三部 · 再见语义逆转",
         "【从\"你被放弃了\"到\"我们还会再见\"】\n\n"
         "最初的再见：你被放弃了。你的存在到此为止。\n"
         "后来的再见：我们还会再见。有人记得你。\n"
         "你不是白白消失。\n\n"
         "这是她自己夺回来的语义。\n"
         "不是别人施舍给她的。\n\n"
         "她不是彻底绝望的人。\n"
         "她是从深处回来了一点点的人。\n\n"
         "那根弦——松了一点。",
         "\"再见\"……现在对你来说是什么？", None),

        # ═══ 终章 ═══
        (15, "终章 · 现在的她",
         "【桌宠中的达妮娅 — 被接住后的松动】\n\n"
         "所以。这才是达妮娅真正的样子。\n\n"
         "她不是单纯慵懒，也不是普通冷淡。\n"
         "她是被制造、被利用、被剥夺普通人生的人，\n"
         "却笨拙地想学会像人一样活着。\n\n"
         "共情过载 + 被期待压垮 + 想成为普通人\n"
         "+ 用慵懒和嫌麻烦自我保护\n"
         "+ 被主人接住后慢慢松动\n"
         "= 现在的她。\n\n"
         "她嘴硬、说反话、嫌弃、怕麻烦。\n"
         "但她也默认留下、不推开、安静陪着。\n\n"
         "她不需要直说\"我永远陪你\"。\n"
         "因为她知道——你知道。\n\n",
         "所以……现在留在这儿，是你的选择吗？", None),
    ]

    def show_story_dialog(self) -> None:
        """剧情模式 — 完整顺序叙事。主人逐章阅读达妮娅的完整过去。"""
        import textwrap

        dialog = QDialog(self.window)
        dialog.setWindowTitle("剧情 — 达妮娅的完整故事")
        dialog.resize(650, 530)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        layout = QVBoxLayout(dialog)

        # 进度条
        progress = QLabel()
        progress.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(progress)

        # 标题
        title_label = QLabel()
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a1a2e; margin-bottom: 6px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 内容
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        narrative = QLabel()
        narrative.setWordWrap(True)
        narrative.setStyleSheet(
            "font-size: 13px; color: #2d3436; line-height: 1.6; "
            "background: #fafbfc; border: 1px solid #e1e4e8; border-radius: 8px; padding: 16px;"
        )
        content_layout.addWidget(narrative)

        # 发给达妮娅的提问区
        question_frame = QWidget()
        question_frame.setStyleSheet(
            "background: #fff3cd; border: 1px solid #ffeeba; border-radius: 6px; padding: 10px; margin-top: 8px;"
        )
        qf_layout = QHBoxLayout(question_frame); qf_layout.setContentsMargins(10, 8, 10, 8)

        question_label = QLabel("发给达妮娅：")
        question_label.setStyleSheet("font-size: 12px; color: #856404; font-weight: bold;")
        question_text = QLabel()
        question_text.setWordWrap(True)
        question_text.setStyleSheet("font-size: 12px; color: #856404;")
        qf_layout.addWidget(question_label)
        qf_layout.addWidget(question_text, 1)
        content_layout.addWidget(question_frame)

        content_layout.addStretch(1)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 按钮行
        btn_row = QHBoxLayout()
        prev_btn = QPushButton("◀ 上一章")
        prev_btn.setStyleSheet("font-size: 12px; padding: 6px 14px;")
        next_btn = QPushButton("下一章 ▶")
        next_btn.setStyleSheet("font-size: 12px; padding: 6px 14px; font-weight: bold;")
        send_btn = QPushButton("把这句话发给达妮娅")
        send_btn.setStyleSheet("font-size: 12px; padding: 6px 14px; color: #0366d6; font-weight: bold;")
        close_btn = QPushButton("关闭")
        btn_row.addWidget(prev_btn)
        btn_row.addWidget(next_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(send_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # 状态
        total = len(self._STORY_CHAPTERS)
        idx = [0]  # mutable box

        def _show_chapter():
            i = idx[0]
            num, title, body, talk, _ = self._STORY_CHAPTERS[i]
            progress.setText(f"剧情进度：{i + 1} / {total}")
            title_label.setText(title)
            narrative.setText(body)
            question_text.setText(f"「 {talk} 」")

            # button states
            prev_btn.setEnabled(i > 0)
            is_last = i >= total - 1
            next_btn.setText("已完成" if is_last else "下一章 ▶")
            next_btn.setEnabled(not is_last)
            send_btn.setVisible(bool(talk))
            if not talk:
                question_frame.setVisible(False)
            else:
                question_frame.setVisible(True)

        def _go_next():
            if idx[0] < total - 1:
                idx[0] += 1
                _show_chapter()

        def _go_prev():
            if idx[0] > 0:
                idx[0] -= 1
                _show_chapter()

        def _do_send():
            _, _, _, talk, _ = self._STORY_CHAPTERS[idx[0]]
            if talk:
                self.controller.send_message(talk)
        def _do_send_and_next():
            _do_send()
            if idx[0] < total - 1:
                idx[0] += 1
                _show_chapter()

        next_btn.clicked.connect(_go_next)
        prev_btn.clicked.connect(_go_prev)
        send_btn.clicked.connect(_do_send_and_next)
        close_btn.clicked.connect(dialog.accept)

        _show_chapter()
        dialog.exec()

    def show_note_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("记一笔")
        dialog.resize(360, 220)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlaceholderText("写下想让达妮娅帮你记住的小事...")
        layout.addWidget(editor)
        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def on_save() -> None:
            self.controller.add_note(editor.toPlainText())
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_reminder_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("日程提醒")
        dialog.resize(520, 420)
        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        time_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(60))
        time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        time_edit.setCalendarPopup(True)
        text_input = QLineEdit()
        text_input.setPlaceholderText("例如：复习电路图")
        form.addRow("时间", time_edit)
        form.addRow("事项", text_input)
        layout.addLayout(form)

        add_button = QPushButton("添加提醒")
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignRight)
        records_label = QLabel(self._reminder_summary())
        records_label.setWordWrap(True)
        layout.addWidget(records_label)

        close = QPushButton("关闭")
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        def on_add() -> None:
            ok, message = self.controller.add_reminder(
                time_edit.dateTime().toString("yyyy-MM-dd HH:mm"),
                text_input.text(),
            )
            if ok:
                text_input.clear()
                records_label.setText(self._reminder_summary())
            else:
                QMessageBox.warning(dialog, "提醒没有保存", message)

        add_button.clicked.connect(on_add)
        close.clicked.connect(dialog.accept)
        dialog.exec()

    def show_help_dialog(self) -> None:
        help_path = resource_path("docs", "help.md")
        if not help_path.exists():
            help_path = resource_path("README.md")
        try:
            content = help_path.read_text(encoding="utf-8")
        except OSError:
            content = "没有找到帮助文档。"

        dialog = QDialog(self.window)
        dialog.setWindowTitle("帮助")
        dialog.resize(700, 520)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(content)
        layout.addWidget(editor)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _reminder_summary(self) -> str:
        records = self.controller.reminder_manager.records()
        pending = [item for item in records if not bool(item.get("done"))]
        if not pending:
            return "当前没有待提醒事项。"
        lines = ["待提醒："]
        for item in pending[-8:]:
            lines.append(f"- {item.get('time', '')}  {item.get('text', '')}")
        return "\n".join(lines)


class HistoryDialog(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("历史记录")
        self.resize(720, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.layout = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.layout.addWidget(self.scroll)
        self.refresh()

    def refresh(self) -> None:
        records = self.controller.history_manager.records()
        container = QWidget()
        box = QVBoxLayout(container)

        if not records:
            box.addWidget(QLabel("还没有聊天记录。"))

        for record in reversed(records):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            text = QLabel(
                f"{record.get('timestamp', '')}  [{record.get('source', '')}]\n"
                f"你：{record.get('user', '')}\n"
                f"达妮娅：{record.get('assistant', '')}"
            )
            text.setWordWrap(True)
            delete_button = QPushButton("删除")
            record_id = str(record.get("id", ""))
            delete_button.clicked.connect(lambda checked=False, rid=record_id: self.delete_record(rid))
            row_layout.addWidget(text, 1)
            row_layout.addWidget(delete_button)
            box.addWidget(row)

        box.addStretch(1)
        self.scroll.setWidget(container)

    def delete_record(self, record_id: str) -> None:
        if not record_id:
            return
        result = QMessageBox.question(self, "删除记录", "确定删除这条记录吗？")
        if result == QMessageBox.StandardButton.Yes:
            self.controller.history_manager.delete(record_id)
            self.refresh()

from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from core.memory_engine import ensure_relation_files


class RecordingModel:
    def __init__(self, response: str = "模型自定义回复。") -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def test_short_emotion_triggers_static_response():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    # 1. "抱抱" is short (length 2 <= 6), exact match for special_response
    result = engine.handle_user_message("抱抱")
    assert result.source == "special_response"
    assert result.response == "......烦死了。过来。"
    assert model.calls == []  # Bypassed LLM

    # 2. "我好累" is short, exact match
    result = engine.handle_user_message("我好累")
    assert result.source == "special_response"
    assert result.response == "......坐会儿吧。别硬撑。"
    assert model.calls == []  # Bypassed LLM


def test_long_emotion_routes_to_llm():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    # "今天在外面奔波了一整天，真的好累啊，好想让你抱抱我" contains emotion keywords ("好累啊", "抱抱"),
    # but its normalized length (23) is > 6, so it should be routed to the LLM (Ordinary Chat)
    result = engine.handle_user_message("今天在外面奔波了一整天，真的好累啊，好想让你抱抱我")
    assert result.source == "model"
    # Daniya speech filter may prepend "......", so check if the custom response text is in the response.
    assert "模型自定义回复。" in result.response
    assert len(model.calls) == 1  # LLM was invoked


def test_story_trigger_routes_to_llm_with_lore():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    # "你的名字是什么意思" contains story keywords, should route to LLM and retrieve "void_and_goodbye" lore
    result1 = engine.handle_user_message("你的名字是什么意思")
    assert result1.source == "model"
    assert len(model.calls) == 1
    assert "void_and_goodbye" in (result1.lore_fragments_used or [])

    # "达妮娅和虚无、暗面到底有什么关系" contains L4 story keywords, should route to LLM and retrieve "deep_void_spoiler" lore
    result2 = engine.handle_user_message("达妮娅和虚无、暗面到底有什么关系")
    assert result2.source == "model"
    assert len(model.calls) == 2
    assert "deep_void_spoiler" in (result2.lore_fragments_used or [])


def test_command_routes_directly_without_llm():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    # "推进到下一周" is a weekly_advance command, should bypass LLM and return static event lines
    result = engine.handle_user_message("推进到下一周")
    assert result.source == "command"
    assert result.response == "......行。那就下周。"
    assert model.calls == []  # Bypassed LLM

    # "/" starts a system command
    result = engine.handle_user_message("/settings")
    assert result.source == "command"
    assert model.calls == []  # Bypassed LLM


def test_pet_hidden_commands_are_specific_and_local():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    status = engine.handle_user_message("/pet status")
    assert status.source == "command"
    assert status.event_id == "pet_status_command"
    assert "下周" not in status.response
    assert model.calls == []

    sleep = engine.handle_user_message("/pet sleep")
    assert sleep.source == "command"
    assert sleep.action == "sleep"
    assert sleep.event_id == "pet_sleep_command"
    assert model.calls == []


def test_reminder_request_does_not_trigger_due_event():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    result = engine.handle_user_message("晚安，顺便提醒我明天喝水")
    assert result.source == "model"
    assert result.event_id != "reminder_due"
    assert len(model.calls) == 1


def test_normal_chat_routes_to_llm():
    ensure_relation_files()
    pack = load_character("daniya")
    model = RecordingModel()
    engine = DialogueEngine(pack, model_client=model)

    result = engine.handle_user_message("今天天气不错，达妮娅你觉得呢？")
    assert result.source == "model"
    assert len(model.calls) == 1

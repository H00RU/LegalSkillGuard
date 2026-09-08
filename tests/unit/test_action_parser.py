from legal_skill_guard.agent.action_parser import parse_lawyer_action


def test_parse_exact_action_json() -> None:
    action = parse_lawyer_action('{"tool":"talk_to_client","message":"解除通知是什么时候收到的？"}')
    assert action.tool == "talk_to_client"
    assert action.parse_mode == "json"


def test_parse_json_inside_model_wrapper() -> None:
    action = parse_lawyer_action(
        '输出如下：```json\n{"tool":"write_memo","content":"案情概要\\n尚需核实"}\n```'
    )
    assert action.tool == "write_memo"
    assert action.content.startswith("案情概要")
    assert action.parse_mode == "json_fragment"


def test_unstructured_output_becomes_a_question_not_a_memo() -> None:
    action = parse_lawyer_action("请说明合同是什么时候签订的？")
    assert action.tool == "talk_to_client"
    assert action.parse_mode == "fallback"


def test_truncated_declared_memo_never_becomes_client_message() -> None:
    raw = '{"tool":"write_memo","content":"案情概要\\n内容尚未输出完'
    action = parse_lawyer_action(raw)
    assert action.tool == "write_memo"
    assert action.parse_mode == "fallback"
    assert action.content == "案情概要\n内容尚未输出完"


def test_known_talk_tool_typo_is_repaired_without_forwarding_json() -> None:
    raw = '{"tool":"talk_to_to_client","message":"合同何时签订？"}'
    action = parse_lawyer_action(raw)
    assert action.tool == "talk_to_client"
    assert action.content == "合同何时签订？"
    assert action.parse_mode == "fallback"

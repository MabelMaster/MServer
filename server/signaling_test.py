import json

import pytest

from server.signaling import answer_message, parse_message, truth_message


def test_parse_offer():
    message = parse_message('{"type":"offer","sdp":"v=0\\r\\n"}')
    assert message["sdp"] == "v=0\r\n"


def test_parse_rejects_a_message_without_sdp():
    with pytest.raises(ValueError):
        parse_message('{"type":"offer"}')


def test_answer_message_is_one_json_line():
    payload = answer_message("v=0\r\n")
    assert payload.endswith(b"\n")
    assert payload.count(b"\n") == 1
    body = json.loads(payload)
    assert body == {"type": "answer", "sdp": "v=0\r\n"}

def test_truth_message_carries_frame_and_position():
    payload = truth_message(2, 10.5, 20.0)
    assert payload.endswith(b"\n")
    assert json.loads(payload) == {"t": 2000 / 30, "x": 10.5, "y": 20.0, "frame": 2}
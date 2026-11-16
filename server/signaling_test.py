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


def test_advertise_host_rewrites_ipv4_and_drops_ipv6():
    from server.signaling import advertise_host

    sdp = "\r\n".join([
        "v=0",
        "c=IN IP4 172.17.0.2",
        "a=candidate:1 1 UDP 1 172.17.0.2 50000 typ host",
        "a=candidate:2 1 UDP 1 fe80::1 50000 typ host",
        "",
    ])
    rewritten = advertise_host(sdp, "127.0.0.1")
    assert "172.17.0.2" not in rewritten
    assert "fe80" not in rewritten
    assert "c=IN IP4 127.0.0.1" in rewritten
    assert "127.0.0.1 50000" in rewritten
    assert rewritten.endswith("\r\n")


def test_listen_hosts_cover_localhost_and_all_interfaces():
    from server.signaling import listen_hosts

    assert listen_hosts("127.0.0.1") == ("127.0.0.1", "::1")
    assert listen_hosts("0.0.0.0") == ("0.0.0.0", "::")
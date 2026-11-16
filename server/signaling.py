import json


def parse_message(line):
    message = json.loads(line)
    if message.get("type") != "offer" or not message.get("sdp"):
        raise ValueError("expected an offer with sdp")
    return message


def answer_message(sdp):
    return (json.dumps({"type": "answer", "sdp": sdp}) + "\n").encode()
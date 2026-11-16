import json


def parse_message(line):
    message = json.loads(line)
    if message.get("type") != "offer" or not message.get("sdp"):
        raise ValueError("expected an offer with sdp")
    return message


def answer_message(sdp):
    return (json.dumps({"type": "answer", "sdp": sdp}) + "\n").encode()

def truth_message(index, x, y):
    body = {"t": index * 1000 / 30, "x": x, "y": y, "frame": index}
    return (json.dumps(body) + "\n").encode()
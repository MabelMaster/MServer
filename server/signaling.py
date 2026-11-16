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


def advertise_host(sdp, host):
    """Rewrite gathered host addresses so a browser outside the network namespace can reach them."""
    ending = "\r\n" if "\r\n" in sdp else "\n"
    rewritten = []
    for line in sdp.splitlines():
        if line.startswith("c=IN IP"):
            rewritten.append(f"c=IN IP4 {host}")
            continue
        if line.startswith("a=candidate:"):
            parts = line.split()
            if len(parts) < 6 or ":" in parts[4]:
                continue
            parts[4] = host
            rewritten.append(" ".join(parts))
            continue
        rewritten.append(line)
    text = ending.join(rewritten)
    if sdp.endswith(("\n", "\r\n")):
        text += ending
    return text


def listen_hosts(host):
    if host == "0.0.0.0":
        return ("0.0.0.0", "::")
    return ("127.0.0.1", "::1")
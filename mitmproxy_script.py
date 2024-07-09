from mitmproxy import http


def request(flow: http.HTTPFlow) -> None:
    with open("logs/requests.log", "a") as f:
        f.write(f"Request: {flow.request.method} {flow.request.url}\n")


def response(flow: http.HTTPFlow) -> None:
    with open("logs/requests.log", "a") as f:
        f.write(f"Response: {flow.response.status_code} {flow.response.text[:100]}\n")








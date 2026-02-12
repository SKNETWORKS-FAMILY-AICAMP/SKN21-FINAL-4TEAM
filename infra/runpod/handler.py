"""RunPod Serverless handler for SGLang inference."""


def handler(event: dict) -> dict:
    """RunPod 서버리스 핸들러.

    입력: {"input": {"messages": [...], "model": "...", "max_tokens": 1024, ...}}
    출력: {"output": {"content": "...", "usage": {"input_tokens": N, "output_tokens": N}}}
    """
    raise NotImplementedError

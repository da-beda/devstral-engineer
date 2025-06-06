import json
from typing import List, Dict, Any, Optional
from textwrap import dedent

from openai import AsyncOpenAI

from config import Config


def _default_client() -> tuple[AsyncOpenAI, str]:
    cfg = Config.load()
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=cfg.api_key)
    return client, cfg.default_model

async def plan_steps(
    request: str,
    tools: List[Dict[str, Any]],
    *,
    client_override: Optional[AsyncOpenAI] = None,
) -> List[Dict[str, Any]]:
    """Generate an ordered plan of tool calls for the given request."""
    if client_override is not None:
        client_to_use = client_override
        model = Config.load().default_model
    else:
        client_to_use, model = _default_client()

    system_prompt = dedent(
        """\
        You are a planning assistant for Devstral Engineer. Given a high-level user request and a list of available tools, produce a minimal ordered list of tool calls needed to fulfill the request.\n
        Respond strictly in JSON with a single key `plan` containing an array of steps. Each step must be an object with `tool` and optional `args` fields. Example:\n
        {"plan": [{"tool": "read_file", "args": {"file_path": "main.py"}}]}\n
        If the request cannot be satisfied with the provided tools, return an empty array.
        """
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request},
    ]

    try:
        resp = await client_to_use.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        plan = data.get("plan", [])
        if isinstance(plan, list):
            return plan
    except Exception:
        pass
    return []

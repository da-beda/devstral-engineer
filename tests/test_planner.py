import pytest

from planner import plan_steps


class FakeResp:
    def __init__(self, content: str):
        self.choices = [
            type("obj", (), {"message": type("obj", (), {"content": content})})
        ]


class FakeCompletions:
    async def create(self, *args, **kwargs):
        return FakeResp(
            '{"plan": [{"tool": "read_file", "args": {"file_path": "a.py"}}]}'
        )


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeClient:
    def __init__(self):
        self.chat = FakeChat()


@pytest.mark.asyncio
async def test_plan_steps_parses_json():
    client = FakeClient()
    plan = await plan_steps("read file", [], client_override=client)
    assert plan == [{"tool": "read_file", "args": {"file_path": "a.py"}}]

import ast
import types
from pathlib import Path
import pytest

# Load only execute_function_call_dict and execute_function_call from devstral_eng.py
source = Path(__file__).resolve().parents[1] / "devstral_eng.py"
mod_ast = ast.parse(source.read_text())
fn_nodes = [
    n
    for n in mod_ast.body
    if isinstance(n, ast.AsyncFunctionDef)
    and n.name in {"execute_function_call_dict", "execute_function_call"}
]
module = types.ModuleType("_exec_funcs")
module.__dict__["json"] = __import__("json")

async def _execute_tool(name, args):
    return f"{name}:{args}"

module.__dict__["_execute_tool"] = _execute_tool
exec(
    compile(ast.Module(fn_nodes, []), filename=str(source), mode="exec"),
    module.__dict__,
)
execute_function_call_dict = module.execute_function_call_dict
execute_function_call = module.execute_function_call


@pytest.mark.asyncio
async def test_execute_function_call_dict_missing_key():
    result = await execute_function_call_dict({})
    assert "Malformed tool call dictionary" in result


@pytest.mark.asyncio
async def test_execute_function_call_dict_invalid_json():
    data = {"function": {"name": "read_file", "arguments": "{"}}
    result = await execute_function_call_dict(data)
    assert "Invalid JSON arguments" in result


class BadToolCall:
    def __init__(self):
        self.function = type("Func", (), {"name": "read_file", "arguments": "{"})


@pytest.mark.asyncio
async def test_execute_function_call_invalid_json_object():
    result = await execute_function_call(BadToolCall())
    assert "Invalid JSON arguments" in result

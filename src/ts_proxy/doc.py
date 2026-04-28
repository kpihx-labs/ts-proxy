import inspect
import json
from typing import (
    Any,
    Dict,
    Optional,
    get_type_hints,
    List,
    Union,
    get_origin,
    get_args,
)


def get_type_name(typ: Any) -> Any:
    """Extract a human-readable name or structure from a type annotation."""
    if typ is inspect.Parameter.empty or typ is Any:
        return "Any"
    if typ is type(None):
        return "None"

    origin = get_origin(typ)
    args = get_args(typ)

    if origin is list:
        return [get_type_name(args[0])] if args else ["Any"]
    if origin is dict:
        return {
            "Key": get_type_name(args[0]) if args else "Any",
            "Value": get_type_name(args[1]) if len(args) > 1 else "Any",
        }
    if origin is Union:
        # Handle Optional[T] which is Union[T, None]
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return f"Optional[{get_type_name(non_none_args[0])}]"
        return " | ".join(str(get_type_name(a)) for a in non_none_args)

    s = str(typ)
    s = s.replace("typing.", "")
    s = s.replace("ts_proxy.api.", "")
    s = s.replace("ts_proxy.", "")
    s = s.replace("<class '", "").replace("'>", "")
    s = s.replace("NoneType", "None")

    return s.strip()


def parse_docstring(docstring: Optional[str]) -> Dict[str, str]:
    """Split docstring into summary, body, and examples."""
    if not docstring:
        return {"summary": "", "body": "", "examples": ""}

    lines = docstring.splitlines()
    body_lines: List[str] = []
    examples_lines: List[str] = []
    section = "body"

    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith(("examples:", "example:")):
            section = "examples"
            continue
        elif stripped.startswith(("parameters:", "args:", "arguments:")):
            section = "args"
            continue

        if section == "body":
            body_lines.append(line)
        elif section == "examples":
            examples_lines.append(line)

    # Extract summary as the first non-empty block of body
    summary_lines = []
    for line in body_lines:
        if not line.strip() and summary_lines:
            break
        if line.strip():
            summary_lines.append(line.strip())

    summary = " ".join(summary_lines)
    body = "\n".join(body_lines).strip()
    examples = "\n".join(examples_lines).strip()

    return {"summary": summary, "body": body, "examples": examples}


def get_function_schema(func: Any) -> Dict[str, Any]:
    """Return a parameter/type map for a function, recursively."""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    schema = {}

    for name, param in sig.parameters.items():
        if name in ("self", "kwargs"):
            continue
        typ = hints.get(name, param.annotation)
        schema[name] = get_type_name(typ)

    return schema


def format_rich_help(docstring: str, schema: Dict[str, Any], full: bool = True) -> str:
    """Format the docstring and schema for Typer help."""
    parsed = parse_docstring(docstring)

    schema_str = json.dumps(schema, indent=2)
    # We use a simple string for Typer help as it doesn't support complex Rich objects directly in 'help'
    # but we can format it with some pseudo-markdown or clear spacing.

    if full:
        output = f"{parsed['summary']}\n\n{parsed['body']}\n\n"
        if parsed["examples"]:
            output += f"EXAMPLES:\n{parsed['examples']}\n\n"
        output += f"JSON SCHEMA:\n{schema_str}"
    else:
        output = f"{parsed['summary']}\nSCHEMA: {schema_str}"

    return output

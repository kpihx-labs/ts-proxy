import inspect
import json
import re
from typing import (
    Any,
    Dict,
    Optional,
    get_type_hints,
    Union,
    get_origin,
    get_args,
)
from pydantic import BaseModel


def get_simplified_type_name(typ: Any) -> Any:
    """Extract a simple human-readable name or structure from a type annotation."""
    if typ is inspect.Parameter.empty or typ is Any:
        return "Any"
    if typ is type(None):
        return "None"

    origin = get_origin(typ)
    args = get_args(typ)

    if origin is list:
        return [get_simplified_type_name(args[0])] if args else ["Any"]
    if origin is dict:
        return {
            "Key": get_simplified_type_name(args[0]) if args else "Any",
            "Value": get_simplified_type_name(args[1]) if len(args) > 1 else "Any",
        }
    if origin is Union:
        # Handle Optional[T] which is Union[T, None]
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return f"Optional[{get_simplified_type_name(non_none_args[0])}]"
        return " | ".join(str(get_simplified_type_name(a)) for a in non_none_args)

    if inspect.isclass(typ) and issubclass(typ, BaseModel):
        # Simplified view of a Pydantic model: just its fields and their types
        model_schema = {}
        for field_name, field in typ.model_fields.items():
            model_schema[field_name] = get_simplified_type_name(field.annotation)
        return model_schema

    s = str(typ)
    s = s.replace("typing.", "")
    s = s.replace("ts_proxy.api.", "")
    s = s.replace("ts_proxy.models.", "")
    s = s.replace("ts_proxy.", "")
    s = s.replace("<class '", "").replace("'>", "")
    s = s.replace("NoneType", "None")

    return s.strip()


def parse_docstring(docstring: Optional[str]) -> Dict[str, str]:
    """
    Split docstring into tiers:
    - description: Everything before 'Parameters:' (Summary + Body)
    - full: The entire docstring as is.
    """
    if not docstring:
        return {"description": "", "full": ""}

    # 1. Description: Everything before 'Parameters:'
    # Split on "Parameters:" header (case-insensitive, whole line)
    parts = re.split(r"(?i)^\s*parameters:\s*$", docstring, flags=re.MULTILINE)
    description = parts[0].strip()

    return {
        "description": description,
        "full": docstring.strip(),
    }


def get_function_schema(func: Any, full: bool = True) -> Dict[str, Any]:
    """Return a parameter/type map for a function. If full=True, use Pydantic JSON schema."""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    schema = {}

    for name, param in sig.parameters.items():
        if name in ("self", "kwargs"):
            continue
        typ = hints.get(name, param.annotation)

        if full:
            if inspect.isclass(typ) and issubclass(typ, BaseModel):
                schema[name] = typ.model_json_schema()
            else:
                schema[name] = get_simplified_type_name(typ)
        else:
            # Simplified schema for global help
            schema[name] = get_simplified_type_name(typ)

    return schema


def format_rich_help(func: Any, full: bool = True) -> str:
    """Format the docstring and schema for Typer help."""
    docstring = inspect.getdoc(func) or ""
    parsed = parse_docstring(docstring)
    schema = get_function_schema(func, full=full)

    if full:
        # Detailed help for 'do <cmd> --help'
        # Display the FULL docstring as is, then the full Pydantic JSON SCHEMA
        schema_str = json.dumps(schema, indent=2)
        output = f"{parsed['full']}\n\nJSON SCHEMA:\n{schema_str}"
    else:
        # Global help for 'do --help'
        # Compact description (replace double newlines with single to avoid Typer truncation)
        description = re.sub(r"\n\s*\n", "\n", parsed["description"])

        # Simple schema: one line if small, else pretty but compact
        schema_str = json.dumps(schema, indent=2)

        output = f"{description}\nJSON SCHEMA: {schema_str}"

    return output

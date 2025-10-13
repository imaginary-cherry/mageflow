import dataclasses
from typing import Any, TypeVar, get_type_hints

from pydantic import create_model, BaseModel


ParamValidationType = dict[str, tuple[type, Any]]
PropType = TypeVar("PropType", bound=dataclasses.dataclass)


def extract_validators(data: dict) -> ParamValidationType:
    return {key: (type(value), value) for key, value in data.items()}


def create_dynamic_model(data: dict) -> BaseModel:
    validators = extract_validators(data)
    model_type = create_model_from_validators(validators)
    return model_type(**data)


def create_model_from_validators(validators: ParamValidationType) -> type[BaseModel]:
    return create_model("DynamicModel", **validators)


def get_marked_fields(
    model: type[BaseModel], mark_type: type[PropType]
) -> list[tuple[PropType, str]]:
    hints = get_type_hints(model, include_extras=True)
    marked = []
    for field_name, annotated_type in hints.items():
        if hasattr(annotated_type, "__metadata__"):  # Annotated stores extras here
            for meta in annotated_type.__metadata__:
                if isinstance(meta, mark_type):
                    marked.append((meta, field_name))
    return marked

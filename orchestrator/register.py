from typing import Optional

from redis.asyncio.client import Redis
from pydantic import BaseModel

from orchestrator.hatchet.utils import serialize_model_validator, parse_model_validator

REGISTER_KEY_PREFIX = "register-name"
VALIDATOR_KEY_PREFIX = "register-input-validator"


def create_register_key(register_name: str) -> str:
    return f"{REGISTER_KEY_PREFIX}/{register_name}"


def create_register_key_input_validator(register_name: str) -> str:
    return f"{VALIDATOR_KEY_PREFIX}/{register_name}"


async def store_input_validator(
    redis: Redis, register_name: str, input_validator: type[BaseModel]
):
    serialized_validator = serialize_model_validator(input_validator)
    await redis.set(
        create_register_key_input_validator(register_name), serialized_validator
    )


async def load_validator(redis: Redis, register_name: str) -> Optional[type[BaseModel]]:
    validator_data = await redis.get(create_register_key_input_validator(register_name))
    if not validator_data:
        return None
    return parse_model_validator(validator_data.decode())


async def store_task_name(redis: Redis, register_name: str, task_name: str):
    await redis.set(create_register_key(register_name), task_name)


async def load_name(redis: Redis, register_name: str) -> str:
    task_name = await redis.get(create_register_key(register_name))
    if not task_name:
        return register_name
    return task_name

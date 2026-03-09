import dataclasses
from dataclasses import field
from typing import Optional

from pydantic import Field
from pydantic.dataclasses import dataclass
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.consts import REMOVED_TASK_TTL
from thirdmagic.signature import SignatureConfig
from thirdmagic.swarm import SwarmTaskSignature
from thirdmagic.swarm.state import PublishState
from thirdmagic.task import TaskSignature

from mageflow.callbacks import AcceptParams


@dataclass
class SignatureTTLConfig:
    active_ttl: Optional[int] = None  # seconds, None = use general
    ttl_when_sign_done: Optional[int] = Field(default=None, ge=REMOVED_TASK_TTL)


@dataclass
class TTLConfig:
    active_ttl: int = 24 * 60 * 60  # general active TTL (default 24h)
    ttl_when_sign_done: int = Field(default=REMOVED_TASK_TTL, ge=REMOVED_TASK_TTL)
    task: SignatureTTLConfig = field(default_factory=SignatureTTLConfig)
    chain: SignatureTTLConfig = field(default_factory=SignatureTTLConfig)
    swarm: SignatureTTLConfig = field(default_factory=SignatureTTLConfig)


@dataclass
class MageflowConfig:
    ttl: TTLConfig = field(default_factory=TTLConfig)
    param_config: AcceptParams = AcceptParams.NO_CTX


def apply_ttl_config(ttl_config: TTLConfig):
    config_mapping = {
        TaskSignature: ttl_config.task,
        ChainTaskSignature: ttl_config.chain,
        SwarmTaskSignature: ttl_config.swarm,
        PublishState: ttl_config.swarm,
    }
    for sig_type, sig_config in config_mapping.items():
        active_ttl = sig_config.active_ttl or ttl_config.active_ttl
        done_ttl = sig_config.ttl_when_sign_done or ttl_config.ttl_when_sign_done

        sig_type.Meta = dataclasses.replace(sig_type.Meta, ttl=active_ttl)
        sig_type.SignatureSettings = SignatureConfig(ttl_when_sign_done=done_ttl)

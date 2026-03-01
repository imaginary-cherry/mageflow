from thirdmagic.chain import ChainTaskSignature
from thirdmagic.swarm import SwarmTaskSignature
from thirdmagic.swarm.state import PublishState
from thirdmagic.task import TaskSignature

from mageflow.config import (
    apply_ttl_config,
    TTLConfig,
    SignatureTTLConfig,
)


def test_per_type_overrides_propagate():
    apply_ttl_config(
        TTLConfig(
            task=SignatureTTLConfig(active_ttl=100, ttl_when_sign_done=50),
        )
    )
    assert TaskSignature.Meta.ttl == 100
    assert TaskSignature.SignatureSettings.ttl_when_sign_done == 50


def test_each_type_independent():
    apply_ttl_config(
        TTLConfig(
            swarm=SignatureTTLConfig(active_ttl=200, ttl_when_sign_done=80),
        )
    )
    assert SwarmTaskSignature.Meta.ttl == 200
    assert SwarmTaskSignature.SignatureSettings.ttl_when_sign_done == 80

    # Chain gets the default SignatureTTLConfig values (None), not the swarm overrides
    assert ChainTaskSignature.Meta.ttl != 200
    assert ChainTaskSignature.SignatureSettings.ttl_when_sign_done != 80


def test_publish_state_follows_swarm_config():
    apply_ttl_config(
        TTLConfig(
            swarm=SignatureTTLConfig(active_ttl=777),
        )
    )
    assert PublishState.Meta.ttl == 777


def test_dataclasses_replace_preserves_other_fields():
    original_refresh = TaskSignature.Meta.refresh_ttl
    apply_ttl_config(
        TTLConfig(
            task=SignatureTTLConfig(active_ttl=999),
        )
    )
    assert TaskSignature.Meta.refresh_ttl == original_refresh

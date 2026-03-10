import pytest
from pydantic import ValidationError
from thirdmagic.consts import REMOVED_TASK_TTL
from thirdmagic.signature import SignatureConfig

from mageflow.config import SignatureTTLConfig, TTLConfig


class TestSignatureConfigValidation:
    def test_rejects_ttl_below_minimum(self):
        with pytest.raises(ValidationError):
            SignatureConfig(ttl_when_sign_done=REMOVED_TASK_TTL - 1)

    def test_accepts_ttl_at_minimum(self):
        config = SignatureConfig(ttl_when_sign_done=REMOVED_TASK_TTL)
        assert config.ttl_when_sign_done == REMOVED_TASK_TTL

    def test_accepts_ttl_above_minimum(self):
        config = SignatureConfig(ttl_when_sign_done=REMOVED_TASK_TTL + 1000)
        assert config.ttl_when_sign_done == REMOVED_TASK_TTL + 1000


class TestTTLConfigValidation:
    def test_rejects_ttl_below_minimum(self):
        with pytest.raises(ValidationError):
            TTLConfig(ttl_when_sign_done=REMOVED_TASK_TTL - 1)

    def test_accepts_ttl_at_minimum(self):
        config = TTLConfig(ttl_when_sign_done=REMOVED_TASK_TTL)
        assert config.ttl_when_sign_done == REMOVED_TASK_TTL

    def test_default_is_valid(self):
        config = TTLConfig()
        assert config.ttl_when_sign_done >= REMOVED_TASK_TTL


class TestSignatureTTLConfigValidation:
    def test_rejects_ttl_below_minimum(self):
        with pytest.raises(ValidationError):
            SignatureTTLConfig(ttl_when_sign_done=REMOVED_TASK_TTL - 1)

    def test_accepts_none(self):
        config = SignatureTTLConfig(ttl_when_sign_done=None)
        assert config.ttl_when_sign_done is None

    def test_accepts_ttl_at_minimum(self):
        config = SignatureTTLConfig(ttl_when_sign_done=REMOVED_TASK_TTL)
        assert config.ttl_when_sign_done == REMOVED_TASK_TTL

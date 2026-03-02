import warnings
from unittest.mock import MagicMock

import pytest
from hatchet_sdk import Hatchet
from redis import Redis

from mageflow.callbacks import AcceptParams
from mageflow.clients.hatchet.mageflow import HatchetMageflow
from mageflow.config import MageflowConfig


@pytest.fixture
def hatchet():
    h = MagicMock(spec=Hatchet)
    h._client = MagicMock()
    return h


@pytest.fixture
def redis():
    return MagicMock(spec=Redis)


class TestParamConfigOnMageflowConfig:
    def test_default_param_config_is_no_ctx(self):
        config = MageflowConfig()
        assert config.param_config == AcceptParams.NO_CTX

    def test_param_config_can_be_set_on_config(self):
        config = MageflowConfig(param_config=AcceptParams.ALL)
        assert config.param_config == AcceptParams.ALL


class TestParamConfigViaConfig:
    def test_uses_param_config_from_config_model(self, hatchet, redis):
        config = MageflowConfig(param_config=AcceptParams.ALL)
        client = HatchetMageflow(hatchet=hatchet, redis_client=redis, config=config)
        assert client.param_config == AcceptParams.ALL

    def test_uses_default_param_config_when_nothing_provided(self, hatchet, redis):
        client = HatchetMageflow(hatchet=hatchet, redis_client=redis)
        assert client.param_config == AcceptParams.NO_CTX

    def test_uses_just_message_from_config(self, hatchet, redis):
        config = MageflowConfig(param_config=AcceptParams.JUST_MESSAGE)
        client = HatchetMageflow(hatchet=hatchet, redis_client=redis, config=config)
        assert client.param_config == AcceptParams.JUST_MESSAGE


class TestParamConfigDeprecation:
    def test_direct_param_config_emits_deprecation_warning(self, hatchet, redis):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            HatchetMageflow(
                hatchet=hatchet,
                redis_client=redis,
                param_config=AcceptParams.ALL,
            )
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 1
            assert "param_config" in str(deprecation_warnings[0].message)
            assert "MageflowConfig" in str(deprecation_warnings[0].message)

    def test_direct_param_config_value_is_used(self, hatchet, redis):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            client = HatchetMageflow(
                hatchet=hatchet,
                redis_client=redis,
                param_config=AcceptParams.JUST_MESSAGE,
            )
        assert client.param_config == AcceptParams.JUST_MESSAGE

    def test_no_deprecation_warning_when_using_config_model(self, hatchet, redis):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            config = MageflowConfig(param_config=AcceptParams.ALL)
            HatchetMageflow(hatchet=hatchet, redis_client=redis, config=config)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 0

    def test_direct_param_config_overrides_config_model(self, hatchet, redis):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            config = MageflowConfig(param_config=AcceptParams.NO_CTX)
            client = HatchetMageflow(
                hatchet=hatchet,
                redis_client=redis,
                param_config=AcceptParams.ALL,
                config=config,
            )
        assert client.param_config == AcceptParams.ALL

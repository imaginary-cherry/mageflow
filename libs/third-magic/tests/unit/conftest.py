from unittest.mock import MagicMock

import pytest

from thirdmagic.clients import BaseClientAdapter
from thirdmagic.signature.model import TaskSignature


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock(spec=BaseClientAdapter)
    TaskSignature.ClientAdapter = adapter
    yield adapter

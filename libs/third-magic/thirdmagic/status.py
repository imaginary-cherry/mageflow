import asyncio

import rapyer
from rapyer.fields import RapyerKey

from thirdmagic.container import ContainerTaskSignature
from thirdmagic.errors import MissingSignatureError, NotAContainerError
from thirdmagic.signature.status import ContainersStatus


async def _load_container(signature_id: RapyerKey) -> ContainerTaskSignature:
    signature = await rapyer.afind_one(signature_id)
    if signature is None:
        raise MissingSignatureError(f"Signature {signature_id} not found")
    if not isinstance(signature, ContainerTaskSignature):
        raise NotAContainerError(
            f"Signature {signature_id} is not a container signature"
        )
    return signature


async def astatus(*signature_ids: RapyerKey) -> ContainersStatus:
    containers = await asyncio.gather(
        *[_load_container(signature_id) for signature_id in signature_ids]
    )
    statuses = await asyncio.gather(
        *[container.container_status() for container in containers]
    )
    return ContainersStatus(containers=list(statuses))

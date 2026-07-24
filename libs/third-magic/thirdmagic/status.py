import rapyer
from rapyer.fields import RapyerKey

from thirdmagic.container import ContainerTaskSignature
from thirdmagic.errors import MissingSignatureError, NotAContainerError
from thirdmagic.signature.status import ContainersStatus


async def astatus(*signature_ids: RapyerKey) -> ContainersStatus:
    if not signature_ids:
        return ContainersStatus(containers=[])

    signatures = await rapyer.afind(*signature_ids, skip_missing=True)
    if len(signatures) != len(signature_ids):
        raise MissingSignatureError(f"Some signatures were not found: {signature_ids}")

    statuses = []
    for signature in signatures:
        if not isinstance(signature, ContainerTaskSignature):
            raise NotAContainerError(
                f"Signature {signature.key} is not a container signature"
            )
        statuses.append(await signature.container_status())
    return ContainersStatus(containers=statuses)

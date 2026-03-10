import rapyer

from thirdmagic.chain.creator import chain
from thirdmagic.swarm.creator import swarm
from thirdmagic.task.creator import sign

abounded_field = rapyer.apipeline

__all__ = ["sign", "chain", "swarm", "abounded_field"]

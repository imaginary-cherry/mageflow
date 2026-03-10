import pytest

import thirdmagic
from tests.unit.assertions import (
    assert_container_created_with_ordered_tasks,
    assert_task_reloaded_as_type,
)
from thirdmagic.chain import ChainTaskSignature
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task import TaskSignature

# --- Multiple Signatures Inside abounded_field ---


@pytest.mark.asyncio
async def test__abounded_field__multiple_signatures_from_task_names__all_created(
    mock_task_def,
):
    async with thirdmagic.abounded_field():
        sig1 = await thirdmagic.sign("task_a")
        sig2 = await thirdmagic.sign("task_b")
        sig3 = await thirdmagic.sign("task_c")

    reloaded1 = await assert_task_reloaded_as_type(sig1.key, TaskSignature)
    reloaded2 = await assert_task_reloaded_as_type(sig2.key, TaskSignature)
    reloaded3 = await assert_task_reloaded_as_type(sig3.key, TaskSignature)

    assert reloaded1.task_name == "task_a"
    assert reloaded2.task_name == "task_b"
    assert reloaded3.task_name == "task_c"


@pytest.mark.asyncio
async def test__abounded_field__multiple_signatures_from_hatchet_tasks__all_created(
    hatchet_mock,
):
    @hatchet_mock.task(name="ht_task_a")
    def ht_task_a(msg):
        return msg

    @hatchet_mock.task(name="ht_task_b")
    def ht_task_b(msg):
        return msg

    @hatchet_mock.task(name="ht_task_c")
    def ht_task_c(msg):
        return msg

    async with thirdmagic.abounded_field():
        sig1 = await thirdmagic.sign(ht_task_a)
        sig2 = await thirdmagic.sign(ht_task_b)
        sig3 = await thirdmagic.sign(ht_task_c)

    reloaded1 = await assert_task_reloaded_as_type(sig1.key, TaskSignature)
    reloaded2 = await assert_task_reloaded_as_type(sig2.key, TaskSignature)
    reloaded3 = await assert_task_reloaded_as_type(sig3.key, TaskSignature)

    assert reloaded1.task_name == "ht_task_a"
    assert reloaded2.task_name == "ht_task_b"
    assert reloaded3.task_name == "ht_task_c"


@pytest.mark.asyncio
async def test__abounded_field__multiple_signatures_mixed_inputs__all_created(
    hatchet_mock, mock_task_def
):
    @hatchet_mock.task(name="ht_task")
    def ht_task(msg):
        return msg

    async with thirdmagic.abounded_field():
        sig_ht = await thirdmagic.sign(ht_task)
        sig_name = await thirdmagic.sign("named_task")

    reloaded_ht = await assert_task_reloaded_as_type(sig_ht.key, TaskSignature)
    reloaded_name = await assert_task_reloaded_as_type(sig_name.key, TaskSignature)

    assert reloaded_ht.task_name == "ht_task"
    assert reloaded_name.task_name == "named_task"


# --- Chains Inside abounded_field ---


@pytest.mark.asyncio
async def test__abounded_field__chain_from_signature_keys__created_correctly(
    hatchet_mock,
):
    @hatchet_mock.task(name="chain_key_1")
    def chain_key_1(msg):
        return msg

    @hatchet_mock.task(name="chain_key_2")
    def chain_key_2(msg):
        return msg

    task1 = await thirdmagic.sign(chain_key_1)
    task2 = await thirdmagic.sign(chain_key_2)

    async with thirdmagic.abounded_field():
        chain_sig = await thirdmagic.chain([task1.key, task2.key])

    await assert_container_created_with_ordered_tasks(
        chain_sig.key, ChainTaskSignature, [task1.key, task2.key]
    )


@pytest.mark.asyncio
async def test__abounded_field__chain_from_task_names__created_correctly(mock_task_def):
    async with thirdmagic.abounded_field():
        chain_sig = await thirdmagic.chain(["chain_name_a", "chain_name_b"])

    reloaded = await assert_task_reloaded_as_type(chain_sig.key, ChainTaskSignature)
    assert len(reloaded.tasks) == 2

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    assert task1.task_name == "chain_name_a"
    assert task2.task_name == "chain_name_b"
    assert task1.signature_container_id == chain_sig.key
    assert task2.signature_container_id == chain_sig.key


@pytest.mark.asyncio
async def test__abounded_field__chain_from_hatchet_tasks__created_correctly(
    hatchet_mock,
):
    @hatchet_mock.task(name="ht_chain_1")
    def ht_chain_1(msg):
        return msg

    @hatchet_mock.task(name="ht_chain_2")
    def ht_chain_2(msg):
        return msg

    async with thirdmagic.abounded_field():
        chain_sig = await thirdmagic.chain([ht_chain_1, ht_chain_2])

    reloaded = await assert_task_reloaded_as_type(chain_sig.key, ChainTaskSignature)
    assert len(reloaded.tasks) == 2

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    assert task1.task_name == "ht_chain_1"
    assert task2.task_name == "ht_chain_2"
    assert task1.signature_container_id == chain_sig.key
    assert task2.signature_container_id == chain_sig.key


@pytest.mark.asyncio
async def test__abounded_field__chain_from_mixed_inputs__created_correctly(
    hatchet_mock, mock_task_def
):
    @hatchet_mock.task(name="ht_mix_chain")
    def ht_mix_chain(msg):
        return msg

    async with thirdmagic.abounded_field():
        pre_created = await thirdmagic.sign("pre_created_task")
        chain_sig = await thirdmagic.chain(
            [pre_created, ht_mix_chain, "named_chain_task"]
        )

    reloaded = await assert_task_reloaded_as_type(chain_sig.key, ChainTaskSignature)
    assert len(reloaded.tasks) == 3

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    task3 = await assert_task_reloaded_as_type(reloaded.tasks[2], TaskSignature)
    assert task1.key == pre_created.key
    assert task2.task_name == "ht_mix_chain"
    assert task3.task_name == "named_chain_task"
    assert task1.signature_container_id == chain_sig.key
    assert task2.signature_container_id == chain_sig.key
    assert task3.signature_container_id == chain_sig.key


# --- Swarms Inside abounded_field ---


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_signature_keys__created_correctly(
    hatchet_mock,
):
    @hatchet_mock.task(name="swarm_key_1")
    def swarm_key_1(msg):
        return msg

    @hatchet_mock.task(name="swarm_key_2")
    def swarm_key_2(msg):
        return msg

    task1 = await thirdmagic.sign(swarm_key_1)
    task2 = await thirdmagic.sign(swarm_key_2)

    async with thirdmagic.abounded_field():
        swarm_sig = await thirdmagic.swarm(
            [task1.key, task2.key], task_name="test-swarm-keys"
        )

    await assert_container_created_with_ordered_tasks(
        swarm_sig.key, SwarmTaskSignature, [task1.key, task2.key]
    )


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_task_names__created_correctly(mock_task_def):
    async with thirdmagic.abounded_field():
        swarm_sig = await thirdmagic.swarm(
            ["swarm_name_a", "swarm_name_b"], task_name="test-swarm-names"
        )

    reloaded = await assert_task_reloaded_as_type(swarm_sig.key, SwarmTaskSignature)
    assert len(reloaded.tasks) == 2

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    assert task1.task_name == "swarm_name_a"
    assert task2.task_name == "swarm_name_b"
    assert task1.signature_container_id == swarm_sig.key
    assert task2.signature_container_id == swarm_sig.key


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_hatchet_tasks__created_correctly(
    hatchet_mock,
):
    @hatchet_mock.task(name="ht_swarm_1")
    def ht_swarm_1(msg):
        return msg

    @hatchet_mock.task(name="ht_swarm_2")
    def ht_swarm_2(msg):
        return msg

    async with thirdmagic.abounded_field():
        swarm_sig = await thirdmagic.swarm(
            [ht_swarm_1, ht_swarm_2], task_name="test-swarm-ht"
        )

    reloaded = await assert_task_reloaded_as_type(swarm_sig.key, SwarmTaskSignature)
    assert len(reloaded.tasks) == 2

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    assert task1.task_name == "ht_swarm_1"
    assert task2.task_name == "ht_swarm_2"
    assert task1.signature_container_id == swarm_sig.key
    assert task2.signature_container_id == swarm_sig.key


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_mixed_inputs__created_correctly(
    hatchet_mock, mock_task_def
):
    @hatchet_mock.task(name="ht_swarm_mix")
    def ht_swarm_mix(msg):
        return msg

    pre_created = await thirdmagic.sign("pre_swarm_task")

    async with thirdmagic.abounded_field():
        swarm_sig = await thirdmagic.swarm(
            [pre_created.key, ht_swarm_mix, "named_swarm_task"],
            task_name="test-swarm-mix",
        )

    reloaded = await assert_task_reloaded_as_type(swarm_sig.key, SwarmTaskSignature)
    assert len(reloaded.tasks) == 3

    task1 = await assert_task_reloaded_as_type(reloaded.tasks[0], TaskSignature)
    task2 = await assert_task_reloaded_as_type(reloaded.tasks[1], TaskSignature)
    task3 = await assert_task_reloaded_as_type(reloaded.tasks[2], TaskSignature)
    assert task1.key == pre_created.key
    assert task2.task_name == "ht_swarm_mix"
    assert task3.task_name == "named_swarm_task"
    assert task1.signature_container_id == swarm_sig.key
    assert task2.signature_container_id == swarm_sig.key
    assert task3.signature_container_id == swarm_sig.key


# --- Combinations Inside abounded_field ---


@pytest.mark.asyncio
async def test__abounded_field__signature_then_chain__both_created(hatchet_mock):
    @hatchet_mock.task(name="solo_task")
    def solo_task(msg):
        return msg

    @hatchet_mock.task(name="chain_a")
    def chain_a(msg):
        return msg

    @hatchet_mock.task(name="chain_b")
    def chain_b(msg):
        return msg

    async with thirdmagic.abounded_field():
        sig = await thirdmagic.sign(solo_task)
        chain_sig = await thirdmagic.chain([chain_a, chain_b])

    await assert_task_reloaded_as_type(sig.key, TaskSignature)
    reloaded_chain = await assert_task_reloaded_as_type(
        chain_sig.key, ChainTaskSignature
    )
    assert len(reloaded_chain.tasks) == 2


@pytest.mark.asyncio
async def test__abounded_field__signature_then_swarm__both_created(hatchet_mock):
    @hatchet_mock.task(name="solo_task")
    def solo_task(msg):
        return msg

    @hatchet_mock.task(name="swarm_item")
    def swarm_item(msg):
        return msg

    async with thirdmagic.abounded_field():
        sig = await thirdmagic.sign(solo_task)
        swarm_sig = await thirdmagic.swarm([swarm_item], task_name="test-combo-swarm")

    await assert_task_reloaded_as_type(sig.key, TaskSignature)
    reloaded_swarm = await assert_task_reloaded_as_type(
        swarm_sig.key, SwarmTaskSignature
    )
    assert len(reloaded_swarm.tasks) == 1


@pytest.mark.asyncio
async def test__abounded_field__chain_then_swarm__both_created(hatchet_mock):
    @hatchet_mock.task(name="c_task_1")
    def c_task_1(msg):
        return msg

    @hatchet_mock.task(name="c_task_2")
    def c_task_2(msg):
        return msg

    @hatchet_mock.task(name="s_task_1")
    def s_task_1(msg):
        return msg

    async with thirdmagic.abounded_field():
        chain_sig = await thirdmagic.chain([c_task_1, c_task_2])
        swarm_sig = await thirdmagic.swarm([s_task_1], task_name="test-cs-swarm")

    reloaded_chain = await assert_task_reloaded_as_type(
        chain_sig.key, ChainTaskSignature
    )
    reloaded_swarm = await assert_task_reloaded_as_type(
        swarm_sig.key, SwarmTaskSignature
    )
    assert len(reloaded_chain.tasks) == 2
    assert len(reloaded_swarm.tasks) == 1


@pytest.mark.asyncio
async def test__abounded_field__all_types_mixed__all_created_correctly(hatchet_mock):
    @hatchet_mock.task(name="sig_task")
    def sig_task(msg):
        return msg

    @hatchet_mock.task(name="chain_1")
    def chain_1(msg):
        return msg

    @hatchet_mock.task(name="chain_2")
    def chain_2(msg):
        return msg

    @hatchet_mock.task(name="swarm_1")
    def swarm_1(msg):
        return msg

    @hatchet_mock.task(name="swarm_2")
    def swarm_2(msg):
        return msg

    async with thirdmagic.abounded_field():
        sig = await thirdmagic.sign(sig_task)
        chain_sig = await thirdmagic.chain([chain_1, chain_2])
        swarm_sig = await thirdmagic.swarm(
            [swarm_1, swarm_2], task_name="test-all-swarm"
        )

    reloaded_sig = await assert_task_reloaded_as_type(sig.key, TaskSignature)
    assert reloaded_sig.task_name == "sig_task"

    reloaded_chain = await assert_task_reloaded_as_type(
        chain_sig.key, ChainTaskSignature
    )
    assert len(reloaded_chain.tasks) == 2
    chain_task1 = await assert_task_reloaded_as_type(
        reloaded_chain.tasks[0], TaskSignature
    )
    chain_task2 = await assert_task_reloaded_as_type(
        reloaded_chain.tasks[1], TaskSignature
    )
    assert chain_task1.task_name == "chain_1"
    assert chain_task2.task_name == "chain_2"
    assert chain_task1.signature_container_id == chain_sig.key
    assert chain_task2.signature_container_id == chain_sig.key

    reloaded_swarm = await assert_task_reloaded_as_type(
        swarm_sig.key, SwarmTaskSignature
    )
    assert len(reloaded_swarm.tasks) == 2
    swarm_task1 = await assert_task_reloaded_as_type(
        reloaded_swarm.tasks[0], TaskSignature
    )
    swarm_task2 = await assert_task_reloaded_as_type(
        reloaded_swarm.tasks[1], TaskSignature
    )
    assert swarm_task1.task_name == "swarm_1"
    assert swarm_task2.task_name == "swarm_2"
    assert swarm_task1.signature_container_id == swarm_sig.key
    assert swarm_task2.signature_container_id == swarm_sig.key


# --- Multiple of Same Type ---


@pytest.mark.asyncio
async def test__abounded_field__multiple_chains__all_created(hatchet_mock):
    @hatchet_mock.task(name="c1_task_a")
    def c1_task_a(msg):
        return msg

    @hatchet_mock.task(name="c1_task_b")
    def c1_task_b(msg):
        return msg

    @hatchet_mock.task(name="c2_task_a")
    def c2_task_a(msg):
        return msg

    @hatchet_mock.task(name="c2_task_b")
    def c2_task_b(msg):
        return msg

    async with thirdmagic.abounded_field():
        chain1 = await thirdmagic.chain([c1_task_a, c1_task_b])
        chain2 = await thirdmagic.chain([c2_task_a, c2_task_b])

    reloaded1 = await assert_task_reloaded_as_type(chain1.key, ChainTaskSignature)
    reloaded2 = await assert_task_reloaded_as_type(chain2.key, ChainTaskSignature)

    assert len(reloaded1.tasks) == 2
    assert len(reloaded2.tasks) == 2

    c1_t1 = await assert_task_reloaded_as_type(reloaded1.tasks[0], TaskSignature)
    c1_t2 = await assert_task_reloaded_as_type(reloaded1.tasks[1], TaskSignature)
    assert c1_t1.task_name == "c1_task_a"
    assert c1_t2.task_name == "c1_task_b"
    assert c1_t1.signature_container_id == chain1.key
    assert c1_t2.signature_container_id == chain1.key

    c2_t1 = await assert_task_reloaded_as_type(reloaded2.tasks[0], TaskSignature)
    c2_t2 = await assert_task_reloaded_as_type(reloaded2.tasks[1], TaskSignature)
    assert c2_t1.task_name == "c2_task_a"
    assert c2_t2.task_name == "c2_task_b"
    assert c2_t1.signature_container_id == chain2.key
    assert c2_t2.signature_container_id == chain2.key


@pytest.mark.asyncio
async def test__abounded_field__multiple_swarms__all_created(hatchet_mock):
    @hatchet_mock.task(name="s1_task")
    def s1_task(msg):
        return msg

    @hatchet_mock.task(name="s2_task")
    def s2_task(msg):
        return msg

    async with thirdmagic.abounded_field():
        swarm1 = await thirdmagic.swarm([s1_task], task_name="swarm-1")
        swarm2 = await thirdmagic.swarm([s2_task], task_name="swarm-2")

    reloaded1 = await assert_task_reloaded_as_type(swarm1.key, SwarmTaskSignature)
    reloaded2 = await assert_task_reloaded_as_type(swarm2.key, SwarmTaskSignature)

    assert len(reloaded1.tasks) == 1
    assert len(reloaded2.tasks) == 1

    s1_t = await assert_task_reloaded_as_type(reloaded1.tasks[0], TaskSignature)
    s2_t = await assert_task_reloaded_as_type(reloaded2.tasks[0], TaskSignature)
    assert s1_t.task_name == "s1_task"
    assert s2_t.task_name == "s2_task"
    assert s1_t.signature_container_id == swarm1.key
    assert s2_t.signature_container_id == swarm2.key

import pytest

import thirdmagic
from tests.unit.assertions import (
    assert_container_created_with_ordered_tasks,
    assert_container_subtasks,
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

    @hatchet_mock.task(name="inner_chain_a")
    def inner_chain_a(msg):
        return msg

    @hatchet_mock.task(name="inner_chain_b")
    def inner_chain_b(msg):
        return msg

    task1 = await thirdmagic.sign(chain_key_1)
    task2 = await thirdmagic.sign(chain_key_2)

    async with thirdmagic.abounded_field():
        inner_chain = await thirdmagic.chain([inner_chain_a, inner_chain_b])
        chain_sig = await thirdmagic.chain([task1.key, inner_chain, task2.key])

    await assert_container_created_with_ordered_tasks(
        chain_sig.key,
        ChainTaskSignature,
        [task1.key, inner_chain.key, task2.key],
    )


@pytest.mark.asyncio
async def test__abounded_field__chain_from_task_names__created_correctly(mock_task_def):
    async with thirdmagic.abounded_field():
        chain_sig = await thirdmagic.chain(["chain_name_a", "chain_name_b"])

    reloaded = await assert_task_reloaded_as_type(chain_sig.key, ChainTaskSignature)
    await assert_container_subtasks(reloaded, ["chain_name_a", "chain_name_b"])


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
    await assert_container_subtasks(reloaded, ["ht_chain_1", "ht_chain_2"])


@pytest.mark.asyncio
async def test__abounded_field__chain_from_mixed_inputs__created_correctly(
    hatchet_mock, mock_task_def
):
    @hatchet_mock.task(name="ht_mix_chain")
    def ht_mix_chain(msg):
        return msg

    @hatchet_mock.task(name="nested_swarm_a")
    def nested_swarm_a(msg):
        return msg

    @hatchet_mock.task(name="nested_swarm_b")
    def nested_swarm_b(msg):
        return msg

    async with thirdmagic.abounded_field():
        pre_created = await thirdmagic.sign("pre_created_task")
        nested_swarm = await thirdmagic.swarm(
            [nested_swarm_a, nested_swarm_b], task_name="nested-swarm"
        )
        chain_sig = await thirdmagic.chain(
            [pre_created, ht_mix_chain, nested_swarm, "named_chain_task"]
        )

    reloaded = await assert_task_reloaded_as_type(chain_sig.key, ChainTaskSignature)
    task1, task2, reloaded_nested, task4 = await assert_container_subtasks(
        reloaded,
        ["pre_created_task", "ht_mix_chain", "nested-swarm", "named_chain_task"],
    )
    assert task1.key == pre_created.key
    assert reloaded_nested.key == nested_swarm.key

    reloaded_nested = await assert_task_reloaded_as_type(
        reloaded_nested.key, SwarmTaskSignature
    )
    await assert_container_subtasks(
        reloaded_nested, ["nested_swarm_a", "nested_swarm_b"]
    )


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

    @hatchet_mock.task(name="inner_chain_x")
    def inner_chain_x(msg):
        return msg

    @hatchet_mock.task(name="inner_chain_y")
    def inner_chain_y(msg):
        return msg

    task1 = await thirdmagic.sign(swarm_key_1)

    async with thirdmagic.abounded_field():
        task2 = await thirdmagic.sign(swarm_key_2)
        inner_chain = await thirdmagic.chain([inner_chain_x, inner_chain_y])

        swarm_sig = await thirdmagic.swarm(
            [task1.key, inner_chain, task2], task_name="test-swarm-keys"
        )

    await assert_container_created_with_ordered_tasks(
        swarm_sig.key,
        SwarmTaskSignature,
        [task1.key, inner_chain.key, task2.key],
    )


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_task_names__created_correctly(mock_task_def):
    async with thirdmagic.abounded_field():
        swarm_sig = await thirdmagic.swarm(
            ["swarm_name_a", "swarm_name_b"], task_name="test-swarm-names"
        )

    reloaded = await assert_task_reloaded_as_type(swarm_sig.key, SwarmTaskSignature)
    await assert_container_subtasks(reloaded, ["swarm_name_a", "swarm_name_b"])


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
    await assert_container_subtasks(reloaded, ["ht_swarm_1", "ht_swarm_2"])


@pytest.mark.asyncio
async def test__abounded_field__swarm_from_mixed_inputs__created_correctly(
    hatchet_mock, mock_task_def
):
    @hatchet_mock.task(name="ht_swarm_mix")
    def ht_swarm_mix(msg):
        return msg

    @hatchet_mock.task(name="nested_chain_a")
    def nested_chain_a(msg):
        return msg

    @hatchet_mock.task(name="nested_chain_b")
    def nested_chain_b(msg):
        return msg

    pre_created = await thirdmagic.sign("pre_swarm_task")

    async with thirdmagic.abounded_field():
        nested_chain = await thirdmagic.chain([nested_chain_a, nested_chain_b])
        swarm_sig = await thirdmagic.swarm(
            [pre_created.key, ht_swarm_mix, nested_chain, "named_swarm_task"],
            task_name="test-swarm-mix",
        )

    reloaded = await assert_task_reloaded_as_type(swarm_sig.key, SwarmTaskSignature)
    task1, task2, reloaded_nested, task4 = await assert_container_subtasks(
        reloaded,
        [
            "pre_swarm_task",
            "ht_swarm_mix",
            "chain-task:nested_chain_a",
            "named_swarm_task",
        ],
    )
    assert task1.key == pre_created.key
    assert reloaded_nested.key == nested_chain.key

    reloaded_nested = await assert_task_reloaded_as_type(
        reloaded_nested.key, ChainTaskSignature
    )
    await assert_container_subtasks(
        reloaded_nested, ["nested_chain_a", "nested_chain_b"]
    )


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
    await assert_container_subtasks(reloaded_chain, ["chain_1", "chain_2"])

    reloaded_swarm = await assert_task_reloaded_as_type(
        swarm_sig.key, SwarmTaskSignature
    )
    await assert_container_subtasks(reloaded_swarm, ["swarm_1", "swarm_2"])


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

    await assert_container_subtasks(reloaded1, ["c1_task_a", "c1_task_b"])
    await assert_container_subtasks(reloaded2, ["c2_task_a", "c2_task_b"])


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

    await assert_container_subtasks(reloaded1, ["s1_task"])
    await assert_container_subtasks(reloaded2, ["s2_task"])

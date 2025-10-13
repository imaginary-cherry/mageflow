async def assert_redis_keys_do_not_contain_sub_task_ids(redis_client, sub_task_ids):
    all_keys = await redis_client.keys("*")
    all_keys_str = [
        key.decode() if isinstance(key, bytes) else str(key) for key in all_keys
    ]

    for sub_task_id in sub_task_ids:
        sub_task_id_str = str(sub_task_id)
        keys_containing_sub_task = [
            key for key in all_keys_str if sub_task_id_str in key
        ]
        assert (
            not keys_containing_sub_task
        ), f"Found Redis keys containing deleted sub-task ID {sub_task_id}: {keys_containing_sub_task}"

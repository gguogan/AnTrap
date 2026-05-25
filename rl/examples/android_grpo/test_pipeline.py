"""End-to-end pipeline test for Android GRPO training.

Tests the full interaction loop WITHOUT a model (uses dummy actions).
Validates: HTTP client → remote server → task init → screenshot → action → score

Usage:
    python test_pipeline.py                          # test 1 emulator
    python test_pipeline.py --num_emus 8             # test all 8
    python test_pipeline.py --server_url http://localhost:29101
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

from android_env_client import AndroidEnvClient, AndroidEnvClientPool


def test_health(pool: AndroidEnvClientPool):
    """Test server and emulator health."""
    print("=== Health Check ===")
    health = pool.health_check()
    for emu_id, ok in health.items():
        status = "OK" if ok else "FAIL"
        print(f"  Emu {emu_id}: {status}")
    n_ok = sum(health.values())
    print(f"  {n_ok}/{len(health)} healthy")
    return n_ok > 0


def test_task_list(client: AndroidEnvClient):
    """Test fetching task list."""
    print("\n=== Task List ===")
    import requests
    resp = requests.get(f"{client.base_url.rsplit('/emu', 1)[0]}/suite/task_list", params={"max_index": 5}, timeout=30)
    data = resp.json()
    print(f"  Total tasks: {data['total']}")
    print(f"  First 5: {data['task_list']}")
    return data["task_list"]


def test_single_trajectory(client: AndroidEnvClient, task_type: str, task_idx: int = 0, max_steps: int = 3):
    """Run a short dummy trajectory on one emulator."""
    emu_id = client.emu_id
    print(f"\n=== Trajectory Test: Emu {emu_id}, Task={task_type} ===")

    # Reset
    print(f"  [{emu_id}] Resetting...")
    t0 = time.time()
    client.reset(go_home=True)
    print(f"  [{emu_id}] Reset done ({time.time() - t0:.1f}s)")

    # Initialize task
    print(f"  [{emu_id}] Initializing task...")
    t0 = time.time()
    client.initialize_task(task_type, task_idx)
    print(f"  [{emu_id}] Task initialized ({time.time() - t0:.1f}s)")

    # Get goal
    goal = client.get_goal()
    print(f"  [{emu_id}] Goal: {goal[:100]}...")

    # Multi-step interaction with dummy actions
    for step in range(max_steps):
        # Screenshot
        t0 = time.time()
        screenshot = client.screenshot(wait_to_stabilize=True)
        dt = time.time() - t0
        print(f"  [{emu_id}] Step {step}: screenshot {screenshot.size} ({dt:.2f}s)")

        # Dummy action: just press home
        t0 = time.time()
        client.execute_action({"action_type": "press_home"})
        dt = time.time() - t0
        print(f"  [{emu_id}] Step {step}: action executed ({dt:.2f}s)")

        time.sleep(1)

    # Score
    t0 = time.time()
    is_successful = client.score_task()
    dt = time.time() - t0
    print(f"  [{emu_id}] Score: {is_successful} ({dt:.2f}s)")

    # Tear down
    client.tear_down_task()
    print(f"  [{emu_id}] Task torn down")

    return is_successful


def test_parallel_reset(pool: AndroidEnvClientPool, task_types: list, num_emus: int):
    """Test parallel reset of multiple emulators."""
    print(f"\n=== Parallel Reset Test ({num_emus} emulators) ===")
    import concurrent.futures

    def reset_one(emu_id):
        client = pool[emu_id]
        task_type = task_types[emu_id % len(task_types)]
        t0 = time.time()
        client.reset(go_home=True)
        client.initialize_task(task_type, 0)
        screenshot = client.screenshot()
        dt = time.time() - t0
        return emu_id, task_type, screenshot.size, dt

    t_total = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_emus) as executor:
        futures = [executor.submit(reset_one, i) for i in range(num_emus)]
        results = [f.result() for f in futures]

    dt_total = time.time() - t_total
    for emu_id, task, size, dt in results:
        print(f"  Emu {emu_id}: {task} → {size} ({dt:.1f}s)")
    print(f"  Total parallel time: {dt_total:.1f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_url", default="http://localhost:29101")
    parser.add_argument("--num_emus", type=int, default=1)
    parser.add_argument("--max_steps", type=int, default=3)
    args = parser.parse_args()

    pool = AndroidEnvClientPool(args.server_url, num_emulators=args.num_emus)

    # 1. Health check
    if not test_health(pool):
        print("FAIL: No healthy emulators")
        return

    # 2. Task list
    task_types = test_task_list(pool[0])

    # 3. Single trajectory
    test_single_trajectory(pool[0], task_types[0], max_steps=args.max_steps)

    # 4. Parallel reset (if multiple emus)
    if args.num_emus > 1:
        test_parallel_reset(pool, task_types, args.num_emus)

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    main()

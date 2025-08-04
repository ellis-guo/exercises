import time
from algorithms.hybrid_selector import HybridSelector
from algorithms.greedy_selector import GreedySelector
import sys
import os

# 将当前目录添加到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def run_comparison():
    """运行并比较两种算法"""

    print("="*60)
    print("Workout Plan Comparison: Greedy vs Hybrid")
    print("="*60)

    # 1. 运行贪心算法
    print("\n1. Running Greedy Algorithm...")
    print("-"*40)
    start_time = time.time()

    greedy_selector = GreedySelector()
    greedy_plan = greedy_selector.generate_weekly_plan()

    greedy_time = time.time() - start_time
    greedy_total_score = sum(day['total_score']
                             for day in greedy_plan.values())

    print(f"Greedy completed in {greedy_time:.3f} seconds")
    print(f"Total weekly score: {greedy_total_score:.2f}")

    # 2. 运行混合算法
    print("\n2. Running Hybrid Algorithm...")
    print("-"*40)
    start_time = time.time()

    hybrid_selector = HybridSelector()
    hybrid_plan = hybrid_selector.generate_weekly_plan()

    hybrid_time = time.time() - start_time
    hybrid_total_score = sum(day['total_score']
                             for day in hybrid_plan.values())

    print(f"Hybrid completed in {hybrid_time:.3f} seconds")
    print(f"Total weekly score: {hybrid_total_score:.2f}")

    # 3. 比较结果
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    print(
        f"Score improvement: {hybrid_total_score - greedy_total_score:.2f} ({(hybrid_total_score/greedy_total_score - 1)*100:.1f}%)")
    print(f"Time ratio: {hybrid_time/greedy_time:.1f}x slower")

    # 4. 可选：打印详细计划
    choice = input("\nShow detailed plans? (y/n): ")
    if choice.lower() == 'y':
        print("\n" + "="*60)
        print("GREEDY ALGORITHM PLAN")
        print("="*60)
        greedy_selector.print_detailed_plan(greedy_plan)

        print("\n" + "="*60)
        print("HYBRID ALGORITHM PLAN")
        print("="*60)
        hybrid_selector.print_detailed_plan(hybrid_plan)


if __name__ == "__main__":
    # 运行比较
    run_comparison()

    # 或者只运行一个算法
    # selector = HybridSelector()  # 或 GreedySelector()
    # plan = selector.generate_weekly_plan()
    # selector.print_detailed_plan(plan)

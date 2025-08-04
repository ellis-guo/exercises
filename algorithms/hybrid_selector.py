try:
    from .base_selector import BaseSelector
except ImportError:
    from base_selector import BaseSelector
from typing import List, Set, Dict
from itertools import combinations
import time


class HybridSelector(BaseSelector):
    """
    混合算法选择器
    - 候选动作 ≤ 30个：使用穷举算法
    - 候选动作 > 30个：使用贪心算法 + 2-opt优化
    """

    def _select_exercises_for_day(self, muscle_groups: List[str],
                                  global_selected_ids: Set[int]) -> List[Dict]:
        """
        为特定的一天选择5个动作 - 使用混合策略
        """
        # 获取候选动作
        candidates = self._get_candidate_exercises(
            muscle_groups, global_selected_ids)

        # 记录算法选择
        num_candidates = len(candidates)

        if num_candidates <= 30:
            # 使用穷举算法
            print(f"  Using exhaustive search ({num_candidates} candidates)")
            return self._exhaustive_search(candidates, global_selected_ids)
        else:
            # 使用贪心 + 2-opt
            print(f"  Using greedy + 2-opt ({num_candidates} candidates)")
            greedy_result = self._greedy_search(
                candidates, global_selected_ids)
            return self._two_opt_improvement(greedy_result, candidates, global_selected_ids)

    def _exhaustive_search(self, candidates: Dict[int, Dict],
                           global_selected_ids: Set[int]) -> List[Dict]:
        """穷举所有5个动作的组合，找到最优解"""
        candidate_ids = list(candidates.keys())

        if len(candidate_ids) < 5:
            # 候选不足5个，返回所有
            return self._build_result_from_ids(candidate_ids, candidates, global_selected_ids)

        best_combination = None
        best_total_score = float('-inf')

        # 尝试所有组合
        for combo in combinations(candidate_ids, 5):
            total_score = self._evaluate_combination(
                combo, candidates, global_selected_ids)

            if total_score > best_total_score:
                best_total_score = total_score
                best_combination = combo

        return self._build_result_from_ids(best_combination, candidates, global_selected_ids)

    def _greedy_search(self, candidates: Dict[int, Dict],
                       global_selected_ids: Set[int]) -> List[Dict]:
        """贪心算法实现（与GreedySelector相同）"""
        selected_exercises = []
        selected_ids = set()
        selected_families = set()

        for position in range(self.config['algorithm_params']['exercises_per_day']):
            best_exercise_id = None
            best_score = float('-inf')
            best_dynamic_score = 0

            for exercise_id, data in candidates.items():
                if exercise_id in selected_ids:
                    continue

                dynamic_score = self._calculate_dynamic_score(
                    data['exercise'],
                    position,
                    selected_exercises,
                    selected_families,
                    global_selected_ids
                )

                total_score = data['static_score'] + dynamic_score

                if total_score > best_score:
                    best_score = total_score
                    best_exercise_id = exercise_id
                    best_dynamic_score = dynamic_score

            if best_exercise_id:
                selected_exercise = candidates[best_exercise_id]['exercise']

                exercise_with_score = {
                    'pk': selected_exercise['pk'],
                    'name': selected_exercise['name'],
                    'primaryMuscles': selected_exercise['primaryMuscles'],
                    'secondaryMuscles': selected_exercise.get('secondaryMuscles', []),
                    'static_score': round(candidates[best_exercise_id]['static_score'], 2),
                    'dynamic_score': round(best_dynamic_score, 2),
                    'score': round(best_score, 2),
                    'position': position + 1
                }

                selected_exercises.append(exercise_with_score)
                selected_ids.add(best_exercise_id)

                family = self._get_exercise_family(best_exercise_id)
                if family:
                    selected_families.add(family)

        return selected_exercises

    def _two_opt_improvement(self, initial_solution: List[Dict],
                             candidates: Dict[int, Dict],
                             global_selected_ids: Set[int]) -> List[Dict]:
        """2-opt局部优化：尝试交换动作位置来改进解"""
        current_solution = initial_solution.copy()
        current_score = sum(ex['score'] for ex in current_solution)

        print(f"    Initial greedy score: {current_score:.2f}")

        improved = True
        iterations = 0
        max_iterations = 100  # 防止无限循环

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1

            # 尝试交换任意两个位置的动作
            for i in range(5):
                for j in range(i + 1, 5):
                    # 创建新解：交换位置i和j的动作
                    new_solution = self._swap_and_recalculate(
                        current_solution, i, j, candidates, global_selected_ids
                    )

                    new_score = sum(ex['score'] for ex in new_solution)

                    # 如果改进了，接受新解
                    if new_score > current_score:
                        current_solution = new_solution
                        current_score = new_score
                        improved = True
                        break

                if improved:
                    break

        print(
            f"    After 2-opt: {current_score:.2f} ({iterations} iterations)")

        return current_solution

    def _evaluate_combination(self, combo: tuple, candidates: Dict[int, Dict],
                              global_selected_ids: Set[int]) -> float:
        """评估一个动作组合的总分"""
        total_score = 0
        selected_families = set()

        for position, exercise_id in enumerate(combo):
            # 构建已选动作列表（用于动态评分）
            selected_so_far = []
            for i in range(position):
                selected_so_far.append({'pk': combo[i]})

            # 计算动态分数
            dynamic_score = self._calculate_dynamic_score(
                candidates[exercise_id]['exercise'],
                position,
                selected_so_far,
                selected_families,
                global_selected_ids
            )

            # 累加总分
            total_score += candidates[exercise_id]['static_score'] + \
                dynamic_score

            # 更新已选族
            family = self._get_exercise_family(exercise_id)
            if family:
                selected_families.add(family)

        return total_score

    def _build_result_from_ids(self, exercise_ids: tuple, candidates: Dict[int, Dict],
                               global_selected_ids: Set[int]) -> List[Dict]:
        """根据ID列表构建完整的结果"""
        result = []
        selected_families = set()

        for position, exercise_id in enumerate(exercise_ids):
            # 构建已选动作列表
            selected_so_far = result.copy()

            # 计算动态分数
            dynamic_score = self._calculate_dynamic_score(
                candidates[exercise_id]['exercise'],
                position,
                selected_so_far,
                selected_families,
                global_selected_ids
            )

            # 构建结果
            exercise = candidates[exercise_id]['exercise']
            static_score = candidates[exercise_id]['static_score']

            exercise_with_score = {
                'pk': exercise['pk'],
                'name': exercise['name'],
                'primaryMuscles': exercise['primaryMuscles'],
                'secondaryMuscles': exercise.get('secondaryMuscles', []),
                'static_score': round(static_score, 2),
                'dynamic_score': round(dynamic_score, 2),
                'score': round(static_score + dynamic_score, 2),
                'position': position + 1
            }

            result.append(exercise_with_score)

            # 更新族
            family = self._get_exercise_family(exercise_id)
            if family:
                selected_families.add(family)

        return result

    def _swap_and_recalculate(self, solution: List[Dict], pos1: int, pos2: int,
                              candidates: Dict[int, Dict],
                              global_selected_ids: Set[int]) -> List[Dict]:
        """交换两个位置的动作并重新计算所有分数"""
        # 获取动作ID列表
        exercise_ids = [ex['pk'] for ex in solution]

        # 交换
        exercise_ids[pos1], exercise_ids[pos2] = exercise_ids[pos2], exercise_ids[pos1]

        # 重新计算（因为位置分数会变）
        return self._build_result_from_ids(exercise_ids, candidates, global_selected_ids)

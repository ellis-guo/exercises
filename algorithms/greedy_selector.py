try:
    from .base_selector import BaseSelector
except ImportError:
    from base_selector import BaseSelector
from typing import List, Set, Dict


class GreedySelector(BaseSelector):
    """
    贪心算法选择器
    每个位置选择当前最优的动作
    """

    def _select_exercises_for_day(self, muscle_groups: List[str],
                                  global_selected_ids: Set[int]) -> List[Dict]:
        """
        为特定的一天选择5个动作 - 使用贪心算法

        Args:
            muscle_groups: 当天要训练的肌群列表
            global_selected_ids: 全周已选择的动作ID集合

        Returns:
            包含5个动作的列表，每个动作包含分数信息
        """
        # 1. 获取候选动作和它们的静态分数
        candidates = self._get_candidate_exercises(
            muscle_groups, global_selected_ids)

        # 2. 贪心选择5个动作
        selected_exercises = []
        selected_ids = set()
        selected_families = set()

        for position in range(self.config['algorithm_params']['exercises_per_day']):
            best_exercise_id = None
            best_score = float('-inf')
            best_dynamic_score = 0

            # 计算每个候选动作在当前位置的总分
            for exercise_id, data in candidates.items():
                if exercise_id in selected_ids:
                    continue

                # 计算动态分数
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

            # 添加最佳动作
            if best_exercise_id:
                selected_exercise = candidates[best_exercise_id]['exercise']

                # 创建包含分数信息的动作记录
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

                # 更新已选择的动作族
                family = self._get_exercise_family(best_exercise_id)
                if family:
                    selected_families.add(family)

        return selected_exercises

# greedy_algorithm.py - 关键修改部分
# -*- coding: utf-8 -*-

import json
import os
import sys
from typing import Dict, List, Tuple, Set

# [编码设置部分保持不变...]


class GreedyWorkoutSelector:
    # ========== 用户配置区 ==========
    # 训练天数设置 (1-7)
    TRAINING_DAYS = 6

    # 肌群系数预设（方便修改）
    DEFAULT_MUSCLE_PREFERENCES = {
        "abdominal": 1.0,
        "bicep": 1.0,
        "calf": 1.2,
        "chest": 1.0,
        "forearm - inner": 1.0,
        "forearm - outer": 1.0,
        "glute": 1.0,
        "hamstring": 1.0,
        "lat": 1.0,
        "lower back": 1.0,
        "oblique": 1.0,
        "quad": 1.0,
        "rotator cuff - back": 1.0,
        "rotator cuff - front": 1.0,
        "shoulder - back": 1.5,
        "shoulder - front": 1.5,
        "shoulder - side": 1.5,
        "thigh - inner": 1.2,
        "thigh - outer": 1.2,
        "trap": 1.0,
        "tricep": 1.0
    }

    # 排除的动作
    EXCLUDED_EXERCISES = {
        35
    }
    # ========== 配置区结束 ==========

    def __init__(self):
        # [初始化部分保持不变...]
        pass

    def _calculate_static_score(self, exercise: Dict, muscle_preferences: Dict) -> float:
        """计算静态分数 - 使用递减机制"""
        score = 0

        # 从配置文件获取参数
        primary_config = self.config['scoring_weights']['primary_muscle']
        secondary_config = self.config['scoring_weights']['secondary_muscle']

        # 主肌群分数（递减机制）
        primary_muscles = exercise.get('primaryMuscles', [])
        for i, muscle in enumerate(primary_muscles):
            if i < primary_config['full_score_limit']:
                # 前N个肌群得满分
                muscle_score = primary_config['base_score']
            else:
                # 之后的肌群递减
                decay_times = i - primary_config['full_score_limit'] + 1
                muscle_score = primary_config['base_score'] * \
                    (primary_config['decay_factor'] ** decay_times)

            preference = muscle_preferences.get(muscle, 1.0)
            score += muscle_score * preference

        # 次肌群分数（递减机制）
        secondary_muscles = exercise.get('secondaryMuscles', [])
        for i, muscle in enumerate(secondary_muscles):
            if i < secondary_config['full_score_limit']:
                # 前N个肌群得满分
                muscle_score = secondary_config['base_score']
            else:
                # 之后的肌群递减
                decay_times = i - secondary_config['full_score_limit'] + 1
                muscle_score = secondary_config['base_score'] * \
                    (secondary_config['decay_factor'] ** decay_times)

            preference = muscle_preferences.get(muscle, 1.0)
            score += muscle_score * preference

        return score

    def _calculate_dynamic_score(self, exercise: Dict, position: int,
                                 selected_exercises: List[Dict],
                                 selected_families: Set[str],
                                 global_selected_ids: Set[int]) -> float:
        """计算动态分数"""
        score = 0
        exercise_id = exercise['pk']

        # 位置加分 - 从配置文件读取
        position_scores = self.config['position_scores']

        # 复合/孤立
        if exercise_id in self.classifications['compound_isolation']['compound']:
            score += position_scores['compound'][position]
        elif exercise_id in self.classifications['compound_isolation']['isolation']:
            score += position_scores['isolation'][position]

        # 自由/器械
        if exercise_id in self.classifications['equipment']['free']:
            score += position_scores['free_weight'][position]
        elif exercise_id in self.classifications['equipment']['equipment']:
            score += position_scores['machine'][position]

        # 统计已选动作的特征
        bilateral_count = 0
        compound_count = 0
        machine_count = 0

        for ex in selected_exercises:
            ex_id = ex['pk']
            if ex_id in self.classifications['laterality']['bilateral']:
                bilateral_count += 1
            if ex_id in self.classifications['compound_isolation']['compound']:
                compound_count += 1
            if ex_id in self.classifications['equipment']['equipment']:
                machine_count += 1

        # 从配置文件读取多样性规则
        diversity = self.config['diversity_rules']

        # 单双侧平衡加分 - 使用新的渐进式规则
        bilateral_balance = diversity['bilateral_balance']
        if bilateral_count < len(bilateral_balance['thresholds']):
            if exercise_id in self.classifications['laterality']['bilateral']:
                score += bilateral_balance['bilateral_bonus'][bilateral_count]
            elif exercise_id in self.classifications['laterality']['single_sided']:
                score += bilateral_balance['unilateral_bonus'][bilateral_count]

        # 复合/孤立平衡加分
        compound_balance = diversity['compound_balance']
        if compound_count < compound_balance['min_compound_for_bonus']:
            if exercise_id in self.classifications['compound_isolation']['compound']:
                score += compound_balance['compound_bonus']
        elif compound_count >= compound_balance['compound_threshold']:
            if exercise_id in self.classifications['compound_isolation']['isolation']:
                score += compound_balance['isolation_bonus']

        # 器械/自由平衡加分
        equipment_balance = diversity['equipment_balance']
        if machine_count < equipment_balance['min_machine_for_bonus']:
            if exercise_id in self.classifications['equipment']['equipment']:
                score += equipment_balance['machine_bonus']
        elif machine_count >= equipment_balance['machine_threshold']:
            if exercise_id in self.classifications['equipment']['free']:
                score += equipment_balance['free_weight_bonus']

        # 同族动作扣分
        family = self._get_exercise_family(exercise_id)
        if family and family in selected_families:
            score += diversity['same_family_penalty']

        # 全周重复动作扣分
        if exercise_id in global_selected_ids:
            score += diversity['same_exercise_penalty']

        return score

    # [其他方法保持不变...]

    def print_static_score_analysis(self) -> None:
        """打印静态分数分析，帮助理解递减机制"""
        self._safe_print("\n" + "="*60)
        self._safe_print("Static Score Analysis (Decay Mechanism)")
        self._safe_print("="*60)

        # 示例：展示不同肌群数量的动作得分
        examples = [
            {"name": "Bicep Curl", "primary": 1, "secondary": 1},
            {"name": "Bench Press", "primary": 2, "secondary": 1},
            {"name": "Squat", "primary": 4, "secondary": 1},
            {"name": "Clean and Jerk", "primary": 5, "secondary": 7}
        ]

        primary_config = self.config['scoring_weights']['primary_muscle']
        secondary_config = self.config['scoring_weights']['secondary_muscle']

        for ex in examples:
            primary_score = 0
            for i in range(ex['primary']):
                if i < primary_config['full_score_limit']:
                    primary_score += primary_config['base_score']
                else:
                    decay_times = i - primary_config['full_score_limit'] + 1
                    primary_score += primary_config['base_score'] * \
                        (primary_config['decay_factor'] ** decay_times)

            secondary_score = 0
            for i in range(ex['secondary']):
                if i < secondary_config['full_score_limit']:
                    secondary_score += secondary_config['base_score']
                else:
                    decay_times = i - secondary_config['full_score_limit'] + 1
                    secondary_score += secondary_config['base_score'] * (
                        secondary_config['decay_factor'] ** decay_times)

            total = primary_score + secondary_score
            self._safe_print(f"\n{ex['name']}:")
            self._safe_print(
                f"  Primary muscles: {ex['primary']} → {primary_score:.2f} points")
            self._safe_print(
                f"  Secondary muscles: {ex['secondary']} → {secondary_score:.2f} points")
            self._safe_print(f"  Total static score: {total:.2f} points")


# 使用示例
if __name__ == "__main__":
    selector = GreedyWorkoutSelector()

    # 可选：先打印静态分数分析
    # selector.print_static_score_analysis()

    print("Generating workout plan...")
    weekly_plan = selector.generate_weekly_plan()
    selector.print_detailed_plan(weekly_plan)

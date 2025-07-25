# greedy_algorithm.py
# -*- coding: utf-8 -*-

import json
import os
import sys
from typing import Dict, List, Tuple, Set

# 设置输出编码
if sys.platform.startswith('win'):
    import locale
    if locale.getpreferredencoding().upper() != 'UTF-8':
        os.system('chcp 65001')  # 设置Windows控制台为UTF-8


class GreedyWorkoutSelector:
    def __init__(self):
        # 获取当前文件所在目录（exercises文件夹）
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 加载所有需要的文件
        self.exercises = self._load_json(
            os.path.join(current_dir, 'strength.json'))
        self.config = self._load_json(os.path.join(current_dir, 'config.json'))

        # 加载分类文件
        classification_dir = os.path.join(current_dir, 'classification')
        self.classifications = {
            'upper_lower': self._load_json(os.path.join(classification_dir, 'ontology1_upper_lower.json')),
            'ppl': self._load_json(os.path.join(classification_dir, 'ontology2_PPL.json')),
            'chest_shoulder_back_armsabs': self._load_json(os.path.join(classification_dir, 'ontology3_chestShoulder_back_armsAbs.json')),
            'chest_legs_back_arms_shoulderscore': self._load_json(os.path.join(classification_dir, 'ontology4_chest_legs_back_arms_shouldersCore.json')),
            'laterality': self._load_json(os.path.join(classification_dir, 'type1_laterality.json')),
            'equipment': self._load_json(os.path.join(classification_dir, 'type2_equipmentMode.json')),
            'compound_isolation': self._load_json(os.path.join(classification_dir, 'type3_compoundIsolation.json')),
            'movement_family': self._load_json(os.path.join(classification_dir, 'type4_movementFamily.json'))
        }

        # 定义训练模板
        self.template_mapping = {
            1: None,  # 所有肌群一起
            2: 'upper_lower',
            3: 'ppl',
            4: 'chest_shoulder_back_armsabs',
            5: 'chest_legs_back_arms_shoulderscore',
            6: 'ppl',  # PPL×2
            7: 'ppl'   # PPL×2
        }

        # 定义训练计划
        self.schedules = {
            1: ["Full Body"],
            2: ["upper", "lower"],
            3: ["push", "pull", "legs"],
            4: ["chest_shoulder", "back", "arms_abs", "legs"],
            5: ["chest", "legs", "back", "arms", "shoulders_core"],
            6: ["push", "pull", "legs", "push", "pull", "legs"],
            7: ["push", "pull", "legs", "push", "pull", "legs", "rest"]
        }

    def _load_json(self, filepath: str) -> Dict:
        """加载JSON文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_user_input(self) -> Dict:
        """获取用户输入"""
        print("\n" + "="*60)
        print("Welcome to Smart Workout Plan Generator!")
        print("="*60)

        # 获取训练天数
        while True:
            try:
                print("\nPlease select weekly training days (1-7):")
                print("1 - Full Body")
                print("2 - Upper/Lower Split")
                print("3 - Push/Pull/Legs")
                print("4 - Chest&Shoulder/Back/Arms&Abs/Legs")
                print("5 - Chest/Legs/Back/Arms/Shoulders&Core")
                print("6 - Push/Pull/Legs x2")
                print("7 - Push/Pull/Legs x2 + Rest")

                training_days = int(input("\nYour choice: "))
                if 1 <= training_days <= 7:
                    break
                else:
                    print("Please enter a number between 1-7!")
            except ValueError:
                print("Please enter a valid number!")

        # 获取肌群偏好
        muscle_preferences = {}
        print("\nDo you have specific muscle groups you want to focus on? (y/n)")
        if input().lower() == 'y':
            print("\nPlease enter muscle preferences (example format):")
            print('{')
            print('    "chest": 2,')
            print('    "back": 1.5,')
            print('    "glute": 2')
            print('}')
            print("\nAvailable muscle groups:")
            muscles = ["abdominal", "bicep", "calf", "chest", "forearm - inner",
                       "forearm - outer", "glute", "hamstring", "lat", "lower back",
                       "oblique", "quad", "rotator cuff - back", "rotator cuff - front",
                       "shoulder - back", "shoulder - front", "shoulder - side",
                       "thigh - inner", "thigh - outer", "trap", "tricep"]
            print(", ".join(muscles))

            print(
                "\nPlease paste your muscle preferences in JSON format (press Enter twice when done):")
            preference_input = []
            while True:
                line = input()
                if line:
                    preference_input.append(line)
                else:
                    break

            try:
                muscle_preferences = json.loads('\n'.join(preference_input))
            except:
                print("Format error, using default settings (all muscles weight = 1)")

        return {
            "training_days": training_days,
            "muscle_preferences": muscle_preferences
        }

    def generate_weekly_plan(self, user_input: Dict) -> Dict:
        """生成一周的训练计划，包含分数信息"""
        training_days = user_input['training_days']
        muscle_preferences = user_input.get('muscle_preferences', {})

        # 获取对应的训练模板
        template_name = self.template_mapping[training_days]
        schedule = self.schedules[training_days]

        weekly_plan = {}

        for day_index, day_type in enumerate(schedule):
            if day_type == "rest":
                weekly_plan[f"Day {day_index + 1}"] = {
                    "type": "Rest Day",
                    "exercises": [],
                    "total_score": 0
                }
            else:
                # 为这一天选择动作（包含分数）
                exercises_with_scores = self._select_exercises_for_day(
                    day_index,
                    day_type,
                    template_name,
                    muscle_preferences
                )

                # 计算当日总分
                total_day_score = sum(ex['score']
                                      for ex in exercises_with_scores)

                weekly_plan[f"Day {day_index + 1}"] = {
                    "type": day_type.replace('_', ' ').title(),
                    "exercises": exercises_with_scores,
                    "total_score": round(total_day_score, 2)
                }

        return weekly_plan

    def _select_exercises_for_day(self, day_index: int, day_type: str,
                                  template_name: str, muscle_preferences: Dict) -> List[Dict]:
        """为特定的一天选择5个动作，返回包含分数的列表"""
        # 1. 获取今天要训练的动作ID列表
        if template_name:
            template_data = self.classifications[template_name]
            exercise_ids = template_data.get(day_type, [])
        else:
            # 训练天数为1时，使用所有动作
            exercise_ids = [ex['pk'] for ex in self.exercises]

        # 2. 计算每个动作的静态分数
        exercise_scores = {}
        for exercise_id in exercise_ids:
            exercise = self._get_exercise_by_id(exercise_id)
            if exercise:
                static_score = self._calculate_static_score(
                    exercise, muscle_preferences)
                exercise_scores[exercise_id] = {
                    'exercise': exercise,
                    'static_score': static_score,
                    'total_score': static_score  # 初始总分等于静态分数
                }

        # 3. 贪心选择5个动作
        selected_exercises = []
        selected_ids = set()
        selected_families = set()

        for position in range(5):
            best_exercise_id = None
            best_score = float('-inf')
            best_dynamic_score = 0

            # 计算每个候选动作在当前位置的总分
            for exercise_id, data in exercise_scores.items():
                if exercise_id in selected_ids:
                    continue

                # 计算动态分数
                dynamic_score = self._calculate_dynamic_score(
                    data['exercise'],
                    position,
                    selected_exercises,
                    selected_families
                )

                total_score = data['static_score'] + dynamic_score

                if total_score > best_score:
                    best_score = total_score
                    best_exercise_id = exercise_id
                    best_dynamic_score = dynamic_score

            # 添加最佳动作
            if best_exercise_id:
                selected_exercise = exercise_scores[best_exercise_id]['exercise']

                # 创建包含分数信息的动作记录
                exercise_with_score = {
                    'pk': selected_exercise['pk'],  # 添加pk
                    'name': selected_exercise['name'],
                    'primaryMuscles': selected_exercise['primaryMuscles'],
                    'secondaryMuscles': selected_exercise.get('secondaryMuscles', []),
                    'static_score': round(exercise_scores[best_exercise_id]['static_score'], 2),
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

    def _get_exercise_by_id(self, exercise_id: int) -> Dict:
        """根据ID获取动作"""
        for exercise in self.exercises:
            if exercise['pk'] == exercise_id:
                return exercise
        return None

    def _calculate_static_score(self, exercise: Dict, muscle_preferences: Dict) -> float:
        """计算静态分数"""
        score = 0

        # 主肌群分数（分摊）
        primary_muscles = exercise.get('primaryMuscles', [])
        if primary_muscles:
            primary_score_per_muscle = self.config['scoring_weights']['primary_muscle'] / len(
                primary_muscles)
            for muscle in primary_muscles:
                preference = muscle_preferences.get(muscle, 1.0)
                score += primary_score_per_muscle * preference

        # 次肌群分数（分摊）
        secondary_muscles = exercise.get('secondaryMuscles', [])
        if secondary_muscles:
            secondary_score_per_muscle = self.config['scoring_weights']['secondary_muscle'] / len(
                secondary_muscles)
            for muscle in secondary_muscles:
                preference = muscle_preferences.get(muscle, 1.0)
                score += secondary_score_per_muscle * preference

        # 删除了复合/孤立动作加分

        return score

    def _calculate_dynamic_score(self, exercise: Dict, position: int,
                                 selected_exercises: List[Dict],
                                 selected_families: Set[str]) -> float:
        """计算动态分数"""
        score = 0
        exercise_id = exercise['pk']

        # 位置加分 - 复合/孤立
        if exercise_id in self.classifications['compound_isolation']['compound']:
            score += self.config['position_scores']['compound'][position]
        elif exercise_id in self.classifications['compound_isolation']['isolation']:
            score += self.config['position_scores']['isolation'][position]

        # 位置加分 - 自由/器械
        if exercise_id in self.classifications['equipment']['free']:
            score += self.config['position_scores']['free_weight'][position]
        elif exercise_id in self.classifications['equipment']['equipment']:
            score += self.config['position_scores']['machine'][position]

        # 统计已选动作的特征
        bilateral_count = 0
        compound_count = 0
        machine_count = 0

        for ex in selected_exercises:
            # 使用已经存储的pk
            ex_id = ex['pk']
            if ex_id in self.classifications['laterality']['bilateral']:
                bilateral_count += 1
            if ex_id in self.classifications['compound_isolation']['compound']:
                compound_count += 1
            if ex_id in self.classifications['equipment']['equipment']:
                machine_count += 1

        # 单双侧平衡加分
        if bilateral_count < self.config['diversity_rules']['min_bilateral_for_bonus']:
            if exercise_id in self.classifications['laterality']['bilateral']:
                score += self.config['diversity_rules']['bilateral_bonus']
        elif bilateral_count >= self.config['diversity_rules']['bilateral_threshold']:
            if exercise_id in self.classifications['laterality']['single_sided']:
                score += self.config['diversity_rules']['unilateral_bonus']

        # 复合/孤立平衡加分
        if compound_count < self.config['diversity_rules']['min_compound_for_bonus']:
            if exercise_id in self.classifications['compound_isolation']['compound']:
                score += self.config['diversity_rules']['compound_bonus']
        elif compound_count >= self.config['diversity_rules']['compound_threshold']:
            if exercise_id in self.classifications['compound_isolation']['isolation']:
                score += self.config['diversity_rules']['isolation_bonus']

        # 器械/自由平衡加分
        if machine_count < self.config['diversity_rules']['min_machine_for_bonus']:
            if exercise_id in self.classifications['equipment']['equipment']:
                score += self.config['diversity_rules']['machine_bonus']
        elif machine_count >= self.config['diversity_rules']['machine_threshold']:
            if exercise_id in self.classifications['equipment']['free']:
                score += self.config['diversity_rules']['free_weight_bonus']

        # 同族动作扣分
        family = self._get_exercise_family(exercise_id)
        if family and family in selected_families:
            score += self.config['diversity_rules']['same_family_penalty']

        return score

    def _get_exercise_family(self, exercise_id: int) -> str:
        """获取动作所属的族"""
        for family_name, exercise_ids in self.classifications['movement_family'].items():
            if exercise_id in exercise_ids:
                return family_name
        return None

    def print_detailed_plan(self, weekly_plan: Dict) -> None:
        """打印详细的训练计划，包含分数"""
        print("\n" + "="*80)
        print("Weekly Workout Plan (Generated by Greedy Algorithm)")
        print("="*80)

        for day, plan in weekly_plan.items():
            print(f"\n{day}: {plan['type']}")
            print(f"Daily Total Score: {plan['total_score']}")
            print("-" * 60)

            if plan['exercises']:
                for exercise in plan['exercises']:
                    print(
                        f"\nPosition {exercise['position']}. [{exercise['pk']}] {exercise['name']}")
                    print(
                        f"   Static Score: {exercise['static_score']} | Dynamic Score: {exercise['dynamic_score']} | Total: {exercise['score']}")
                    print(
                        f"   Primary Muscles: {', '.join(exercise['primaryMuscles'])}")
                    if exercise['secondaryMuscles']:
                        print(
                            f"   Secondary Muscles: {', '.join(exercise['secondaryMuscles'])}")
            else:
                print("   Rest and Recovery!")


# 使用示例
if __name__ == "__main__":
    # 创建选择器实例
    selector = GreedyWorkoutSelector()

    # 获取用户输入
    user_input = selector.get_user_input()

    print("\nGenerating your personalized workout plan...")

    # 生成训练计划
    weekly_plan = selector.generate_weekly_plan(user_input)

    # 打印详细计划
    selector.print_detailed_plan(weekly_plan)

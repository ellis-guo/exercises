import json
import os
import sys
from typing import Dict, List, Tuple, Set

# 强制设置UTF-8编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Windows控制台UTF-8设置
if sys.platform.startswith('win'):
    import locale
    # 设置Python的默认编码
    if hasattr(sys, 'setdefaultencoding'):
        sys.setdefaultencoding('utf-8')
    # 设置Windows控制台代码页
    os.system('chcp 65001 > nul 2>&1')  # 静默执行
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'


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

    # 排除的动作（因为没有器械或其他原因不做的动作）
    # 可以使用动作ID(pk)或动作名称
    EXCLUDED_EXERCISES = {
        35
    }
    # ========== 配置区结束 ==========

    def __init__(self):
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 加载所有需要的文件 - 明确指定UTF-8编码
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
            'movement_family': self._load_json(os.path.join(classification_dir, 'type4_movementFamily.json')),
            'common': self._load_json(os.path.join(classification_dir, 'type5_isCommon.json'))
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
        """加载JSON文件 - 使用UTF-8编码"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _safe_print(self, text: str) -> None:
        """安全打印，处理编码问题"""
        try:
            print(text)
        except UnicodeEncodeError:
            # 如果直接打印失败，尝试编码后再打印
            print(text.encode('utf-8', errors='replace').decode('utf-8'))

    def generate_weekly_plan(self) -> Dict:
        """生成一周的训练计划，包含分数信息"""
        training_days = self.TRAINING_DAYS

        # 使用预设的肌群偏好
        muscle_preferences = self.DEFAULT_MUSCLE_PREFERENCES.copy()

        # 获取对应的训练模板
        template_name = self.template_mapping[training_days]
        schedule = self.schedules[training_days]

        weekly_plan = {}
        global_selected_ids = set()  # 追踪整周已选动作，避免重复

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
                    muscle_preferences,
                    global_selected_ids  # 传递全局已选动作集合
                )

                # 更新全局已选动作集合
                for ex in exercises_with_scores:
                    global_selected_ids.add(ex['pk'])

                # 计算当日总分
                total_day_score = sum(ex['score']
                                      for ex in exercises_with_scores)

                weekly_plan[f"Day {day_index + 1}"] = {
                    "type": day_type.replace('_', ' ').title(),
                    "exercises": exercises_with_scores,
                    "total_score": round(total_day_score, 2)
                }

        return weekly_plan

    def _is_exercise_excluded(self, exercise: Dict) -> bool:
        """检查动作是否在排除列表中"""
        # 检查ID
        if exercise['pk'] in self.EXCLUDED_EXERCISES:
            return True

        # 检查名称（部分匹配）
        for excluded in self.EXCLUDED_EXERCISES:
            if isinstance(excluded, str):
                # 如果是字符串，检查是否包含在动作名称中
                if excluded.lower() in exercise['name'].lower():
                    return True

        return False

    def _select_exercises_for_day(self, day_index: int, day_type: str,
                                  template_name: str, muscle_preferences: Dict,
                                  global_selected_ids: Set[int]) -> List[Dict]:
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
            # 检查是否被排除
            if exercise and not self._is_exercise_excluded(exercise):
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
                    selected_families,
                    global_selected_ids  # 传递全局已选动作集合
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

        # 核心动作加分
        core_bonus_config = diversity.get('core_exercise_bonus', {})
        if exercise_id in self.classifications['common'].get('Common', []):
            positions = core_bonus_config.get('positions', [])
            bonus_scores = core_bonus_config.get('bonus_scores', [])
            if position in positions:
                pos_index = positions.index(position)
                if pos_index < len(bonus_scores):
                    score += bonus_scores[pos_index]

        # 复合/孤立动作额外位置加分
        compound_position_config = diversity.get('compound_position_bonus', {})
        if compound_position_config:
            positions = compound_position_config.get('positions', [])
            if position in positions:
                pos_index = positions.index(position)
                if exercise_id in self.classifications['compound_isolation']['compound']:
                    compound_extra = compound_position_config.get(
                        'compound_extra', [])
                    if pos_index < len(compound_extra):
                        score += compound_extra[pos_index]
                elif exercise_id in self.classifications['compound_isolation']['isolation']:
                    isolation_extra = compound_position_config.get(
                        'isolation_extra', [])
                    if pos_index < len(isolation_extra):
                        score += isolation_extra[pos_index]

        return score

    def _get_exercise_family(self, exercise_id: int) -> str:
        """获取动作所属的族"""
        for family_name, exercise_ids in self.classifications['movement_family'].items():
            if exercise_id in exercise_ids:
                return family_name
        return None

    def print_detailed_plan(self, weekly_plan: Dict) -> None:
        """打印详细的训练计划，包含分数"""
        self._safe_print("\n" + "="*80)
        self._safe_print("Weekly Workout Plan (Generated by Greedy Algorithm)")
        self._safe_print("="*80)

        # 显示当前配置
        template_names = {
            1: "Full Body",
            2: "Upper/Lower Split",
            3: "Push/Pull/Legs",
            4: "Chest&Shoulder/Back/Arms&Abs/Legs",
            5: "Chest/Legs/Back/Arms/Shoulders&Core",
            6: "Push/Pull/Legs x2",
            7: "Push/Pull/Legs x2 + Rest"
        }
        self._safe_print(
            f"\nTraining Days: {self.TRAINING_DAYS} ({template_names[self.TRAINING_DAYS]})")

        # 显示当前使用的肌群系数
        self._safe_print("\nCurrent Muscle Preferences:")
        non_default = {
            k: v for k, v in self.DEFAULT_MUSCLE_PREFERENCES.items() if v != 1.0}
        if non_default:
            for muscle, coef in non_default.items():
                self._safe_print(f"  {muscle}: {coef}")
        else:
            self._safe_print("  All muscles: 1.0 (default)")

        # 显示排除的动作
        if self.EXCLUDED_EXERCISES:
            self._safe_print("\nExcluded Exercises:")
            for excluded in self.EXCLUDED_EXERCISES:
                if isinstance(excluded, int):
                    # 如果是ID，尝试找到对应的动作名称
                    ex = self._get_exercise_by_id(excluded)
                    if ex:
                        self._safe_print(f"  - [{excluded}] {ex['name']}")
                    else:
                        self._safe_print(f"  - ID: {excluded}")
                else:
                    self._safe_print(f"  - Contains: '{excluded}'")

        for day, plan in weekly_plan.items():
            self._safe_print(f"\n{day}: {plan['type']}")
            self._safe_print(f"Daily Total Score: {plan['total_score']}")
            self._safe_print("-" * 60)

            if plan['exercises']:
                for exercise in plan['exercises']:
                    self._safe_print(
                        f"\nPosition {exercise['position']}. [{exercise['pk']}] {exercise['name']}")
                    self._safe_print(
                        f"   Static Score: {exercise['static_score']} | Dynamic Score: {exercise['dynamic_score']} | Total: {exercise['score']}")
                    self._safe_print(
                        f"   Primary Muscles: {', '.join(exercise['primaryMuscles'])}")
                    if exercise['secondaryMuscles']:
                        self._safe_print(
                            f"   Secondary Muscles: {', '.join(exercise['secondaryMuscles'])}")
            else:
                self._safe_print("   Rest and Recovery!")

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


# 直接运行
if __name__ == "__main__":
    # 创建选择器实例
    selector = GreedyWorkoutSelector()

    print("Generating workout plan...")

    # 生成训练计划
    weekly_plan = selector.generate_weekly_plan()

    # 打印详细计划
    selector.print_detailed_plan(weekly_plan)

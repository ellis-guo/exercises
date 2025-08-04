import json
import os
import sys
from typing import Dict, List, Tuple, Set
from abc import ABC, abstractmethod

# 强制设置UTF-8编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# Windows控制台UTF-8设置
if sys.platform.startswith('win'):
    import locale
    # 设置Windows控制台代码页
    os.system('chcp 65001 > nul 2>&1')  # 静默执行
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'


class BaseSelector(ABC):
    """
    基类选择器，包含所有共享的数据加载、评分计算、打印等功能
    子类只需要实现 _select_exercises_for_day 方法
    """

    # ========== 用户配置区 ==========
    # 训练天数设置 (1-7)
    TRAINING_DAYS = 5

    # 肌群系数预设（基于preferenceMapping的大类）
    # 可选值：chest, back, shoulder, arm, leg, core
    MUSCLE_PREFERENCES = {
        "chest": 1.0,
        "back": 1.0,
        "shoulder": 1.0,
        "arm": 1.0,
        "leg": 1.0,
        "core": 1.0
    }

    # 排除的动作（使用动作ID）
    EXCLUDED_EXERCISES = {
        35  # 示例：排除 Rotational Throw – Medicine Ball
    }
    # ========== 配置区结束 ==========

    def __init__(self):
        # 获取 project 根目录
        # 当前文件在 project/exercises/algorithms/base_selector.py
        # 所以需要向上三级到达 project/
        current_file_dir = os.path.dirname(
            os.path.abspath(__file__))  # algorithms/
        exercises_dir = os.path.dirname(current_file_dir)  # exercises/
        project_root = os.path.dirname(exercises_dir)  # project/

        # 加载所有需要的文件
        self.exercises = self._load_json(
            os.path.join(project_root, 'exercises', 'strength.json'))
        self.config = self._load_json(
            os.path.join(project_root, 'exercises', 'config.json'))

        # 加载分类文件
        classification_dir = os.path.join(
            project_root, 'exercises', 'classification')

        # 加载新的映射文件（在classification文件夹中）
        self.category_mapping = self._load_json(
            os.path.join(classification_dir, 'categoryMapping.json'))
        self.preference_mapping = self._load_json(
            os.path.join(classification_dir, 'preferenceMapping.json'))
        self.training_templates = self._load_json(
            os.path.join(classification_dir, 'trainingTemplates.json'))

        self.classifications = {
            'major': self._load_json(os.path.join(classification_dir, 'type1_isMajor.json')),
            'compound': self._load_json(os.path.join(classification_dir, 'type2_isCompound.json')),
            'single': self._load_json(os.path.join(classification_dir, 'type3_isSingle.json')),
            'machine': self._load_json(os.path.join(classification_dir, 'type4_isMachine.json')),
            'common': self._load_json(os.path.join(classification_dir, 'type5_isCommon.json')),
            'family': self._load_json(os.path.join(classification_dir, 'type6_movementFamily.json'))
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
            print(text.encode('utf-8', errors='replace').decode('utf-8'))

    def generate_weekly_plan(self) -> Dict:
        """生成一周的训练计划"""
        training_days = self.TRAINING_DAYS

        # 获取训练模板
        template = self.training_templates[str(training_days)]

        weekly_plan = {}
        global_selected_ids = set()  # 追踪整周已选动作，避免重复

        for day_index, muscle_groups in enumerate(template):
            day_name = f"Day {day_index + 1}"

            # 休息日
            if not muscle_groups:
                weekly_plan[day_name] = {
                    "type": "Rest Day",
                    "exercises": [],
                    "total_score": 0
                }
                continue

            # 为这一天选择动作 - 调用子类实现的方法
            exercises_with_scores = self._select_exercises_for_day(
                muscle_groups,
                global_selected_ids
            )

            # 更新全局已选动作集合
            for ex in exercises_with_scores:
                global_selected_ids.add(ex['pk'])

            # 计算当日总分
            total_day_score = sum(ex['score'] for ex in exercises_with_scores)

            # 生成训练类型描述
            day_type = self._generate_day_type(muscle_groups)

            weekly_plan[day_name] = {
                "type": day_type,
                "muscle_groups": muscle_groups,
                "exercises": exercises_with_scores,
                "total_score": round(total_day_score, 2)
            }

        return weekly_plan

    @abstractmethod
    def _select_exercises_for_day(self, muscle_groups: List[str],
                                  global_selected_ids: Set[int]) -> List[Dict]:
        """
        为特定的一天选择5个动作
        这是子类必须实现的核心方法

        Args:
            muscle_groups: 当天要训练的肌群列表
            global_selected_ids: 全周已选择的动作ID集合

        Returns:
            包含5个动作的列表，每个动作包含分数信息
        """
        pass

    def _get_candidate_exercises(self, muscle_groups: List[str],
                                 global_selected_ids: Set[int]) -> Dict[int, Dict]:
        """获取候选动作并计算静态分数"""
        # 1. 获取今天要训练的动作ID列表
        exercise_ids = set()
        for muscle_group in muscle_groups:
            if muscle_group in self.category_mapping:
                exercise_ids.update(self.category_mapping[muscle_group])

        # 如果是全身训练
        if not exercise_ids or muscle_groups == ["all"]:
            exercise_ids = {ex['pk'] for ex in self.exercises}

        # 2. 计算每个动作的静态分数
        candidates = {}
        for exercise_id in exercise_ids:
            exercise = self._get_exercise_by_id(exercise_id)
            # 检查是否被排除
            if exercise and not self._is_exercise_excluded(exercise):
                static_score = self._calculate_static_score(exercise)
                candidates[exercise_id] = {
                    'exercise': exercise,
                    'static_score': static_score
                }

        return candidates

    def _generate_day_type(self, muscle_groups: List[str]) -> str:
        """根据肌群列表生成训练日类型描述"""
        muscle_names = {
            "chest": "Chest",
            "back": "Back",
            "shoulder": "Shoulders",
            "tricep": "Triceps",
            "bicep": "Biceps",
            "legs": "Legs",
            "arm": "Arms",
            "core": "Core"
        }

        names = [muscle_names.get(mg, mg.title()) for mg in muscle_groups]

        if len(names) == 1:
            return names[0]
        elif len(names) == 2:
            return f"{names[0]} & {names[1]}"
        else:
            return f"{', '.join(names[:-1])} & {names[-1]}"

    def _get_muscle_preference(self, muscle: str) -> float:
        """获取具体肌群的偏好系数"""
        # 找出这个具体肌群属于哪个大类
        for category, muscles in self.preference_mapping.items():
            if muscle in muscles:
                return self.MUSCLE_PREFERENCES.get(category, 1.0)
        return 1.0

    def _get_exercise_by_id(self, exercise_id: int) -> Dict:
        """根据ID获取动作"""
        for exercise in self.exercises:
            if exercise['pk'] == exercise_id:
                return exercise
        return None

    def _is_exercise_excluded(self, exercise: Dict) -> bool:
        """检查动作是否在排除列表中"""
        return exercise['pk'] in self.EXCLUDED_EXERCISES

    def _calculate_static_score(self, exercise: Dict) -> float:
        """计算静态分数 - 使用分摊机制"""
        score = 0

        # 从配置文件获取参数
        primary_base = self.config['scoring_weights']['primary_muscle']['base_score']
        secondary_base = self.config['scoring_weights']['secondary_muscle']['base_score']

        # 主肌群分数（分摊机制）
        primary_muscles = exercise.get('primaryMuscles', [])
        if primary_muscles:
            score_per_muscle = primary_base / len(primary_muscles)
            for muscle in primary_muscles:
                preference = self._get_muscle_preference(muscle)
                score += score_per_muscle * preference

        # 次肌群分数（分摊机制）
        secondary_muscles = exercise.get('secondaryMuscles', [])
        if secondary_muscles:
            score_per_muscle = secondary_base / len(secondary_muscles)
            for muscle in secondary_muscles:
                preference = self._get_muscle_preference(muscle)
                score += score_per_muscle * preference

        # 常用动作加分
        if exercise['pk'] in self.classifications['common']['Common']:
            score += self.config['scoring_weights']['common_exercise_bonus']['score']

        return score

    def _calculate_dynamic_score(self, exercise: Dict, position: int,
                                 selected_exercises: List[Dict],
                                 selected_families: Set[str],
                                 global_selected_ids: Set[int]) -> float:
        """计算动态分数 - 两层结构"""
        score = 0
        exercise_id = exercise['pk']

        # === 第一层：位置相关得分 ===
        position_scores = self.config['position_scores']

        # 大肌群动作位置得分
        if exercise_id in self.classifications['major']['Major']:
            score += position_scores['major_muscle']['scores'][position]
        # 小肌群动作位置得分
        elif exercise_id in self.classifications['major']['Minor']:
            score += position_scores['minor_muscle']['scores'][position]

        # 复合动作位置得分
        if exercise_id in self.classifications['compound']['compound']:
            score += position_scores['compound']['scores'][position]
        # 孤立动作位置得分
        elif exercise_id in self.classifications['compound']['isolation']:
            score += position_scores['isolation']['scores'][position]

        # 自由重量位置得分
        if exercise_id in self.classifications['machine']['free']:
            score += position_scores['free_weight']['scores'][position]
        # 器械动作位置得分
        elif exercise_id in self.classifications['machine']['equipment']:
            score += position_scores['equipment']['scores'][position]

        # === 第二层：多样性平衡 ===
        # 统计已选动作的特征
        bilateral_count = 0
        compound_count = 0
        machine_count = 0

        # 统计已选动作覆盖的肌群（基于categoryMapping）
        selected_muscle_groups = set()
        for ex in selected_exercises:
            ex_id = ex['pk']
            # 找出这个动作属于哪些肌群
            for muscle_group, exercise_ids in self.category_mapping.items():
                if ex_id in exercise_ids:
                    selected_muscle_groups.add(muscle_group)

            if ex_id in self.classifications['single']['bilateral']:
                bilateral_count += 1
            if ex_id in self.classifications['compound']['compound']:
                compound_count += 1
            if ex_id in self.classifications['machine']['equipment']:
                machine_count += 1

        # 从配置文件读取多样性规则
        diversity = self.config['diversity_rules']
        threshold = diversity['balance_threshold']
        penalty = diversity['balance_penalty']

        # 单双侧平衡（只惩罚，不奖励）
        if exercise_id in self.classifications['single']['bilateral'] and bilateral_count >= threshold:
            score += penalty  # 双侧动作超过阈值，惩罚
        elif exercise_id in self.classifications['single']['single_sided'] and (len(selected_exercises) - bilateral_count) >= threshold:
            score += penalty  # 单侧动作超过阈值，惩罚

        # 复合/孤立平衡（只惩罚，不奖励）
        if exercise_id in self.classifications['compound']['compound'] and compound_count >= threshold:
            score += penalty  # 复合动作超过阈值，惩罚
        elif exercise_id in self.classifications['compound']['isolation'] and (len(selected_exercises) - compound_count) >= threshold:
            score += penalty  # 孤立动作超过阈值，惩罚

        # 器械/自由平衡（只惩罚，不奖励）
        if exercise_id in self.classifications['machine']['equipment'] and machine_count >= threshold:
            score += penalty  # 器械动作超过阈值，惩罚
        elif exercise_id in self.classifications['machine']['free'] and (len(selected_exercises) - machine_count) >= threshold:
            score += penalty  # 自由动作超过阈值，惩罚

        # === 惩罚机制 ===
        penalties = diversity['penalties']

        # 同族动作惩罚
        family = self._get_exercise_family(exercise_id)
        if family and family in selected_families:
            score += penalties['same_family']

        # 全周重复动作惩罚
        if exercise_id in global_selected_ids:
            score += penalties['weekly_repeat']

        # 同肌群动作惩罚：计算当前动作有多少肌群已被选中
        muscle_group_overlap = 0
        for muscle_group, exercise_ids in self.category_mapping.items():
            if exercise_id in exercise_ids and muscle_group in selected_muscle_groups:
                muscle_group_overlap += 1

        if muscle_group_overlap > 0:
            score += penalties['same_muscle_group'] * muscle_group_overlap

        return score

    def _get_exercise_family(self, exercise_id: int) -> str:
        """获取动作所属的族"""
        for family_name, exercise_ids in self.classifications['family'].items():
            if exercise_id in exercise_ids:
                return family_name
        return None

    def print_detailed_plan(self, weekly_plan: Dict) -> None:
        """打印详细的训练计划"""
        self._safe_print("\n" + "="*80)
        self._safe_print(
            f"Weekly Workout Plan (Generated by {self.__class__.__name__})")
        self._safe_print("="*80)

        # 显示当前配置
        template_names = {
            1: "Full Body",
            2: "Upper/Lower Split",
            3: "Push/Pull/Legs",
            4: "Push/Pull x2",
            5: "Bro Split",
            6: "Push/Pull/Legs x2",
            7: "Push/Pull/Legs x2 + Rest"
        }
        self._safe_print(
            f"\nTraining Days: {self.TRAINING_DAYS} ({template_names[self.TRAINING_DAYS]})")

        # 显示当前使用的肌群系数
        self._safe_print("\nCurrent Muscle Preferences:")
        non_default = {k: v for k,
                       v in self.MUSCLE_PREFERENCES.items() if v != 1.0}
        if non_default:
            for muscle, coef in sorted(non_default.items()):
                self._safe_print(f"  {muscle}: {coef}")
        else:
            self._safe_print("  All muscle groups: 1.0 (default)")

        # 显示排除的动作
        if self.EXCLUDED_EXERCISES:
            self._safe_print("\nExcluded Exercises:")
            for excluded_id in self.EXCLUDED_EXERCISES:
                ex = self._get_exercise_by_id(excluded_id)
                if ex:
                    self._safe_print(f"  - [{excluded_id}] {ex['name']}")
                else:
                    self._safe_print(f"  - ID: {excluded_id}")

        # 打印每日计划
        for day, plan in weekly_plan.items():
            self._safe_print(f"\n{day}: {plan['type']}")
            if 'muscle_groups' in plan and plan['muscle_groups']:
                self._safe_print(
                    f"Target Muscles: {', '.join(plan['muscle_groups'])}")
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

    def print_scoring_explanation(self) -> None:
        """打印评分机制说明"""
        self._safe_print("\n" + "="*60)
        self._safe_print("Scoring Mechanism Explanation")
        self._safe_print("="*60)

        self._safe_print(
            "\nStatic Score (Muscle-based with sharing mechanism):")
        self._safe_print(
            "  - Primary muscles: 3.0 ÷ number of muscles × preference")
        self._safe_print(
            "  - Secondary muscles: 2.0 ÷ number of muscles × preference")
        self._safe_print("  - Common exercises: +2.0 bonus")

        self._safe_print("\nDynamic Score Layer 1 (Position-based):")
        self._safe_print("  - Major muscle exercises: [+8, +5, 0, 0, 0]")
        self._safe_print("  - Minor muscle exercises: [0, 0, 0, +5, +8]")
        self._safe_print("  - Compound exercises: [+8, +5, 0, 0, 0]")
        self._safe_print("  - Isolation exercises: [0, 0, 0, +5, +8]")
        self._safe_print("  - Free weight exercises: [+3, +2, 0, 0, 0]")
        self._safe_print("  - Equipment exercises: [0, 0, 0, +2, +3]")

        self._safe_print("\nDynamic Score Layer 2 (Diversity balance):")
        self._safe_print("  - Bilateral: >3 selected → -3 penalty")
        self._safe_print("  - Unilateral: >3 selected → -3 penalty")
        self._safe_print("  - Compound: >3 selected → -3 penalty")
        self._safe_print("  - Isolation: >3 selected → -3 penalty")
        self._safe_print("  - Machine: >3 selected → -3 penalty")
        self._safe_print("  - Free weight: >3 selected → -3 penalty")

        self._safe_print("\nPenalties:")
        self._safe_print("  - Same movement family: -10")
        self._safe_print("  - Weekly repetition: -8")
        self._safe_print(
            "  - Same muscle group: -1 per overlapping muscle group")

"""
Skills package initialization
Register all available skills here
"""
from typing import Dict
from src.skills.base import BaseSkill
from src.skills.manager import SkillManager


def register_all_skills(skill_manager: SkillManager, config: Dict) -> None:
    """Register all enabled skills according to config"""
    from src.skills.smzdm_opencli import SmzdmOpencliSkill

    # 只注册 smzdm 好价搜索 skill
    enabled_skills = config['skills'].get('enabled', ['smzdm'])

    skill_map = {
        'smzdm': SmzdmOpencliSkill,
    }

    for name in enabled_skills:
        if name in skill_map:
            skill_cls = skill_map[name]
            skill_config = config['skills'].get(name, {})
            if skill_config.get('enabled', True):
                skill = skill_cls(skill_config)
                if skill.enabled:
                    skill_manager.register(skill)

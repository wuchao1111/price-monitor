"""
Skill Manager - manages all registered skills, handles routing and querying
"""
import asyncio
from typing import Dict, List, Optional
from logging import getLogger
from src.skills.base import BaseSkill
from src.models.schemas import PriceResult


logger = getLogger(__name__)


class SkillManager:
    """Manager for all registered price query skills"""

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """
        Register a skill

        Args:
            skill: Skill instance to register
        """
        if skill.name in self._skills:
            logger.warning(f"Skill {skill.name} already registered, overwriting")
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name} - {skill.description}")

    def unregister(self, skill_name: str) -> None:
        """
        Unregister a skill

        Args:
            skill_name: Name of skill to unregister
        """
        if skill_name in self._skills:
            del self._skills[skill_name]
            logger.info(f"Unregistered skill: {skill_name}")

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """Get a skill by name"""
        return self._skills.get(skill_name)

    def list_skills(self) -> List[BaseSkill]:
        """List all registered skills"""
        return list(self._skills.values())

    def list_enabled_skills(self) -> List[BaseSkill]:
        """List all enabled skills"""
        return [s for s in self._skills.values() if s.enabled]

    async def query_all(
        self,
        keyword: str,
        skill_names: Optional[List[str]] = None
    ) -> List[PriceResult]:
        """
        Query price from all relevant skills

        Args:
            keyword: Search keyword
            skill_names: Optional list of skill names to query, None means all enabled

        Returns:
            List of PriceResult, sorted by price ascending
        """
        skills_to_query: List[BaseSkill]

        if skill_names:
            skills_to_query = [
                self._skills[name]
                for name in skill_names
                if name in self._skills and self._skills[name].enabled
            ]
        else:
            skills_to_query = [
                s for s in self._skills.values()
                if s.enabled and s.is_supported(keyword)
            ]

        if not skills_to_query:
            logger.warning(f"No skills available to query for keyword: {keyword}")
            return []

        # Query all skills concurrently
        tasks = [skill.query_price(keyword) for skill in skills_to_query]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all valid results
        all_results: List[PriceResult] = []
        for skill, result in zip(skills_to_query, results):
            if isinstance(result, Exception):
                logger.error(f"Skill {skill.name} failed: {result}")
                continue
            all_results.extend(result)

        # Sort by price ascending (cheapest first)
        all_results.sort(key=lambda x: x.price)

        logger.info(
            f"Query '{keyword}' got {len(all_results)} results from {len(skills_to_query)} skills"
        )
        return all_results

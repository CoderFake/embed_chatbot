"""Prompt loader for lead scoring."""
import yaml
from pathlib import Path
from typing import Dict

from app.config.settings import settings
from app.cache.keys import CacheKeys
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """Load and manage scoring prompts."""
    
    def __init__(self, prompts_dir: str = "app/static/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, str] = {}
    
    def load_prompt(self, prompt_name: str) -> str:
        """
        Load prompt from YAML file and format with language.
        
        Args:
            prompt_name: Name of prompt file (without .yaml extension)
            
        Returns:
            Prompt content as string with language formatted
        """
        cache_key = CacheKeys.prompt_cache(prompt_name, settings.GRADING_OUTPUT_LANGUAGE)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        prompt_file = self.prompts_dir / f"{prompt_name}.yaml"
        
        if not prompt_file.exists():
            logger.error(f"Prompt file not found: {prompt_file}")
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            prompt_template = data.get("prompt", "")
            prompt = prompt_template.format(language=settings.GRADING_OUTPUT_LANGUAGE)
            
            self._cache[cache_key] = prompt
            
            logger.info(f"Loaded prompt: {prompt_name} (language: {settings.GRADING_OUTPUT_LANGUAGE})")
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to load prompt {prompt_name}: {e}", exc_info=True)
            raise


# Global instance
prompt_loader = PromptLoader()


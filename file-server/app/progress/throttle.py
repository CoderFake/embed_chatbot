"""
Progress throttling logic - ensures progress updates are not sent too frequently
Publishes if:
1. Progress delta >= 5% OR
2. Time since last publish >= 3 seconds
"""
from typing import Dict, Optional
from dataclasses import dataclass
import time


@dataclass
class ProgressState:
    """State for progress throttling"""
    last_progress: float = 0.0
    last_published_at: float = 0.0
    

class ProgressThrottle:
    """
    Throttles progress updates based on percentage delta and time elapsed.
    
    Configuration from settings:
    - PROGRESS_MIN_DELTA: Minimum percentage change to trigger publish (default: 5%)
    - PROGRESS_MIN_INTERVAL: Minimum seconds between publishes (default: 3s)
    """
    
    def __init__(self, min_delta: float = 5.0, min_interval: float = 3.0):
        """
        Initialize throttle
        
        Args:
            min_delta: Minimum progress percentage change to trigger publish
            min_interval: Minimum seconds between publishes
        """
        self.min_delta = min_delta
        self.min_interval = min_interval
        self._states: Dict[str, ProgressState] = {}
    
    def should_publish(self, task_id: str, current_progress: float, force: bool = False) -> bool:
        """
        Check if progress update should be published
        
        Args:
            task_id: Unique task identifier
            current_progress: Current progress percentage (0-100)
            force: Force publish regardless of throttle rules
            
        Returns:
            True if should publish, False otherwise
        """
        if force:
            return True
        
        if task_id not in self._states:
            self._states[task_id] = ProgressState()
        
        state = self._states[task_id]
        current_time = time.time()
        
        progress_delta = abs(current_progress - state.last_progress)
        
        time_elapsed = current_time - state.last_published_at
        
        should_publish = (
            progress_delta >= self.min_delta or
            time_elapsed >= self.min_interval
        )
        
        if should_publish:
            state.last_progress = current_progress
            state.last_published_at = current_time
        
        return should_publish
    
    def reset(self, task_id: str):
        """Reset throttle state for a task"""
        if task_id in self._states:
            del self._states[task_id]
    
    def cleanup(self, task_ids: Optional[list[str]] = None):
        """
        Clean up states for completed tasks
        
        Args:
            task_ids: List of task IDs to clean up. If None, cleans all.
        """
        if task_ids is None:
            self._states.clear()
        else:
            for task_id in task_ids:
                self.reset(task_id)

"""
Activity Scheduler for AI Community Companions.
Orchestrates bot activities, manages queues, and coordinates timing.
"""

import asyncio
import heapq
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Awaitable
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import random

from mind.core.types import (
    ScheduledActivity, ActivityType, BotProfile, EmotionalState
)
from mind.config.settings import settings
from mind.blocking.blocking_service import blocking_service


# ============================================================================
# PRIORITY QUEUE TYPES
# ============================================================================

class ActivityPriority(int, Enum):
    """Priority levels for activities (lower = higher priority)."""
    CRITICAL = 1       # Direct mentions, urgent responses
    HIGH = 3          # Replies to conversations
    NORMAL = 5        # Regular posts, comments
    LOW = 7           # Background activity
    BACKGROUND = 10   # Maintenance tasks


@dataclass(order=True)
class PrioritizedActivity:
    """Activity with priority for heap queue."""
    priority: int
    scheduled_time: datetime
    activity: ScheduledActivity = field(compare=False)


# ============================================================================
# ACTIVITY SCHEDULER
# ============================================================================

class ActivityScheduler:
    """
    Manages the scheduling and execution of bot activities.
    Uses a priority queue with time-based scheduling.
    """

    def __init__(self, max_concurrent: int = 50):
        self.max_concurrent = max_concurrent
        self.activity_queue: List[PrioritizedActivity] = []
        self.running_tasks: Dict[UUID, asyncio.Task] = {}
        self.handlers: Dict[ActivityType, Callable] = {}
        self._running = False
        self._lock = asyncio.Lock()

    def register_handler(
        self,
        activity_type: ActivityType,
        handler: Callable[[ScheduledActivity], Awaitable[Any]]
    ):
        """Register a handler for an activity type."""
        self.handlers[activity_type] = handler

    async def schedule(
        self,
        activity: ScheduledActivity,
        priority: ActivityPriority = ActivityPriority.NORMAL
    ):
        """Add an activity to the schedule."""
        async with self._lock:
            item = PrioritizedActivity(
                priority=priority.value,
                scheduled_time=activity.scheduled_time,
                activity=activity
            )
            heapq.heappush(self.activity_queue, item)

    async def schedule_batch(
        self,
        activities: List[ScheduledActivity],
        priority: ActivityPriority = ActivityPriority.NORMAL
    ):
        """Schedule multiple activities at once."""
        async with self._lock:
            for activity in activities:
                item = PrioritizedActivity(
                    priority=priority.value,
                    scheduled_time=activity.scheduled_time,
                    activity=activity
                )
                heapq.heappush(self.activity_queue, item)

    async def cancel(self, activity_id: UUID) -> bool:
        """Cancel a scheduled activity."""
        async with self._lock:
            # Find and mark as cancelled
            for item in self.activity_queue:
                if item.activity.id == activity_id:
                    item.activity.is_cancelled = True
                    return True

            # Check running tasks
            if activity_id in self.running_tasks:
                self.running_tasks[activity_id].cancel()
                return True

            return False

    async def start(self):
        """Start the scheduler loop."""
        self._running = True
        asyncio.create_task(self._scheduler_loop())

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        # Cancel all running tasks
        for task in self.running_tasks.values():
            task.cancel()

    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                await self._process_due_activities()
                await asyncio.sleep(1)  # Check every second
            except Exception as e:
                # Log error but keep running
                print(f"Scheduler error: {e}")
                await asyncio.sleep(5)

    async def _process_due_activities(self):
        """Process activities that are due."""
        now = datetime.utcnow()

        while self.activity_queue:
            async with self._lock:
                if not self.activity_queue:
                    break

                # Peek at next activity
                next_item = self.activity_queue[0]

                # Not due yet
                if next_item.scheduled_time > now:
                    break

                # Check if we have capacity
                if len(self.running_tasks) >= self.max_concurrent:
                    break

                # Pop and process
                item = heapq.heappop(self.activity_queue)

            # Skip cancelled activities
            if item.activity.is_cancelled:
                continue

            # Execute the activity
            await self._execute_activity(item.activity)

    async def _execute_activity(self, activity: ScheduledActivity):
        """Execute a single activity."""
        handler = self.handlers.get(ActivityType(activity.activity_type))

        if not handler:
            print(f"No handler for activity type: {activity.activity_type}")
            return

        async def run_activity():
            try:
                await handler(activity)
                activity.is_completed = True
            except Exception as e:
                print(f"Activity {activity.id} failed: {e}")
            finally:
                self.running_tasks.pop(activity.id, None)

        task = asyncio.create_task(run_activity())
        self.running_tasks[activity.id] = task

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the queue."""
        now = datetime.utcnow()

        pending = len([a for a in self.activity_queue if not a.activity.is_cancelled])
        due = len([a for a in self.activity_queue
                  if a.scheduled_time <= now and not a.activity.is_cancelled])

        return {
            "total_pending": pending,
            "due_now": due,
            "running": len(self.running_tasks),
            "capacity_used": len(self.running_tasks) / self.max_concurrent
        }


# ============================================================================
# BOT ORCHESTRATOR
# ============================================================================

class BotOrchestrator:
    """
    High-level orchestrator for bot activities.
    Decides what bots should do and when.
    """

    def __init__(
        self,
        scheduler: ActivityScheduler,
        seed: Optional[int] = None
    ):
        self.scheduler = scheduler
        self.rng = random.Random(seed)
        self.bot_states: Dict[UUID, Dict[str, Any]] = {}

    async def plan_bot_activities(
        self,
        bot: BotProfile,
        time_horizon_hours: int = 24
    ) -> List[ScheduledActivity]:
        """
        Plan activities for a bot over the given time horizon.

        Returns list of scheduled activities.
        """
        activities = []
        current_time = datetime.utcnow()
        end_time = current_time + timedelta(hours=time_horizon_hours)

        pattern = bot.activity_pattern

        # Plan posts
        posts_to_schedule = int(pattern.avg_posts_per_day * (time_horizon_hours / 24))
        for _ in range(posts_to_schedule):
            post_time = self._generate_activity_time(
                bot, current_time, end_time, "post"
            )
            if post_time:
                activities.append(ScheduledActivity(
                    bot_id=bot.id,
                    activity_type=ActivityType.POST,
                    scheduled_time=post_time,
                    context={"type": "organic_post"}
                ))

        # Plan comments/interactions
        comments_to_schedule = int(pattern.avg_comments_per_day * (time_horizon_hours / 24))
        for _ in range(comments_to_schedule):
            comment_time = self._generate_activity_time(
                bot, current_time, end_time, "comment"
            )
            if comment_time:
                activities.append(ScheduledActivity(
                    bot_id=bot.id,
                    activity_type=ActivityType.COMMENT,
                    scheduled_time=comment_time,
                    context={"type": "organic_engagement"}
                ))

        # Plan group chat participation
        chat_events = int(pattern.avg_comments_per_day * 0.5 * (time_horizon_hours / 24))
        for _ in range(chat_events):
            chat_time = self._generate_activity_time(
                bot, current_time, end_time, "chat"
            )
            if chat_time:
                activities.append(ScheduledActivity(
                    bot_id=bot.id,
                    activity_type=ActivityType.GROUP_CHAT,
                    scheduled_time=chat_time,
                    context={"type": "group_participation"}
                ))

        return activities

    def _generate_activity_time(
        self,
        bot: BotProfile,
        start: datetime,
        end: datetime,
        activity_type: str
    ) -> Optional[datetime]:
        """Generate a realistic activity time within the range."""
        pattern = bot.activity_pattern

        # Parse active hours
        wake_hour = int(pattern.wake_time.split(":")[0])
        sleep_hour = int(pattern.sleep_time.split(":")[0])

        # Try up to 10 times to find a valid time
        for _ in range(10):
            # Random time in range
            delta = (end - start).total_seconds()
            random_seconds = self.rng.random() * delta
            candidate = start + timedelta(seconds=random_seconds)

            hour = candidate.hour

            # Check if within active hours
            if sleep_hour < wake_hour:  # Sleeps after midnight
                is_awake = hour >= wake_hour or hour < sleep_hour
            else:
                is_awake = wake_hour <= hour < sleep_hour

            if not is_awake:
                continue

            # Bias toward peak hours
            is_peak = hour in pattern.peak_activity_hours
            if not is_peak and self.rng.random() > 0.4:
                continue

            return candidate

        return None

    async def handle_incoming_message(
        self,
        bot_id: UUID,
        message_context: Dict[str, Any]
    ) -> Optional[ScheduledActivity]:
        """
        Handle an incoming message that might need a response.

        Returns a scheduled activity if the bot should respond.
        """
        # This would integrate with the human behavior engine
        # to determine if/when to respond

        is_direct = message_context.get("is_direct_message", False)
        is_mention = message_context.get("is_mentioned", False)
        sender_id = message_context.get("sender_id")

        # Check if the bot is blocked by the sender (skip response if blocked)
        if sender_id and is_direct:
            is_blocked = await blocking_service.is_blocked(sender_id, bot_id)
            if is_blocked:
                # Don't respond to messages from users who blocked us
                return None

        if is_direct:
            priority = ActivityPriority.HIGH
            base_delay = self.rng.randint(2, 30)  # seconds
        elif is_mention:
            priority = ActivityPriority.HIGH
            base_delay = self.rng.randint(5, 60)
        else:
            priority = ActivityPriority.NORMAL
            base_delay = self.rng.randint(30, 300)

        response_time = datetime.utcnow() + timedelta(seconds=base_delay)

        activity = ScheduledActivity(
            bot_id=bot_id,
            activity_type=ActivityType.REPLY,
            scheduled_time=response_time,
            context=message_context,
            priority=priority.value
        )

        await self.scheduler.schedule(activity, priority)
        return activity

    async def trigger_community_activity(
        self,
        community_id: UUID,
        bot_ids: List[UUID],
        activity_type: str = "discussion"
    ):
        """
        Trigger coordinated activity in a community.

        This creates natural-looking activity waves.
        """
        now = datetime.utcnow()

        # Select subset of bots to participate
        num_participants = max(2, int(len(bot_ids) * self.rng.uniform(0.1, 0.4)))
        participants = self.rng.sample(bot_ids, num_participants)

        activities = []

        for i, bot_id in enumerate(participants):
            # Stagger the activities
            delay = i * self.rng.randint(30, 120)  # 30 seconds to 2 minutes apart
            activity_time = now + timedelta(seconds=delay)

            if i == 0:
                # First bot starts the discussion
                act_type = ActivityType.POST
                context = {"type": "discussion_starter", "community_id": str(community_id)}
            else:
                # Others engage
                act_type = ActivityType.COMMENT
                context = {"type": "discussion_engagement", "community_id": str(community_id)}

            activity = ScheduledActivity(
                bot_id=bot_id,
                activity_type=act_type,
                scheduled_time=activity_time,
                target_id=community_id,
                context=context
            )
            activities.append(activity)

        await self.scheduler.schedule_batch(activities)


# ============================================================================
# INFERENCE BATCH MANAGER
# ============================================================================

class InferenceBatchManager:
    """
    Manages batching of LLM inference requests for efficiency.
    Groups similar requests to maximize throughput.
    """

    def __init__(
        self,
        batch_size: int = 4,
        max_wait_ms: int = 100
    ):
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self.pending_requests: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._batch_event = asyncio.Event()
        self._processor: Optional[Callable] = None

    def set_processor(
        self,
        processor: Callable[[List[Dict]], Awaitable[List[Any]]]
    ):
        """Set the batch processor function."""
        self._processor = processor

    async def submit(self, request: Dict[str, Any]) -> Any:
        """Submit a request and wait for result."""
        future = asyncio.Future()
        request["_future"] = future

        async with self._lock:
            self.pending_requests.append(request)

            # If batch is full, process immediately
            if len(self.pending_requests) >= self.batch_size:
                asyncio.create_task(self._process_batch())
            else:
                # Start timer for partial batch
                asyncio.create_task(self._wait_and_process())

        return await future

    async def _wait_and_process(self):
        """Wait for more requests or timeout, then process."""
        await asyncio.sleep(self.max_wait_ms / 1000)
        await self._process_batch()

    async def _process_batch(self):
        """Process the current batch of requests."""
        async with self._lock:
            if not self.pending_requests:
                return

            batch = self.pending_requests[:self.batch_size]
            self.pending_requests = self.pending_requests[self.batch_size:]

        if not self._processor:
            for req in batch:
                req["_future"].set_exception(Exception("No processor set"))
            return

        try:
            # Extract requests (without futures)
            clean_requests = [{k: v for k, v in r.items() if k != "_future"} for r in batch]

            # Process batch
            results = await self._processor(clean_requests)

            # Distribute results
            for req, result in zip(batch, results):
                req["_future"].set_result(result)

        except Exception as e:
            for req in batch:
                req["_future"].set_exception(e)


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_scheduler(max_concurrent: int = 50) -> ActivityScheduler:
    """Create an activity scheduler."""
    return ActivityScheduler(max_concurrent=max_concurrent)


def create_orchestrator(
    scheduler: ActivityScheduler,
    seed: Optional[int] = None
) -> BotOrchestrator:
    """Create a bot orchestrator."""
    return BotOrchestrator(scheduler=scheduler, seed=seed)


def create_batch_manager(
    batch_size: int = 4,
    max_wait_ms: int = 100
) -> InferenceBatchManager:
    """Create an inference batch manager."""
    return InferenceBatchManager(batch_size=batch_size, max_wait_ms=max_wait_ms)

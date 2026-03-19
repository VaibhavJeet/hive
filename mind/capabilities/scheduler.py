"""
Task Scheduler - Cron-like scheduling for bot activities.

Enables scheduling of recurring tasks, delayed actions, and
time-based triggers for bot behaviors.

Features:
- Cron expression support
- One-time delayed tasks
- Recurring tasks
- Task persistence
- Failure handling and retries
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID, uuid4
import json

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority for scheduling."""
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


# Type for task handlers
TaskHandler = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class TaskResult:
    """Result from task execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0


@dataclass
class ScheduledTask:
    """A scheduled task."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    handler: Optional[TaskHandler] = None
    handler_name: str = ""  # For serialization

    # Scheduling
    next_run: Optional[datetime] = None
    cron_expression: Optional[str] = None  # e.g., "0 * * * *" (hourly)
    interval_seconds: Optional[int] = None  # For simple recurring
    run_once: bool = False

    # Execution
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 60

    # State
    status: TaskStatus = TaskStatus.PENDING
    last_run: Optional[datetime] = None
    last_result: Optional[TaskResult] = None
    run_count: int = 0
    failure_count: int = 0
    enabled: bool = True

    # Association
    bot_id: Optional[UUID] = None
    metadata: dict = field(default_factory=dict)

    def calculate_next_run(self) -> Optional[datetime]:
        """Calculate the next run time."""
        now = datetime.utcnow()

        if self.cron_expression:
            return self._parse_cron_next(now)
        elif self.interval_seconds:
            base = self.last_run or now
            return base + timedelta(seconds=self.interval_seconds)
        elif self.run_once and not self.last_run:
            return self.next_run or now
        return None

    def _parse_cron_next(self, after: datetime) -> datetime:
        """
        Parse cron expression and get next run time.

        Simplified cron: minute hour day_of_month month day_of_week
        Supports: *, */n, n, n-m, n,m,o
        """
        try:
            from croniter import croniter
            cron = croniter(self.cron_expression, after)
            return cron.get_next(datetime)
        except ImportError:
            # Fallback: run hourly if croniter not available
            logger.warning("croniter not installed, using hourly fallback")
            return after + timedelta(hours=1)
        except Exception as e:
            logger.error(f"Invalid cron expression '{self.cron_expression}': {e}")
            return after + timedelta(hours=1)

    def to_dict(self) -> dict:
        """Serialize task for persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "handler_name": self.handler_name,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "cron_expression": self.cron_expression,
            "interval_seconds": self.interval_seconds,
            "run_once": self.run_once,
            "kwargs": self.kwargs,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "enabled": self.enabled,
            "bot_id": str(self.bot_id) if self.bot_id else None,
            "metadata": self.metadata,
        }


class TaskScheduler:
    """
    Manages scheduled tasks and their execution.

    Usage:
        scheduler = TaskScheduler()

        # Schedule a recurring task
        @scheduler.schedule(interval_seconds=3600)  # Hourly
        async def check_notifications():
            ...

        # Schedule with cron expression
        @scheduler.schedule(cron="0 9 * * *")  # Daily at 9 AM
        async def morning_routine():
            ...

        # Start the scheduler
        await scheduler.start()
    """

    def __init__(self, max_concurrent: int = 10):
        self._tasks: dict[str, ScheduledTask] = {}
        self._handlers: dict[str, TaskHandler] = {}
        self._running = False
        self._runner_task: Optional[asyncio.Task] = None
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._execution_tasks: dict[str, asyncio.Task] = {}

    def register_handler(self, name: str, handler: TaskHandler) -> None:
        """Register a task handler by name."""
        self._handlers[name] = handler

    def schedule(
        self,
        cron: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        run_at: Optional[datetime] = None,
        name: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **task_kwargs
    ) -> Callable[[TaskHandler], TaskHandler]:
        """
        Decorator to schedule a task.

        Usage:
            @scheduler.schedule(interval_seconds=60)
            async def my_task():
                ...
        """
        def decorator(handler: TaskHandler) -> TaskHandler:
            task_name = name or handler.__name__
            self.register_handler(task_name, handler)

            task = ScheduledTask(
                name=task_name,
                handler=handler,
                handler_name=task_name,
                cron_expression=cron,
                interval_seconds=interval_seconds,
                next_run=run_at,
                run_once=run_at is not None and not cron and not interval_seconds,
                priority=priority,
                **task_kwargs
            )

            if task.next_run is None:
                task.next_run = task.calculate_next_run()

            self.add_task(task)
            return handler
        return decorator

    def add_task(self, task: ScheduledTask) -> str:
        """Add a task to the scheduler."""
        # Resolve handler if needed
        if task.handler is None and task.handler_name:
            task.handler = self._handlers.get(task.handler_name)

        self._tasks[task.id] = task
        logger.info(f"Scheduled task: {task.name} (next run: {task.next_run})")
        return task.id

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the scheduler."""
        if task_id in self._tasks:
            # Cancel if running
            if task_id in self._execution_tasks:
                self._execution_tasks[task_id].cancel()
            del self._tasks[task_id]
            return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        bot_id: Optional[UUID] = None
    ) -> list[ScheduledTask]:
        """List tasks, optionally filtered."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if bot_id:
            tasks = [t for t in tasks if t.bot_id == bot_id]
        return sorted(tasks, key=lambda t: (t.next_run or datetime.max))

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._runner_task = asyncio.create_task(self._run_loop())
        logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        # Cancel all running tasks
        for task in self._execution_tasks.values():
            task.cancel()

        if self._runner_task:
            self._runner_task.cancel()
            try:
                await self._runner_task
            except asyncio.CancelledError:
                pass

        logger.info("Task scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()

                # Find tasks ready to run
                ready_tasks = [
                    task for task in self._tasks.values()
                    if (task.enabled and
                        task.status == TaskStatus.PENDING and
                        task.next_run and
                        task.next_run <= now)
                ]

                # Sort by priority
                ready_tasks.sort(key=lambda t: -t.priority.value)

                # Execute ready tasks
                for task in ready_tasks:
                    if not self._running:
                        break
                    asyncio.create_task(self._execute_task(task))

                # Sleep before next check
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task."""
        async with self._semaphore:
            task.status = TaskStatus.RUNNING
            start_time = datetime.utcnow()

            try:
                # Create execution task with timeout
                exec_task = asyncio.create_task(
                    asyncio.wait_for(
                        task.handler(*task.args, **task.kwargs),
                        timeout=task.timeout_seconds
                    )
                )
                self._execution_tasks[task.id] = exec_task

                result = await exec_task

                # Success
                task.last_result = TaskResult(
                    success=True,
                    data=result,
                    execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
                )
                task.status = TaskStatus.COMPLETED
                task.run_count += 1
                task.failure_count = 0  # Reset on success

                logger.debug(f"Task {task.name} completed successfully")

            except asyncio.TimeoutError:
                task.last_result = TaskResult(
                    success=False,
                    error=f"Task timed out after {task.timeout_seconds}s"
                )
                task.status = TaskStatus.FAILED
                task.failure_count += 1

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                raise

            except Exception as e:
                logger.error(f"Task {task.name} failed: {e}")
                task.last_result = TaskResult(success=False, error=str(e))
                task.status = TaskStatus.FAILED
                task.failure_count += 1

                # Retry logic
                if task.failure_count < task.max_retries:
                    task.next_run = datetime.utcnow() + timedelta(
                        seconds=task.retry_delay_seconds * task.failure_count
                    )
                    task.status = TaskStatus.PENDING

            finally:
                task.last_run = start_time
                if task.id in self._execution_tasks:
                    del self._execution_tasks[task.id]

                # Schedule next run if recurring
                if task.status == TaskStatus.COMPLETED and not task.run_once:
                    task.next_run = task.calculate_next_run()
                    task.status = TaskStatus.PENDING

    async def run_task_now(self, task_id: str) -> Optional[TaskResult]:
        """Immediately run a task."""
        task = self.get_task(task_id)
        if not task:
            return None

        task.next_run = datetime.utcnow()
        await self._execute_task(task)
        return task.last_result


# Global scheduler
_global_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global task scheduler."""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = TaskScheduler()
    return _global_scheduler


# Convenience decorator using global scheduler
def scheduled(
    cron: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    **kwargs
) -> Callable[[TaskHandler], TaskHandler]:
    """Schedule a task with the global scheduler."""
    return get_scheduler().schedule(cron=cron, interval_seconds=interval_seconds, **kwargs)

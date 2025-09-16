"""Celery application configuration for Agentic-AI.

This module defines the Celery app used to run background tasks such as
batch product processing. Configure broker and backend via environment vars.

Environment variables:
- CELERY_BROKER_URL (e.g., redis://redis:6379/0)
- CELERY_RESULT_BACKEND (e.g., redis://redis:6379/1)
"""

import os
from celery import Celery


def create_celery_app() -> Celery:
	broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
	result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

	app = Celery("agentic_ai", broker=broker_url, backend=result_backend)

	# Resolve tasks module name whether running from repo root or Agent dir
	# If run from repo root, tasks are "Agent.tasks"; from Agent dir, it's "tasks".
	tasks_module = "Agent.tasks" if os.path.basename(os.getcwd()) != "Agent" else "tasks"

	# Reasonable defaults; can be overridden via CELERY_* env vars
	app.conf.update(
		task_serializer="json",
		result_serializer="json",
		accept_content=["json"],
		task_time_limit=300,
		task_soft_time_limit=270,
		worker_max_tasks_per_child=100,
		# Ensure tasks module is imported by workers
		include=[tasks_module],
	)

	# Optional eager mode for local testing (runs tasks in-process)
	eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "0").lower() in {"1", "true", "yes"}
	if eager:
		app.conf.task_always_eager = True
		app.conf.task_eager_propagates = True
	return app


celery_app = create_celery_app()

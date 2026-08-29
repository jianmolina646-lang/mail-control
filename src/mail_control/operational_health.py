from __future__ import annotations

import asyncio
import os

from mail_control.infrastructure.resources import Resources
from mail_control.modules.system.health import DependencyStatus, check_dependencies
from mail_control.settings import get_settings


def is_healthy(
    dependencies: DependencyStatus,
    queue_required: bool,
    consumer_count: int,
) -> bool:
    return dependencies.ready and (not queue_required or consumer_count > 0)


async def check() -> bool:
    resources = await Resources.connect(get_settings())
    try:
        dependencies = await check_dependencies(resources)
        queue_name = os.getenv("HEALTH_QUEUE", "").strip()
        consumer_count = 0
        if queue_name:
            channel = await resources.rabbitmq.channel()
            try:
                queue = await channel.declare_queue(queue_name, passive=True)
                if queue.declaration_result is not None:
                    consumer_count = queue.declaration_result.consumer_count or 0
            finally:
                await channel.close()
        return is_healthy(dependencies, bool(queue_name), consumer_count)
    except Exception:
        return False
    finally:
        await resources.close()


def main() -> None:
    raise SystemExit(0 if asyncio.run(check()) else 1)


if __name__ == "__main__":
    main()

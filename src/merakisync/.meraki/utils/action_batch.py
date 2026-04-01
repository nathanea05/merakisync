from __future__ import annotations

from typing import Any, Iterable


MAX_ACTIONS_PER_BATCH = 100
MAX_SYNCHRONOUS_ACTIONS = 20


def create_batch_action(
    *,
    resource: str,
    operation: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a properly formatted Meraki action batch action.

    Example:
        action = create_batch_action(
            resource="/devices/Q2XX-XXXX-XXXX/switch/ports/3",
            operation="update",
            body={"enabled": True},
        )

    Returns:
        {
            "resource": "/devices/...",
            "operation": "update",
            "body": {...}
        }
    """
    if not resource or not isinstance(resource, str):
        raise ValueError("resource must be a non-empty string")

    if not operation or not isinstance(operation, str):
        raise ValueError("operation must be a non-empty string")

    action: dict[str, Any] = {
        "resource": resource,
        "operation": operation,
    }

    if body is not None:
        if not isinstance(body, dict):
            raise TypeError("body must be a dict or None")
        action["body"] = body

    return action


def send_action_batches(
    dashboard: Any,
    organization_id: str,
    actions: Iterable[dict[str, Any]],
    *,
    confirmed: bool = True,
    synchronous: bool = False,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Send Meraki action batches in chunks.

    Meraki limits:
      - asynchronous batches: up to 100 actions
      - synchronous batches: up to 20 actions

    Args:
        dashboard:
            Meraki DashboardAPI instance.
        organization_id:
            Meraki organization ID.
        actions:
            Iterable of batch action dicts.
        confirmed:
            Whether the batch should be confirmed immediately.
            Defaults to True.
        synchronous:
            Whether the batch should execute synchronously.
            Defaults to False.
        **kwargs:
            Extra keyword arguments passed directly to
            dashboard.organizations.createOrganizationActionBatch().
            Useful for callback, etc.

    Returns:
        List of API responses, one per submitted batch.
    """
    action_list = list(actions)

    if not action_list:
        return []

    batch_size = MAX_SYNCHRONOUS_ACTIONS if synchronous else MAX_ACTIONS_PER_BATCH

    if synchronous and len(action_list) > MAX_SYNCHRONOUS_ACTIONS:
        # We still support chunking, but each chunk must be <= 20.
        batch_size = MAX_SYNCHRONOUS_ACTIONS

    responses: list[dict[str, Any]] = []

    for i in range(0, len(action_list), batch_size):
        chunk = action_list[i : i + batch_size]

        if synchronous and len(chunk) > MAX_SYNCHRONOUS_ACTIONS:
            raise ValueError(
                f"Synchronous action batches cannot exceed "
                f"{MAX_SYNCHRONOUS_ACTIONS} actions"
            )

        if len(chunk) > MAX_ACTIONS_PER_BATCH:
            raise ValueError(
                f"Action batches cannot exceed {MAX_ACTIONS_PER_BATCH} actions"
            )

        response = dashboard.organizations.createOrganizationActionBatch(
            organization_id,
            actions=chunk,
            confirmed=confirmed,
            synchronous=synchronous,
            **kwargs,
        )
        responses.append(response)

    return responses

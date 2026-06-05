"""Tests for utils/action_batch: create_batch_action and send_action_batches."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from merakisync.utils.action_batch import (
    MAX_ACTIONS_PER_BATCH,
    MAX_SYNCHRONOUS_ACTIONS,
    create_batch_action,
    send_action_batches,
)


# ---------------------------------------------------------------------------
# create_batch_action
# ---------------------------------------------------------------------------

class TestCreateBatchAction:
    def test_minimal_action(self):
        action = create_batch_action(
            resource="/devices/Q2AB-1234/switch/ports/1",
            operation="update",
        )
        assert action["resource"] == "/devices/Q2AB-1234/switch/ports/1"
        assert action["operation"] == "update"
        assert "body" not in action

    def test_action_with_body(self):
        body = {"enabled": True, "vlan": 100}
        action = create_batch_action(
            resource="/devices/Q2AB-1234/switch/ports/1",
            operation="update",
            body=body,
        )
        assert action["body"] == body

    def test_body_none_not_included(self):
        action = create_batch_action(
            resource="/devices/Q2AB-1234/switch/ports/1",
            operation="update",
            body=None,
        )
        assert "body" not in action

    def test_empty_resource_raises(self):
        with pytest.raises(ValueError, match="resource"):
            create_batch_action(resource="", operation="update")

    def test_none_resource_raises(self):
        with pytest.raises(ValueError, match="resource"):
            create_batch_action(resource=None, operation="update")  # type: ignore

    def test_non_string_resource_raises(self):
        with pytest.raises(ValueError, match="resource"):
            create_batch_action(resource=123, operation="update")  # type: ignore

    def test_empty_operation_raises(self):
        with pytest.raises(ValueError, match="operation"):
            create_batch_action(resource="/devices/S1", operation="")

    def test_none_operation_raises(self):
        with pytest.raises(ValueError, match="operation"):
            create_batch_action(resource="/devices/S1", operation=None)  # type: ignore

    def test_non_dict_body_raises(self):
        with pytest.raises(TypeError, match="body must be a dict"):
            create_batch_action(resource="/devices/S1", operation="update", body=["not", "a", "dict"])  # type: ignore

    def test_returned_dict_has_correct_keys(self):
        action = create_batch_action(resource="/x", operation="update", body={"k": "v"})
        assert set(action.keys()) == {"resource", "operation", "body"}


# ---------------------------------------------------------------------------
# send_action_batches
# ---------------------------------------------------------------------------

class TestSendActionBatches:
    def _make_dashboard(self):
        dash = MagicMock()
        dash.organizations.createOrganizationActionBatch.return_value = {"id": "batch1"}
        return dash

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_empty_actions_returns_empty_list(self, mock_sleep):
        dash = self._make_dashboard()
        result = send_action_batches(dash, "org1", [])
        assert result == []
        dash.organizations.createOrganizationActionBatch.assert_not_called()

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_single_batch_sent(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource="/x", operation="update") for _ in range(5)]
        result = send_action_batches(dash, "org1", actions)
        assert len(result) == 1
        dash.organizations.createOrganizationActionBatch.assert_called_once()

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_large_batch_split_into_chunks(self, mock_sleep):
        dash = self._make_dashboard()
        # 150 actions → 2 chunks of 100 and 50
        actions = [create_batch_action(resource=f"/x/{i}", operation="update") for i in range(150)]
        result = send_action_batches(dash, "org1", actions)
        assert len(result) == 2
        assert dash.organizations.createOrganizationActionBatch.call_count == 2

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_synchronous_uses_smaller_chunk_size(self, mock_sleep):
        dash = self._make_dashboard()
        # 25 actions with synchronous=True → 2 chunks of 20 and 5
        actions = [create_batch_action(resource=f"/x/{i}", operation="update") for i in range(25)]
        result = send_action_batches(dash, "org1", actions, synchronous=True)
        assert len(result) == 2

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_confirmed_passed_to_api(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource="/x", operation="update")]
        send_action_batches(dash, "org1", actions, confirmed=True)
        call_kwargs = dash.organizations.createOrganizationActionBatch.call_args.kwargs
        assert call_kwargs["confirmed"] is True

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_synchronous_passed_to_api(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource="/x", operation="update")]
        send_action_batches(dash, "org1", actions, synchronous=True)
        call_kwargs = dash.organizations.createOrganizationActionBatch.call_args.kwargs
        assert call_kwargs["synchronous"] is True

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_sleep_called_between_batches(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource=f"/x/{i}", operation="update") for i in range(5)]
        send_action_batches(dash, "org1", actions)
        mock_sleep.assert_called()

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_org_id_passed_to_api(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource="/x", operation="update")]
        send_action_batches(dash, "org_xyz", actions)
        call_args = dash.organizations.createOrganizationActionBatch.call_args
        assert call_args.args[0] == "org_xyz"

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_actions_chunked_correctly(self, mock_sleep):
        dash = self._make_dashboard()
        actions = [create_batch_action(resource=f"/x/{i}", operation="update") for i in range(3)]
        send_action_batches(dash, "org1", actions)
        call_args = dash.organizations.createOrganizationActionBatch.call_args
        assert len(call_args.kwargs["actions"]) == 3

    @patch("merakisync.utils.action_batch.time.sleep")
    def test_responses_collected(self, mock_sleep):
        dash = self._make_dashboard()
        dash.organizations.createOrganizationActionBatch.return_value = {"id": "batch_resp"}
        actions = [create_batch_action(resource="/x", operation="update")]
        result = send_action_batches(dash, "org1", actions)
        assert result == [{"id": "batch_resp"}]

from __future__ import annotations

from kynara_sdk.types import Decision


class KynaraError(Exception):
    pass


class KynaraUnavailable(KynaraError):
    """Control plane couldn't be reached and the configured failure mode is fail-closed."""


class PermissionDenied(KynaraError):
    """An agent tried to perform an action the policy engine refused.

    Attributes:
        decision: The full ``Decision`` object from the control plane, including
                  ``reason``, ``matched_policy_id``, and any obligations.
    """

    def __init__(self, decision: Decision, action: str, subject_id: str):
        self.decision = decision
        self.action = action
        self.subject_id = subject_id
        super().__init__(
            f"permission denied for {action} by {subject_id}: {decision.reason} "
            f"(matched_policy_id={decision.matched_policy_id})"
        )


class ApprovalRequired(KynaraError):
    """Policy demands an out-of-band approval before the action proceeds.

    SDK consumers usually pause the tool call, emit an approval request to the user or
    an approval channel (Slack / PagerDuty), then re-invoke the tool with an
    ``approval_token`` context field.
    """

    def __init__(self, decision: Decision, action: str):
        self.decision = decision
        self.action = action
        super().__init__(f"approval required for {action}: {decision.reason}")

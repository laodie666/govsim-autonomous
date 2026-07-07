"""Channel / messaging group management for GovSim Autonomous.

Each agent is in EXACTLY ONE group at a time:
  - "public" (default, everyone starts here)
  - or a private channel (#channel_0, #channel_1, ...)

Joining a private channel = leaving your current group.
Leaving a private channel = returning to "public".
Talk always goes to your current group — no channel name needed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Invitation:
    channel_name: str
    from_agent: str
    to_agent: str
    message: str = ""


class ChannelManager:
    """Manages channel membership, invitations, and message routing.

    Single-group model: every agent belongs to exactly one channel at a time.
    """

    def __init__(self, agent_ids: list[str]) -> None:
        self._channels: dict[str, set[str]] = {}
        self._public_channels: set[str] = set()
        self._next_channel_id: int = 0
        self._invitations: list[Invitation] = []
        # Track which creator has a pending channel with outstanding invites
        self._creator_pending: dict[str, str] = {}  # creator_id -> channel_name
        # Track each agent's current channel (single-group model)
        self._agent_channel: dict[str, str] = {}

        # Create the default public channel — all agents start here
        self._channels["public"] = set(agent_ids)
        self._public_channels.add("public")
        self._next_channel_id = 0
        for aid in agent_ids:
            self._agent_channel[aid] = "public"

    # ── Current channel ──────────────────────────────────────────────

    def agent_channel(self, agent_id: str) -> str:
        """Return the channel this agent is currently in."""
        return self._agent_channel.get(agent_id, "public")

    # ── Channel queries ──────────────────────────────────────────────

    def is_member(self, channel_name: str, agent_id: str) -> bool:
        """Check if agent is a member of the named channel (single-group)."""
        if channel_name not in self._channels:
            return False
        return self._agent_channel.get(agent_id) == channel_name

    def heard_by(self, channel_name: str) -> set[str]:
        """Return the set of agents who hear messages in this channel."""
        if channel_name not in self._channels:
            return set()
        return {
            aid for aid, ch in self._agent_channel.items()
            if ch == channel_name
        }

    def get_channels(self, agent_id: str) -> list[dict]:
        """Return the agent's current channel with metadata."""
        ch = self._agent_channel.get(agent_id)
        if ch is None or ch not in self._channels:
            return []
        members = {
            aid for aid, c in self._agent_channel.items()
            if c == ch
        }
        return [{
            "name": ch,
            "members": sorted(members),
            "is_public": ch in self._public_channels,
        }]

    def get_pending_invitations(self, agent_id: str) -> list[Invitation]:
        """Return all pending invitations for this agent."""
        return [inv for inv in self._invitations if inv.to_agent == agent_id]

    def get_pending_creator(self, agent_id: str) -> str | None:
        """Return the channel name this agent has pending as creator, or None."""
        return self._creator_pending.get(agent_id)

    def _generate_channel_name(self) -> str:
        """Generate a unique auto-incrementing channel name."""
        name = f"channel_{self._next_channel_id}"
        self._next_channel_id += 1
        return name

    # ── Channel creation ─────────────────────────────────────────────

    def create_private_channel(self, creator: str, members: list[str], message: str = "") -> str:
        """Create a new private channel.

        The creator moves FROM their current channel TO the new channel.
        Invited members receive invitations (they stay in their current
        channel until they accept).

        Returns the auto-generated channel name.
        """
        # Cancel any existing pending creation for this creator
        self._cancel_pending_creator(creator)

        name = self._generate_channel_name()

        # Move creator to the new channel (single-group: leaves old channel)
        old_channel = self._agent_channel.get(creator, "public")
        if old_channel in self._channels and old_channel not in self._public_channels:
            self._channels[old_channel].discard(creator)
            self._cleanup_if_empty(old_channel)

        self._channels[name] = {creator}
        self._agent_channel[creator] = name

        # Filter out self from targets
        actual_targets = [m for m in members if m != creator]

        for m in actual_targets:
            self._invitations.append(Invitation(
                channel_name=name,
                from_agent=creator,
                to_agent=m,
                message=message,
            ))

        # Only track as pending if there are actual invitees
        if actual_targets:
            self._creator_pending[creator] = name

        return name

    # ── Pending creator management ──────────────────────────────────

    def _cancel_pending_creator(self, agent_id: str) -> None:
        """Cancel pending channel creation for this agent.
        Removes invites and cleans up the pending channel if empty.
        Does NOT move the agent — they stay in their current channel.
        """
        channel_name = self._creator_pending.pop(agent_id, None)
        if channel_name is None:
            return
        # Remove any pending invites the creator sent for this channel
        self._invitations = [
            inv for inv in self._invitations
            if not (inv.from_agent == agent_id and inv.channel_name == channel_name)
        ]
        # If channel still exists and only the creator is there, clean up
        if channel_name in self._channels:
            current_members = {
                aid for aid, ch in self._agent_channel.items()
                if ch == channel_name
            }
            if not current_members:
                del self._channels[channel_name]

    def _refresh_creator_pending(self, channel_name: str) -> None:
        """Check if the creator of a channel still has pending invites."""
        creator = next(
            (cid for cid, ch in self._creator_pending.items() if ch == channel_name),
            None,
        )
        if creator is None:
            return
        remaining = [
            inv for inv in self._invitations
            if inv.channel_name == channel_name
        ]
        if not remaining:
            del self._creator_pending[creator]

    # ── Invitations ──────────────────────────────────────────────────

    def accept_invite(self, agent_id: str, channel_name: str) -> None:
        """Accept an invitation and join the channel.

        The agent moves FROM their current channel TO the invited channel.
        """
        if channel_name not in self._channels:
            raise ValueError(f"channel '{channel_name}' not found")
        # Already a member — no-op
        if self._agent_channel.get(agent_id) == channel_name:
            return
        pending = [inv for inv in self._invitations
                   if inv.to_agent == agent_id and inv.channel_name == channel_name]
        if not pending:
            raise ValueError(f"no invitation for {agent_id} to '{channel_name}'")

        # Accepting an invite clears the accepter's own pending creation
        self._cancel_pending_creator(agent_id)

        self._invitations = [inv for inv in self._invitations if inv not in pending]

        # Move agent from old channel to new channel
        old_channel = self._agent_channel.get(agent_id, "public")
        if old_channel in self._channels and old_channel not in self._public_channels:
            self._channels[old_channel].discard(agent_id)
            self._cleanup_if_empty(old_channel)

        self._agent_channel[agent_id] = channel_name
        self._channels[channel_name].add(agent_id)

        # Check if the creator's pending should be cleared
        self._refresh_creator_pending(channel_name)

    def reject_invite(self, agent_id: str, channel_name: str) -> None:
        """Reject an invitation without joining."""
        if channel_name not in self._channels:
            raise ValueError(f"channel '{channel_name}' not found")
        self._invitations = [
            inv for inv in self._invitations
            if not (inv.to_agent == agent_id and inv.channel_name == channel_name)
        ]
        self._refresh_creator_pending(channel_name)

    def abandon_invitation(self, agent_id: str, channel_name: str) -> None:
        """Creator abandons their own pending invitation."""
        if self._creator_pending.get(agent_id) == channel_name:
            self._cancel_pending_creator(agent_id)

    # ── Membership management ────────────────────────────────────────

    def leave(self, agent_id: str, channel_name: str) -> None:
        """Leave a private channel. Agent returns to 'public'."""
        if channel_name not in self._channels:
            raise ValueError(f"channel '{channel_name}' not found")
        if channel_name in self._public_channels:
            raise ValueError("cannot leave public channel")
        if self._agent_channel.get(agent_id) != channel_name:
            raise ValueError(f"agent {agent_id} is not in channel '{channel_name}'")

        # Move agent back to public
        self._agent_channel[agent_id] = "public"

        # Clean up empty private channels
        self._cleanup_if_empty(channel_name)

        # If the agent was the creator with a pending channel, clear it
        if self._creator_pending.get(agent_id) == channel_name:
            del self._creator_pending[agent_id]

    # ── Dissolution ──────────────────────────────────────────────────

    def dissolve_all(self) -> None:
        """Move all agents back to 'public' and delete all private channels.

        Called between phases to reset the channel landscape.
        """
        # Move all agents to public
        for agent_id in list(self._agent_channel.keys()):
            self._agent_channel[agent_id] = "public"

        # Delete all private channels
        private_channels = [name for name in list(self._channels.keys())
                           if name not in self._public_channels]
        for name in private_channels:
            del self._channels[name]

        # Clear all invitations
        self._invitations.clear()
        self._creator_pending.clear()

    def _cleanup_if_empty(self, channel_name: str) -> None:
        """Remove a private channel if no agents are in it."""
        if channel_name in self._public_channels:
            return
        current_members = {
            aid for aid, ch in self._agent_channel.items()
            if ch == channel_name
        }
        if not current_members and channel_name in self._channels:
            del self._channels[channel_name]
            # Also remove any pending invitations to this channel
            self._invitations = [
                inv for inv in self._invitations
                if inv.channel_name != channel_name
            ]

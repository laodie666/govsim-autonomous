"""Tests for the channel/messaging group system."""

from __future__ import annotations

import pytest
from simulation.channels import ChannelManager, Invitation


# ── ChannelManager creation ──────────────────────────────────────────

def test_public_channel_exists():
    """All agents are in #public at startup."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    assert mgr.is_member("public", "alice")
    assert mgr.is_member("public", "bob")
    assert mgr.is_member("public", "charlie")


def test_public_heard_by_all():
    """Messages in #public are heard by all agents."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    assert mgr.heard_by("public") == {"alice", "bob", "charlie"}


def test_get_channels_returns_public():
    """get_channels includes #public for all agents."""
    mgr = ChannelManager(["alice", "bob"])
    alice_channels = mgr.get_channels("alice")
    assert any(c["name"] == "public" for c in alice_channels)


# ── Private channel creation ─────────────────────────────────────────

def test_create_private_channel_auto_name():
    """Channel names are auto-generated and distinct."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    name2 = mgr.create_private_channel("charlie", ["alice"])
    assert name1 != name2
    assert name1.startswith("channel_")
    assert name2.startswith("channel_")


def test_create_private_channel_creator_is_member():
    """Creator is automatically a member of their new channel."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    assert mgr.is_member(name, "alice")


def test_create_private_channel_others_not_auto_member():
    """Other listed agents are NOT auto-joined — they get an invitation."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    assert not mgr.is_member(name, "bob")  # must accept first


def test_create_private_channel_creates_invitations():
    """Invitations are created for listed members (excluding creator)."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob", "charlie"])
    invs = mgr.get_pending_invitations("bob")
    assert any(i.channel_name == name and i.from_agent == "alice" for i in invs)
    invs_c = mgr.get_pending_invitations("charlie")
    assert any(i.channel_name == name and i.from_agent == "alice" for i in invs_c)


def test_create_private_adds_to_creator_channels():
    """New channel appears in creator's channel list."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    channels = mgr.get_channels("alice")
    assert any(c["name"] == name for c in channels)


# ── Accepting invitations ────────────────────────────────────────────

def test_accept_invite_joins_channel():
    """Accepting an invitation adds agent to channel members."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    assert mgr.is_member(name, "bob")


def test_accept_invite_marks_invitation():
    """Accepting removes pending invitation."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    assert mgr.get_pending_invitations("bob") == []


def test_accept_invite_non_existent_raises():
    """Accepting invitation to non-existent channel raises."""
    mgr = ChannelManager(["alice", "bob"])
    with pytest.raises(ValueError, match="not found"):
        mgr.accept_invite("bob", "nonexistent")


def test_accept_invite_no_invitation_raises():
    """Accepting without a pending invitation raises."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob"])
    with pytest.raises(ValueError, match="no invitation"):
        mgr.accept_invite("charlie", name)


# ── Rejecting invitations ────────────────────────────────────────────

def test_reject_invite_does_not_join():
    """Rejecting does not add agent to channel."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.reject_invite("bob", name)
    assert not mgr.is_member(name, "bob")


def test_reject_invite_removes_pending():
    """Rejecting removes the pending invitation."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.reject_invite("bob", name)
    assert mgr.get_pending_invitations("bob") == []


# ── Leaving channels ─────────────────────────────────────────────────

def test_leave_channel():
    """Leaving removes agent from channel members."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    mgr.leave("bob", name)
    assert not mgr.is_member(name, "bob")


def test_leave_private_cleans_up_empty():
    """When last member leaves a private channel, it's removed."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.leave("alice", name)
    # Channel should be gone
    assert not mgr.is_member("alice", name)  # alice left
    assert name not in [c["name"] for c in mgr.get_channels("alice")]
    # bob's invitation should also be gone
    assert mgr.get_pending_invitations("bob") == []


def test_leave_public_not_allowed():
    """Agents cannot leave #public."""
    mgr = ChannelManager(["alice", "bob"])
    with pytest.raises(ValueError, match="cannot leave public"):
        mgr.leave("alice", "public")


def test_leave_nonexistent_raises():
    """Leaving non-existent channel raises."""
    mgr = ChannelManager(["alice"])
    with pytest.raises(ValueError, match="not found"):
        mgr.leave("alice", "nonexistent")


# ── Private channel heard_by ─────────────────────────────────────────

def test_private_heard_by_members_only():
    """Only channel members hear private channel messages."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    heard = mgr.heard_by(name)
    assert "alice" in heard
    assert "bob" in heard
    assert "charlie" not in heard  # not invited/accepted
    assert len(heard) == 2


def test_heard_by_public_returns_all():
    """#public heard_by returns all agents."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    assert mgr.heard_by("public") == {"alice", "bob", "charlie"}


# ── Edge cases ───────────────────────────────────────────────────────

def test_create_private_with_no_members():
    """Creating a channel with no additional members still creates it (creator only)."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", [])
    assert mgr.is_member(name, "alice")
    assert not mgr.is_member(name, "bob")


def test_get_channels_excludes_cleaned_up():
    """After cleanup, the channel doesn't appear in any agent's list."""
    mgr = ChannelManager(["alice"])
    name = mgr.create_private_channel("alice", [])
    mgr.leave("alice", name)
    assert all(c["name"] != name for c in mgr.get_channels("alice"))


def test_join_invited_channel_twice_noop():
    """Joining an already-joined channel is a no-op."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    mgr.accept_invite("bob", name)  # second join should not raise
    assert mgr.is_member(name, "bob")


def test_channel_info_includes_members():
    """get_channels returns member list for each channel."""
    mgr = ChannelManager(["alice", "bob"])
    alice_channels = mgr.get_channels("alice")
    pub = [c for c in alice_channels if c["name"] == "public"][0]
    assert "alice" in pub["members"]
    assert "bob" in pub["members"]


def test_get_pending_no_invitations():
    """Agent with no invitations gets empty list."""
    mgr = ChannelManager(["alice", "bob"])
    assert mgr.get_pending_invitations("alice") == []


# ── One-pending-creation constraint ──────────────────────────────────

def test_creator_no_pending_by_default():
    """Agent has no pending created channel by default."""
    mgr = ChannelManager(["alice", "bob"])
    assert mgr.get_pending_creator("alice") is None


def test_creator_pending_after_create():
    """After creating a group with invitees, creator has a pending."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    assert mgr.get_pending_creator("alice") == name


def test_creator_no_pending_with_no_targets():
    """Creating a group with NO invitees does NOT set pending (no invites sent)."""
    mgr = ChannelManager(["alice", "bob"])
    mgr.create_private_channel("alice", [])
    assert mgr.get_pending_creator("alice") is None


def test_create_again_cancels_old_pending():
    """Creating a second group cancels the first group's invites and replaces pending."""
    mgr = ChannelManager(["alice", "bob"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    assert mgr.get_pending_creator("alice") == name1
    # Bob had an invite for name1
    assert len(mgr.get_pending_invitations("bob")) == 1

    name2 = mgr.create_private_channel("alice", ["bob"])
    assert mgr.get_pending_creator("alice") == name2
    assert name2 != name1
    # Bob's invite for name1 should be gone
    with pytest.raises(ValueError):
        mgr.accept_invite("bob", name1)
    # Bob should have invite for name2
    assert any(i.channel_name == name2 for i in mgr.get_pending_invitations("bob"))


def test_old_channel_cleaned_if_empty_on_replace():
    """When replacing a pending channel, if no one joined the old one, it's cleaned up."""
    mgr = ChannelManager(["alice", "bob"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    name2 = mgr.create_private_channel("alice", ["bob"])
    # name1 should be gone — channel no longer exists
    assert not mgr.is_member("alice", name1)
    assert name1 not in [c["name"] for c in mgr.get_channels("alice")]


def test_accept_invite_clears_own_pending():
    """Agent who accepts someone else's invite has their own pending creation cleared."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    # Alice creates a group (has pending)
    alice_channel = mgr.create_private_channel("alice", ["bob"])
    assert mgr.get_pending_creator("alice") == alice_channel
    # Charlie creates a group and invites Alice
    charlie_channel = mgr.create_private_channel("charlie", ["alice"])
    # Alice accepts Charlie's invite
    mgr.accept_invite("alice", charlie_channel)
    # Alice's pending should be cleared
    assert mgr.get_pending_creator("alice") is None
    # Alice's old channel should be cleaned up (Bob hadn't accepted)
    assert not mgr.is_member("alice", alice_channel)


def test_accept_invite_old_channel_kept_if_others_joined():
    """Accepting an invite clears pending, but if someone already joined the old channel, it stays."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    # Alice creates a group
    alice_ch = mgr.create_private_channel("alice", ["bob", "charlie"])
    # Bob accepts Alice's invite
    mgr.accept_invite("bob", alice_ch)
    assert mgr.is_member(alice_ch, "bob")
    # Now Alice accepts an invite from Charlie
    charlie_ch = mgr.create_private_channel("charlie", ["alice"])
    mgr.accept_invite("alice", charlie_ch)
    # Alice's pending cleared
    assert mgr.get_pending_creator("alice") is None
    # But Bob is still in alice_ch (it was not empty)
    assert mgr.is_member(alice_ch, "bob")
    # Alice is no longer in alice_ch
    assert not mgr.is_member(alice_ch, "alice")


def test_multiple_agents_independent_pending():
    """Each agent can have their own pending, independent of others."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    name2 = mgr.create_private_channel("bob", ["charlie"])
    name3 = mgr.create_private_channel("charlie", ["alice"])
    assert mgr.get_pending_creator("alice") == name1
    assert mgr.get_pending_creator("bob") == name2
    assert mgr.get_pending_creator("charlie") == name3


def test_all_invitees_accept_clears_creator_pending():
    """When all pending invites for a creator's channel are accepted, pending is cleared."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob", "charlie"])
    assert mgr.get_pending_creator("alice") == name
    # Bob accepts
    mgr.accept_invite("bob", name)
    # Still pending (Charlie hasn't responded)
    assert mgr.get_pending_creator("alice") == name
    # Charlie accepts
    mgr.accept_invite("charlie", name)
    # All resolved — pending cleared
    assert mgr.get_pending_creator("alice") is None


def test_all_invitees_reject_clears_creator_pending():
    """When all pending invites are rejected, pending is cleared."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob", "charlie"])
    assert mgr.get_pending_creator("alice") == name
    mgr.reject_invite("bob", name)
    assert mgr.get_pending_creator("alice") == name  # still pending
    mgr.reject_invite("charlie", name)
    assert mgr.get_pending_creator("alice") is None  # all rejected


def test_creator_leave_clears_pending():
    """When creator leaves their own channel, pending is cleared."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    assert mgr.get_pending_creator("alice") == name
    mgr.leave("alice", name)
    assert mgr.get_pending_creator("alice") is None


# ── Channel dissolution ──────────────────────────────────────────────

def test_dissolve_all_moves_all_to_public():
    """After dissolve_all, every agent is in 'public'."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    # Create 2 private channels
    ch1 = mgr.create_private_channel("alice", ["bob"])
    ch2 = mgr.create_private_channel("charlie", ["alice"])
    mgr.accept_invite("bob", ch1)
    # alice created ch1 (channel_0) and is still there
    # bob accepted invite to ch1 (channel_0)
    # charlie created ch2 (channel_1)
    assert mgr.agent_channel("alice") == ch1
    assert mgr.agent_channel("bob") == ch1
    assert mgr.agent_channel("charlie") == ch2
    assert mgr.agent_channel("alice") != "public"
    assert mgr.agent_channel("bob") != "public"
    assert mgr.agent_channel("charlie") != "public"
    # Dissolve all
    mgr.dissolve_all()
    assert mgr.agent_channel("alice") == "public"
    assert mgr.agent_channel("bob") == "public"
    assert mgr.agent_channel("charlie") == "public"
    # Private channels should be gone
    assert ch1 not in mgr._channels
    assert ch2 not in mgr._channels
    # Invitations cleared
    assert mgr._invitations == []


def test_dissolve_all_keeps_public():
    """dissolve_all preserves the public channel."""
    mgr = ChannelManager(["alice"])
    mgr.dissolve_all()
    assert "public" in mgr._channels


def test_dissolve_all_when_all_already_public():
    """Calling dissolve_all when all agents already in public is safe."""
    mgr = ChannelManager(["alice", "bob"])
    mgr.dissolve_all()  # already all in public
    assert mgr.agent_channel("alice") == "public"
    assert mgr.agent_channel("bob") == "public"
    assert mgr._invitations == []


def test_reject_invite_non_existent_channel_raises():
    """Rejecting invite to a channel that doesn't exist raises ValueError."""
    mgr = ChannelManager(["alice", "bob"])
    with pytest.raises(ValueError, match="not found"):
        mgr.reject_invite("bob", "nonexistent_channel")


def test_reject_invite_no_invitation_is_silent():
    """Rejecting invite when no invitation exists is a silent no-op (no raise)."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name = mgr.create_private_channel("alice", ["bob"])
    # Charlie was never invited — should be a no-op, not raise
    mgr.reject_invite("charlie", name)  # Does not raise


def test_leave_channel_not_member_raises():
    """Leaving a channel you're not a member of raises ValueError."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    # Bob hasn't accepted yet, so he's not a member
    with pytest.raises(ValueError, match="not in channel"):
        mgr.leave("bob", name)


def test_heard_by_non_existent_channel_returns_empty():
    """Asking heard_by for a non-existent channel returns empty set (doesn't raise)."""
    mgr = ChannelManager(["alice"])
    result = mgr.heard_by("nonexistent")
    assert result == set(), "heard_by on non-existent channel should return empty set"


def test_multiple_pending_invitations_independent():
    """An agent can be invited to multiple channels simultaneously."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    name2 = mgr.create_private_channel("charlie", ["bob"])
    pending = mgr.get_pending_invitations("bob")
    assert len(pending) == 2
    assert any(i.channel_name == name1 for i in pending)
    assert any(i.channel_name == name2 for i in pending)


def test_accept_one_invite_leaves_other_pending():
    """Accepting one invite doesn't affect other pending invitations."""
    mgr = ChannelManager(["alice", "bob", "charlie"])
    name1 = mgr.create_private_channel("alice", ["bob"])
    name2 = mgr.create_private_channel("charlie", ["bob"])
    mgr.accept_invite("bob", name1)
    assert mgr.is_member(name1, "bob")
    pending = mgr.get_pending_invitations("bob")
    assert len(pending) == 1
    assert pending[0].channel_name == name2


def test_agent_channel_for_private_returns_name():
    """agent_channel returns the channel name for private channels."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    assert mgr.agent_channel("alice") == name
    assert mgr.agent_channel("bob") == "public"  # hasn't joined yet
    mgr.accept_invite("bob", name)
    assert mgr.agent_channel("bob") == name


def test_leave_channel_returns_to_public():
    """After leaving a private channel, agent's channel is 'public'."""
    mgr = ChannelManager(["alice", "bob"])
    name = mgr.create_private_channel("alice", ["bob"])
    mgr.accept_invite("bob", name)
    mgr.leave("bob", name)
    assert mgr.agent_channel("bob") == "public"

"""Tests for NapcatType.get_specific_type."""

from bilipy_bot.sources.napcat.types import NapcatType


class TestGetSpecificType:
    """get_specific_type 从消息字典路由到最具体类型."""

    # ── meta_event ──

    def test_lifecycle_meta(self):
        msg = {"post_type": "meta_event", "meta_event_type": "lifecycle"}
        assert NapcatType.get_specific_type(msg) == NapcatType.LIFECYCLE_META

    def test_heartbeat_meta(self):
        msg = {"post_type": "meta_event", "meta_event_type": "heartbeat"}
        assert NapcatType.get_specific_type(msg) == NapcatType.HEARTBEAT_META

    def test_meta_fallback(self):
        msg = {"post_type": "meta_event", "meta_event_type": "unknown"}
        assert NapcatType.get_specific_type(msg) == NapcatType.META

    # ── message ──

    def test_group_message(self):
        msg = {"post_type": "message", "message_type": "group"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_MESSAGE

    def test_private_message(self):
        msg = {"post_type": "message", "message_type": "private"}
        assert NapcatType.get_specific_type(msg) == NapcatType.PRIVATE_MESSAGE

    def test_message_fallback(self):
        msg = {"post_type": "message", "message_type": "unknown"}
        assert NapcatType.get_specific_type(msg) == NapcatType.MESSAGE

    # ── message_sent ──

    def test_group_sent(self):
        msg = {"post_type": "message_sent", "message_type": "group"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_SENT

    def test_private_sent(self):
        msg = {"post_type": "message_sent", "message_type": "private"}
        assert NapcatType.get_specific_type(msg) == NapcatType.PRIVATE_SENT

    def test_sent_fallback(self):
        msg = {"post_type": "message_sent", "message_type": "unknown"}
        assert NapcatType.get_specific_type(msg) == NapcatType.SENT

    # ── request ──

    def test_friend_request(self):
        msg = {"post_type": "request", "request_type": "friend"}
        assert NapcatType.get_specific_type(msg) == NapcatType.FRIEND_REQUEST

    def test_group_request(self):
        msg = {"post_type": "request", "request_type": "group"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_REQUEST

    def test_request_fallback(self):
        msg = {"post_type": "request", "request_type": "unknown"}
        assert NapcatType.get_specific_type(msg) == NapcatType.REQUEST

    # ── notice ──

    def test_group_upload_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_upload"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_UPLOAD_NOTICE

    def test_group_admin_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_admin"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_ADMIN_NOTICE

    def test_group_decrease_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_decrease"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_DECREASE_NOTICE

    def test_group_increase_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_increase"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_INCREASE_NOTICE

    def test_group_ban_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_ban"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_BAN_NOTICE

    def test_friend_add_notice(self):
        msg = {"post_type": "notice", "notice_type": "friend_add"}
        assert NapcatType.get_specific_type(msg) == NapcatType.FRIEND_ADD_NOTICE

    def test_group_recall_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_recall"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_RECALL_NOTICE

    def test_friend_recall_notice(self):
        msg = {"post_type": "notice", "notice_type": "friend_recall"}
        assert NapcatType.get_specific_type(msg) == NapcatType.FRIEND_RECALL_NOTICE

    def test_group_emoji_like_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_msg_emoji_like"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_EMOJI_LIKE_NOTICE

    def test_reaction_notice(self):
        msg = {"post_type": "notice", "notice_type": "reaction"}
        assert NapcatType.get_specific_type(msg) == NapcatType.REACTION_NOTICE

    def test_group_essence_notice(self):
        msg = {"post_type": "notice", "notice_type": "essence"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_ESSENCE_NOTICE

    def test_group_card_notice(self):
        msg = {"post_type": "notice", "notice_type": "group_card"}
        assert NapcatType.get_specific_type(msg) == NapcatType.GROUP_CARD_NOTICE

    # ── notice / notify 三级分发 ──

    def test_poke_notify(self):
        msg = {"post_type": "notice", "notice_type": "notify", "sub_type": "poke"}
        assert NapcatType.get_specific_type(msg) == NapcatType.POKE_NOTIFY

    def test_lucky_king_notify(self):
        msg = {
            "post_type": "notice",
            "notice_type": "notify",
            "sub_type": "lucky_king",
        }
        assert NapcatType.get_specific_type(msg) == NapcatType.LUCKY_KING_NOTIFY

    def test_honor_notify(self):
        msg = {"post_type": "notice", "notice_type": "notify", "sub_type": "honor"}
        assert NapcatType.get_specific_type(msg) == NapcatType.HONOR_NOTIFY

    def test_notify_unknown_subtype_fallback(self):
        msg = {
            "post_type": "notice",
            "notice_type": "notify",
            "sub_type": "unknown_sub",
        }
        assert NapcatType.get_specific_type(msg) == NapcatType.NOTICE

    # ── 边界情况 ──

    def test_unknown_post_type(self):
        msg = {"post_type": "something_weird"}
        assert NapcatType.get_specific_type(msg) == NapcatType.UNKNOWN

    def test_empty_dict(self):
        assert NapcatType.get_specific_type({}) == NapcatType.UNKNOWN

"""Tests for DataPair utility."""

from bilipy_bot.utils import DataPair


class TestDataPair:
    """Test DataPair update and copy semantics."""

    def test_update_on_empty_pair(self):
        """首次 update 应同时设置 old 和 new 为同一值."""
        pair = DataPair()
        data = {"id": 1, "value": "a"}
        pair.update(data)
        assert pair.old == data
        assert pair.new == data
        # 同一对象（首次直接赋值）
        assert pair.old is pair.new

    def test_update_on_nonempty_pair(self):
        """第二次 update 应将 old 更新为上次的 new，new 设为新值."""
        pair = DataPair()
        pair.update({"id": 1, "value": "a"})
        second = {"id": 2, "value": "b"}
        pair.update(second)

        # old 现在等于第一次的 new
        assert pair.old == {"id": 1, "value": "a"}
        # new 等于第二次传入的值
        assert pair.new == second
        # old 和 new 是不同对象
        assert pair.old is not pair.new

    def test_get_data_old_returns_copy(self):
        """get_data('old') 返回浅拷贝，而非内部对象."""
        pair = DataPair()
        inner = [1, 2, 3]
        pair.update(inner)
        pair.update([4, 5, 6])

        got = pair.get_data("old")
        # 值相等
        assert got == inner
        # 但 id 不同（浅拷贝）
        assert got is not pair.old

    def test_get_data_new_returns_copy(self):
        """get_data('new') 返回浅拷贝."""
        pair = DataPair()
        inner = [1, 2, 3]
        pair.update(inner)

        got = pair.get_data("new")
        assert got == inner
        assert got is not pair.new

    def test_get_data_invalid_key_raises(self):
        """get_data 传入无效 key 应抛出 AttributeError."""
        pair = DataPair()
        pair.update("data")
        import pytest

        with pytest.raises(AttributeError):
            pair.get_data("invalid")  # type: ignore  # pyright: intentional error test

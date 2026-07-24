import unittest
from unittest.mock import Mock, patch

from app.core import login_limiter


class LoginLimiterTests(unittest.TestCase):
    def test_first_failure_starts_expiration_window(self):
        redis = Mock()
        redis.incr.return_value = 1

        with patch.object(login_limiter, "_redis", redis):
            attempts = login_limiter.register_failure(
                "203.0.113.10",
                "admin@example.com",
            )

        self.assertEqual(attempts, 1)
        redis.expire.assert_called_once()
        redis.pipeline.assert_not_called()

    def test_fifth_failure_blocks_login(self):
        redis = Mock()
        redis.incr.return_value = 5
        pipeline = redis.pipeline.return_value

        with patch.object(login_limiter, "_redis", redis):
            attempts = login_limiter.register_failure(
                "203.0.113.10",
                "admin@example.com",
            )

        self.assertEqual(attempts, 5)
        pipeline.setex.assert_called_once()
        pipeline.delete.assert_called_once()
        pipeline.execute.assert_called_once()

    def test_success_clears_failures_and_block(self):
        redis = Mock()

        with patch.object(login_limiter, "_redis", redis):
            login_limiter.clear_failures(
                "203.0.113.10",
                "admin@example.com",
            )

        redis.delete.assert_called_once()
        self.assertEqual(len(redis.delete.call_args.args), 2)


if __name__ == "__main__":
    unittest.main()

import pytest

from app.auth.passwords import hash_password, verify_password

pytestmark = pytest.mark.xfail(strict=True, reason="step 1.2: not implemented")


def test_hash_is_argon2id() -> None:
    password_hash = hash_password("correct horse battery")

    assert password_hash.startswith("$argon2id$"), password_hash
    assert "correct horse battery" not in password_hash
    assert verify_password(password_hash, "correct horse battery")
    assert not verify_password(password_hash, "correct horse battery!")
    # A random salt per hash: the same password never gives the same string.
    assert hash_password("correct horse battery") != password_hash


def test_verify_never_raises_on_a_broken_hash() -> None:
    assert not verify_password("not-a-hash", "whatever1")
    assert not verify_password("", "whatever1")

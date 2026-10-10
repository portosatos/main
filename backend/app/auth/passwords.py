"""Password hashing with argon2id (SPEC F1, §4)."""


def hash_password(password: str) -> str:
    raise NotImplementedError("step 1.2")


def verify_password(password_hash: str, password: str) -> bool:
    raise NotImplementedError("step 1.2")

from legal_skill_guard.utils.hashing import canonical_json_sha256


def test_canonical_json_hash_is_key_order_invariant() -> None:
    assert canonical_json_sha256({"a": 1, "b": 2}) == canonical_json_sha256({"b": 2, "a": 1})

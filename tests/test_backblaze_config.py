from tradix.storage.backblaze import BackblazeConfig


BASE_ENV = {
    "B2_ENDPOINT": "https://s3.us-east-005.backblazeb2.com",
    "B2_REGION": "us-east-005",
    "B2_BUCKET_NAME": "tradix-factory-storage",
    "B2_APPLICATION_KEY_ID": "test-key-id",
    "B2_APPLICATION_KEY": "test-secret",
}


def test_config_loads_without_exposing_credentials() -> None:
    config = BackblazeConfig.from_env(BASE_ENV)
    assert config.bucket_name == "tradix-factory-storage"
    assert config.region == "us-east-005"
    assert config.endpoint_url == "https://s3.us-east-005.backblazeb2.com"
    assert "test-secret" not in repr(config)


def test_config_rejects_region_endpoint_mismatch() -> None:
    env = {**BASE_ENV, "B2_REGION": "us-west-004"}
    try:
        BackblazeConfig.from_env(env)
    except ValueError as exc:
        assert "match B2_REGION" in str(exc)
    else:
        raise AssertionError("Expected endpoint/region mismatch to fail closed")


def test_config_rejects_non_https_endpoint() -> None:
    env = {**BASE_ENV, "B2_ENDPOINT": "http://s3.us-east-005.backblazeb2.com"}
    try:
        BackblazeConfig.from_env(env)
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("Expected non-HTTPS endpoint to fail closed")


def test_config_rejects_missing_secrets() -> None:
    env = {key: value for key, value in BASE_ENV.items() if key != "B2_APPLICATION_KEY"}
    try:
        BackblazeConfig.from_env(env)
    except ValueError as exc:
        assert "B2_APPLICATION_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing key to fail closed")

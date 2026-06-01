from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    anthropic_api_key: str
    model_id: str = "claude-sonnet-4-6"
    database_path: str = "data/after_sales.db"
    log_level: str = "INFO"

    # 分流阈值
    triage_confidence_threshold: float = 0.75

    # 过敏
    allergy_batch_alert_threshold: float = 0.005
    allergy_batch_window_days: int = 7
    allergy_follow_up_days: list[int] = [7, 14]

    # 赔付
    refund_window_full_days: int = 3
    refund_window_partial_days: int = 60
    fraud_check_days: int = 30
    fraud_check_max_count: int = 2
    vip_threshold_yearly: float = 5000

    # 回复
    reply_max_length: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()

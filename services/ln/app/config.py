from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "bank-ln"
    jwt_secret: str = "wecode-bank-demo-secret-change-me"
    us_base_url: str = "http://127.0.0.1:8001"
    max_active_loans_per_user: int = 5
    max_exposure_cents: int = 50_000_000  # 500,000 yuan
    default_currency: str = "USD"
    late_fee_bps_per_day: int = 5  # 0.05%/day
    grace_days: int = 3


settings = Settings()

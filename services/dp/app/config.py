from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "bank-dp"
    database_url: str = "mysql+pymysql://wecode:wecode_pass@mysql:3306/bank_dp"
    jwt_secret: str = "wecode-bank-demo-secret-change-me"
    cf_base_url: str = "http://127.0.0.1:8001"
    ac_base_url: str = "http://127.0.0.1:8001"
    us_base_url: str = "http://127.0.0.1:8001"
    accounting_queue: str = "ac.accounting.events"

    class Config:
        env_file = ".env"


settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "bank-cf"
    database_url: str = "mysql+pymysql://wecode:wecode_pass@mysql:3306/bank_cf"
    jwt_secret: str = "wecode-bank-demo-secret-change-me"

    class Config:
        env_file = ".env"


settings = Settings()

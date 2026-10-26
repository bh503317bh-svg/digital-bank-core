from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "bank-ac"
    database_url: str = "mysql+pymysql://wecode:wecode_pass@mysql:3306/bank_ac"

    class Config:
        env_file = ".env"


settings = Settings()

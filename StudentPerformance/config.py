import os
from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv()


class Config:
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    API_KEY = os.getenv("API_KEY")

    SQLALCHEMY_DATABASE_URI = URL.create(
    "mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    database=DB_NAME
)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-123'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://ecom_user_db:90NEKl6Us2GQHVs5zGri66fUIguWSI6t@dpg-d3tfbs2li9vc73bauok0-a.oregon-postgres.render.com/ecom_1w2u'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

import os


def get_db_url():
    """
    Returns the PostgreSQL connection URL.
    Prioritizes the DATABASE_URL environment variable (used by Render / cloud hosts),
    automatically normalizing legacy postgres:// to postgresql:// for psycopg2.
    Falls back to granular DB_* environment variables or local development defaults.
    """
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        return db_url

    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '')
    host = os.environ.get('DB_HOST', 'localhost')
    port = os.environ.get('DB_PORT', '5432')
    database = os.environ.get('DB_NAME', 'landbank')

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return f"postgresql://{user}@{host}:{port}/{database}"


if __name__ == '__main__':
    print(f"Database URL configured: {get_db_url()}")

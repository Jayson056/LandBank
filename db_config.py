import os

# Database configuration for local development
# For Render, a DATABASE_URL environment variable will be used.
# Make sure PostgreSQL is running locally and these credentials are correct.
local_db_config = {
    'host': 'dpg-d19tutemcj7s73ettva0-a',
    'port': '5432', # Default PostgreSQL port
    'user': 'database_lanbank_user', # Default PostgreSQL user
    'password': 'Oky6pZH3n8lBnaAbx9iQodLpWRwF3XIo', # *** IMPORTANT: Change this to your actual PostgreSQL password ***
    'database': 'database_lanbank'
}

# In a production environment like Render, you will typically get a DATABASE_URL
# environment variable that looks like:
# postgres://user:password@host:port/database_name
# This function will handle both local and Render environments.
def get_db_url():
    """
    Returns the database URL from environment variables (for Render) or constructs
    one from local_db_config (for local development).
    """
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        print("Using DATABASE_URL from environment.")
        return db_url
    else:
        print("Using local database configuration.")
        config = local_db_config
        return f"postgresql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"

if __name__ == '__main__':
    # This block is for testing the configuration loading
    print(f"Database URL to be used: {get_db_url()}")

# config.py
db_config = {
    'host': 'your-render-mysql-service.internal-hostname.render.com', # <-- THIS IS THE KEY CHANGE!
    'user': 'your_render_db_user',
    'password': 'your_render_db_password',
    'database': 'landbank', # Or whatever database name Render provides/you chose
    'port': 3306 # Usually 3306, but confirm
}

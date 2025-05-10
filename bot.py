import main

def app(environ, start_response):
    """Заглушка для gunicorn, яка запускає бота один раз і тримає процес живим."""
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [b'Bot is running...']
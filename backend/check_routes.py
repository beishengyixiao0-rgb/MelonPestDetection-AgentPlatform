from main import app

routes = []

def get_routes(app, prefix=''):
    for r in app.routes:
        if hasattr(r, 'routes'):
            sub_prefix = prefix + getattr(r, 'prefix', '')
            get_routes(r, sub_prefix)
        else:
            path = prefix + getattr(r, 'path', str(r))
            if not isinstance(r, str):
                routes.append(path)

get_routes(app)

for r in sorted(routes):
    print(r)
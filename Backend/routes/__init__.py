from .captcha_routes import captcha_bp

def register_routes(app):
    app.register_blueprint(captcha_bp, url_prefix="/captcha")

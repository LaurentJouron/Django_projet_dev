from .models import Visit


class VisitMiddleware:
    """
    Advanced middleware to record visits with intelligent filters.

    This middleware tracks all GET requests to the site, excluding:
    - Static and media files
    - AJAX requests
    - Bot/crawler requests
    - Files with common extensions

    Usage:
        Add 'your_app.middleware.VisitMiddleware' to MIDDLEWARE in settings.py
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        """
        Process the request and record visits for GET requests only.

        Args:
            request: HttpRequest object

        Returns:
            HttpResponse object
        """
        # Only record GET requests (not POST, PUT, DELETE, etc.)
        if request.method == "GET" and self.should_track(request):
            Visit.objects.create(path=request.path)

        response = self.get_response(request)
        return response

    def should_track(self, request):
        """
        Determine if this request should be tracked.

        Args:
            request: HttpRequest object

        Returns:
            bool: True if the request should be tracked, False otherwise
        """
        path = request.path

        # Don't track static and media files
        if path.startswith("/static/") or path.startswith("/media/"):
            return False

        # Don't track AJAX requests
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return False

        # Don't track files with common extensions
        extensions = [
            ".css",
            ".js",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".ico",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".map",
            ".json",
        ]
        if any(path.lower().endswith(ext) for ext in extensions):
            return False

        # Don't track bot requests (optional)
        user_agent = request.headers.get("User-Agent", "").lower()
        bots = ["bot", "crawler", "spider", "scraper"]
        if any(bot in user_agent for bot in bots):
            return False

        return True

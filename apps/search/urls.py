from django.urls import path
from .views import SearchView, SearchSuggestionsView

app_name = "search"

urlpatterns = [
    path("", SearchView.as_view(), name="search"),
    path(
        "suggestions/",
        SearchSuggestionsView.as_view(),
        name="search_suggestions",
    ),
]

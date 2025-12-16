"""Pagination utilities for in-memory lists."""

from flask_sqlalchemy.pagination import Pagination


class ListPagination(Pagination):
    """Pagination for pre-sorted in-memory lists.
    
    Use this when you need to paginate a list that has already been 
    sorted in Python (e.g., after distance-based sorting).
    
    Example:
        sorted_items = sort_items_by_distance(items, user)
        pagination = ListPagination(items=sorted_items, page=1, per_page=12)
    """
    
    def __init__(
        self,
        items: list,
        page: int = 1,
        per_page: int = 20,
        **kwargs
    ) -> None:
        # Store the full list for slicing
        self._all_items = items
        # Pass items to parent via kwargs for _query_items
        super().__init__(page=page, per_page=per_page, error_out=False, **kwargs)
    
    def _query_items(self) -> list:
        """Return the slice of items for the current page."""
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        return self._all_items[start:end]
    
    def _query_count(self) -> int:
        """Return the total count of all items."""
        return len(self._all_items)

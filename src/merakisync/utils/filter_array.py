def filter_array(
        values: set[str],
        include: list[str],
        exclude: list[str]
        ) -> bool:
    """Takes values as a set and determines if items in include/exclude are included or excluded in the set"""

    if include and not set(include).issubset(values):
        return False
    if exclude and set(exclude).intersection(values):
        return False

    return True

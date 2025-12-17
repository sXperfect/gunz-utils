# -*- coding: utf-8 -*-
"""
Validation utilities.

This module provides decorators and helpers to improve data validation
and error reporting, wrapping underlying libraries like Pydantic.
"""

import functools
import typing as t
from pydantic import validate_call, ValidationError

def type_checked(func: t.Optional[t.Callable] = None, **kwargs: t.Any) -> t.Callable:
    """
    A wrapper around pydantic.validate_call that provides cleaner, user-friendly error messages.

    It catches `pydantic.ValidationError` and re-raises it as a `TypeError` with a
    formatted message indicating exactly which argument failed and why.

    Parameters
    ----------
    func : Callable, optional
        The function to decorate.
    **kwargs :
        Additional arguments passed to `pydantic.validate_call` (e.g., `config`).

    Returns
    -------
    Callable
        The decorated function with validation logic.

    Examples
    --------
    >>> @type_checked
    ... def my_func(a: int):
    ...     pass
    ...
    >>> my_func("string")
    TypeError: Validation error in 'my_func':
    Argument 'a': Input should be a valid integer, unable to parse string as an integer (got 'string')
    """
    def decorator(f: t.Callable) -> t.Callable:
        # Create the validated version of the function
        validated_func = validate_call(f, **kwargs)

        @functools.wraps(f)
        def wrapper(*args: t.Any, **kw: t.Any) -> t.Any:
            try:
                return validated_func(*args, **kw)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    # Extract location: usually ('args', 0) or ('kwargs', 'arg_name')
                    # We want to present a clean name to the user.
                    loc = error.get("loc", ())
                    msg = error.get("msg", "Invalid input")
                    input_val = error.get("input", "unknown")
                    
                    # Simplify location string
                    # Remove 'args' or 'kwargs' if they are the first element
                    clean_loc = []
                    for item in loc:
                        if item not in ("args", "kwargs"):
                            clean_loc.append(str(item))
                    
                    loc_str = " -> ".join(clean_loc) if clean_loc else "input"
                    
                    errors.append(f"Argument '{loc_str}': {msg} (got {input_val!r})")

                error_msg = f"Validation error in '{f.__name__}':\n" + "\n".join(errors)
                
                # Re-raise as TypeError to be more Pythonic for type issues, 
                # effectively hiding the Pydantic trace from the end user unless they look closer.
                raise TypeError(error_msg) from None

        return wrapper

    if func:
        return decorator(func)
    return decorator

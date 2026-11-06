"""Errors with messages written for the person using the app."""

from fastapi import HTTPException, status


def not_found(what: str = "This item") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} was not found.")


def forbidden(message: str = "You don't have permission to do this.") -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, message)


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def invalid(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def stale_revision(what: str = "This item") -> HTTPException:
    return conflict(f"{what} was changed by someone else, so your change wasn't saved. Check the latest version and try again.")

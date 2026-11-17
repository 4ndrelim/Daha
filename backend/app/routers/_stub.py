from typing import NoReturn

from fastapi import HTTPException


def not_implemented() -> NoReturn:
    raise HTTPException(501, "not implemented")

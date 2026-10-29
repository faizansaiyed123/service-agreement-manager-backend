from fastapi import Response

from app.core.config import get_settings

ACCESS_COOKIE = "sam_access"
REFRESH_COOKIE = "sam_refresh"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() not in {"development", "test"}
    access_path = settings.api_v1_prefix.rstrip("/") or "/"
    refresh_path = f"{access_path}/auth/refresh"
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_minutes * 60,
        path=access_path,
        secure=secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path=refresh_path,
        secure=secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() == "production"
    access_path = settings.api_v1_prefix.rstrip("/") or "/"
    refresh_path = f"{access_path}/auth/refresh"
    response.delete_cookie(ACCESS_COOKIE, path=access_path, secure=secure, httponly=True, samesite=settings.cookie_samesite)
    response.delete_cookie(REFRESH_COOKIE, path=refresh_path, secure=secure, httponly=True, samesite=settings.cookie_samesite)

CUSTOMER_ACCESS_COOKIE = "sam_customer_access"
CUSTOMER_REFRESH_COOKIE = "sam_customer_refresh"


def set_customer_portal_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() not in {"development", "test"}
    access_path = settings.api_v1_prefix.rstrip("/") or "/"
    refresh_path = f"{access_path}/customer-portal/auth/refresh"
    response.set_cookie(
        CUSTOMER_ACCESS_COOKIE, access_token,
        max_age=settings.access_token_minutes * 60,
        path=access_path, secure=secure, httponly=True, samesite=settings.cookie_samesite,
    )
    response.set_cookie(
        CUSTOMER_REFRESH_COOKIE, refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path=refresh_path, secure=secure, httponly=True, samesite=settings.cookie_samesite,
    )


def clear_customer_portal_cookies(response: Response) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() not in {"development", "test"}
    access_path = settings.api_v1_prefix.rstrip("/") or "/"
    refresh_path = f"{access_path}/customer-portal/auth/refresh"
    response.delete_cookie(CUSTOMER_ACCESS_COOKIE, path=access_path, secure=secure, httponly=True, samesite=settings.cookie_samesite)
    response.delete_cookie(CUSTOMER_REFRESH_COOKIE, path=refresh_path, secure=secure, httponly=True, samesite=settings.cookie_samesite)

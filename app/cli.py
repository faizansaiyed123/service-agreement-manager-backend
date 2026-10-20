import sys
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Company, User


def create_owner() -> int:
    """Interactively create the first trusted workspace owner on an already-migrated database."""
    email = input("Owner email (must be an address you control): ").strip().lower()
    full_name = input("Owner full name: ").strip()
    company_name = input("Company/workspace name: ").strip()
    password = getpass("Owner password (minimum 12 characters): ")
    confirmation = getpass("Confirm owner password: ")
    if not email or "@" not in email or not full_name or not company_name:
        print("Email, name, and company are required.", file=sys.stderr)
        return 2
    if len(password) < 12 or len(password) > 128:
        print("Password must contain between 12 and 128 characters.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            print("A user with this email already exists.", file=sys.stderr)
            return 2
        company = Company(name=company_name)
        db.add(company)
        db.flush()
        user = User(
            company_id=company.id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role="owner",
        )
        db.add(user)
        db.commit()
        print("Owner account created. Sign in using the configured HTTPS application URL.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "create-owner":
        print("Usage: python -m app.cli create-owner", file=sys.stderr)
        return 2
    return create_owner()


if __name__ == "__main__":
    raise SystemExit(main())

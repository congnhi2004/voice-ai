from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from pwdlib import PasswordHash

from .config import Settings
from .models import AuthUser, PricingPlan, SubscriptionState


ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
PASSWORD_HASH = PasswordHash.recommended()


class AuthNotConfiguredError(RuntimeError):
    pass


class BillingNotConfiguredError(RuntimeError):
    pass


class AuthBillingError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredUser:
    id: str
    email: str
    name: str | None
    password_hash: str
    plan_id: str
    subscription_status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None

    def public(self) -> AuthUser:
        return AuthUser(
            id=self.id,
            email=self.email,
            name=self.name,
            plan_id=self.plan_id,
            subscription_status=self.subscription_status,
            stripe_customer_id=self.stripe_customer_id,
        )

    def subscription(self) -> SubscriptionState:
        return SubscriptionState(
            plan_id=self.plan_id,
            subscription_status=self.subscription_status,
            stripe_customer_id=self.stripe_customer_id,
            stripe_subscription_id=self.stripe_subscription_id,
            entitlements=entitlements_for_plan(self.plan_id, self.subscription_status),
        )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def available_plans(settings: Settings) -> list[PricingPlan]:
    return [
        PricingPlan(
            id="free",
            name="Free",
            monthly_price_usd=0,
            included_minutes=20,
            overage_price_usd_per_minute=None,
            features=[
                {"key": "local_tts", "label": "Local TTS and video workflow"},
                {"key": "community_support", "label": "Community support"},
            ],
            demo_only=False,
        ),
        PricingPlan(
            id="starter",
            name="Starter",
            monthly_price_usd=49,
            included_minutes=500,
            overage_price_usd_per_minute=0.18,
            stripe_price_id=settings.stripe_price_starter,
            features=[
                {"key": "production_tts", "label": "Production TTS access"},
                {"key": "video_localization", "label": "Video localization jobs"},
                {"key": "api_access", "label": "API access"},
            ],
            demo_only=False,
        ),
        PricingPlan(
            id="pro",
            name="Pro",
            monthly_price_usd=199,
            included_minutes=3000,
            overage_price_usd_per_minute=0.12,
            stripe_price_id=settings.stripe_price_pro,
            features=[
                {"key": "higher_limits", "label": "Higher usage limits"},
                {"key": "priority_processing", "label": "Priority processing"},
                {"key": "team_ready", "label": "Team-ready billing"},
            ],
            demo_only=False,
        ),
    ]


def billable_plan(settings: Settings, plan_id: str) -> PricingPlan | None:
    for plan in available_plans(settings):
        if plan.id == plan_id and plan.monthly_price_usd > 0:
            return plan
    return None


def entitlements_for_plan(plan_id: str, subscription_status: str) -> dict[str, Any]:
    subscribed = subscription_status in ACTIVE_SUBSCRIPTION_STATUSES
    if plan_id == "pro" and subscribed:
        return {"included_minutes": 3000, "video_jobs": True, "priority_processing": True}
    if plan_id == "starter" and subscribed:
        return {"included_minutes": 500, "video_jobs": True, "priority_processing": False}
    return {"included_minutes": 20, "video_jobs": True, "priority_processing": False}


class AuthBillingStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT,
                    password_hash TEXT NOT NULL,
                    plan_id TEXT NOT NULL DEFAULT 'free',
                    subscription_status TEXT NOT NULL DEFAULT 'none',
                    stripe_customer_id TEXT UNIQUE,
                    stripe_subscription_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stripe_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti TEXT PRIMARY KEY,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT NOT NULL
                )
                """
            )

    def create_user(self, *, email: str, password: str, name: str | None) -> StoredUser:
        normalized = email.strip().lower()
        user_id = f"usr_{uuid.uuid4().hex}"
        timestamp = now_utc().isoformat()
        password_hash = PASSWORD_HASH.hash(password)
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, email, name, password_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, normalized, name, password_hash, timestamp, timestamp),
                )
        except sqlite3.IntegrityError as exc:
            raise AuthBillingError("user_exists") from exc
        user = self.get_user_by_email(normalized)
        if user is None:
            raise AuthBillingError("user_create_failed")
        return user

    def authenticate(self, *, email: str, password: str) -> StoredUser | None:
        user = self.get_user_by_email(email.strip().lower())
        if user is None:
            PASSWORD_HASH.verify(password, PASSWORD_HASH.hash("dummy-password-for-timing"))
            return None
        if not PASSWORD_HASH.verify(password, user.password_hash):
            return None
        return user

    def get_user_by_email(self, email: str) -> StoredUser | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return self._row_to_user(row)

    def get_user(self, user_id: str) -> StoredUser | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row)

    def get_user_by_stripe_customer(self, customer_id: str) -> StoredUser | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)).fetchone()
        return self._row_to_user(row)

    def set_stripe_customer(self, user_id: str, customer_id: str) -> StoredUser:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET stripe_customer_id = ?, updated_at = ? WHERE id = ?",
                (customer_id, now_utc().isoformat(), user_id),
            )
        user = self.get_user(user_id)
        if user is None:
            raise AuthBillingError("user_not_found")
        return user

    def update_subscription(
        self,
        *,
        customer_id: str,
        subscription_id: str | None,
        status: str,
        plan_id: str,
    ) -> StoredUser | None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET plan_id = ?, subscription_status = ?, stripe_subscription_id = ?, updated_at = ?
                WHERE stripe_customer_id = ?
                """,
                (plan_id, status or "unknown", subscription_id, now_utc().isoformat(), customer_id),
            )
        return self.get_user_by_stripe_customer(customer_id)

    def record_event_once(self, event_id: str, event_type: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO stripe_events (id, event_type, received_at) VALUES (?, ?, ?)",
                    (event_id, event_type, now_utc().isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def revoke_token(self, *, jti: str, expires_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO revoked_tokens (jti, expires_at, revoked_at) VALUES (?, ?, ?)",
                (jti, expires_at.isoformat(), now_utc().isoformat()),
            )

    def token_revoked(self, jti: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT jti FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
        return row is not None

    def _row_to_user(self, row: sqlite3.Row | None) -> StoredUser | None:
        if row is None:
            return None
        return StoredUser(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            plan_id=row["plan_id"],
            subscription_status=row["subscription_status"],
            stripe_customer_id=row["stripe_customer_id"],
            stripe_subscription_id=row["stripe_subscription_id"],
        )


class AuthService:
    def __init__(self, settings: Settings, store: AuthBillingStore) -> None:
        self.settings = settings
        self.store = store

    def require_configured(self) -> None:
        if not self.settings.auth_configured:
            raise AuthNotConfiguredError("AUTH_JWT_SECRET is required when ENVIRONMENT is production, staging, or public.")

    def register(self, *, email: str, password: str, name: str | None) -> tuple[AuthUser, str]:
        self.require_configured()
        user = self.store.create_user(email=email, password=password, name=name)
        return user.public(), self.issue_token(user)

    def login(self, *, email: str, password: str) -> tuple[AuthUser, str] | None:
        self.require_configured()
        user = self.store.authenticate(email=email, password=password)
        if user is None:
            return None
        return user.public(), self.issue_token(user)

    def issue_token(self, user: StoredUser) -> str:
        secret = self.settings.jwt_secret
        if not secret:
            raise AuthNotConfiguredError("AUTH_JWT_SECRET is required.")
        expires_at = now_utc() + timedelta(minutes=self.settings.auth_access_token_expire_minutes)
        payload = {"sub": user.id, "email": user.email, "jti": f"tok_{uuid.uuid4().hex}", "exp": expires_at, "iat": now_utc()}
        return jwt.encode(payload, secret, algorithm=self.settings.auth_jwt_algorithm)

    def user_from_token(self, token: str) -> StoredUser | None:
        payload = self.decode_token(token)
        if payload is None:
            return None
        jti = payload.get("jti")
        if not isinstance(jti, str) or self.store.token_revoked(jti):
            return None
        subject = payload.get("sub")
        if not isinstance(subject, str):
            return None
        return self.store.get_user(subject)

    def revoke_token(self, token: str) -> bool:
        payload = self.decode_token(token)
        if payload is None:
            return False
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not isinstance(jti, str) or not isinstance(exp, int):
            return False
        self.store.revoke_token(jti=jti, expires_at=datetime.fromtimestamp(exp, tz=timezone.utc))
        return True

    def decode_token(self, token: str) -> dict[str, Any] | None:
        secret = self.settings.jwt_secret
        if not secret:
            raise AuthNotConfiguredError("AUTH_JWT_SECRET is required.")
        try:
            return jwt.decode(token, secret, algorithms=[self.settings.auth_jwt_algorithm])
        except jwt.PyJWTError:
            return None


class StripeBillingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def require_configured(self) -> None:
        if not self.settings.stripe_configured:
            raise BillingNotConfiguredError(
                "Stripe billing is not configured. Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL, and STRIPE_PORTAL_RETURN_URL."
            )

    def _client(self):
        self.require_configured()
        from stripe import StripeClient

        return StripeClient(self.settings.stripe_secret_key)

    def create_customer(self, *, email: str, name: str | None, user_id: str) -> str:
        customer = self._client().v1.customers.create(
            params={"email": email, "name": name, "metadata": {"voice_ai_user_id": user_id}}
        )
        return customer.id

    def create_checkout_session(self, *, customer_id: str, price_id: str, plan_id: str, user_id: str) -> tuple[str, str | None]:
        session = self._client().v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": self.settings.stripe_success_url,
                "cancel_url": self.settings.stripe_cancel_url,
                "client_reference_id": user_id,
                "metadata": {"voice_ai_user_id": user_id, "plan_id": plan_id},
                "subscription_data": {"metadata": {"voice_ai_user_id": user_id, "plan_id": plan_id}},
            }
        )
        return session.url, getattr(session, "id", None)

    def create_portal_session(self, *, customer_id: str) -> tuple[str, str | None]:
        session = self._client().v1.billing_portal.sessions.create(
            params={"customer": customer_id, "return_url": self.settings.stripe_portal_return_url}
        )
        return session.url, getattr(session, "id", None)

    def construct_event(self, *, payload: bytes, signature: str) -> Any:
        self.require_configured()
        from stripe import Webhook

        return Webhook.construct_event(payload, signature, self.settings.stripe_webhook_secret)


class BillingService:
    def __init__(self, settings: Settings, store: AuthBillingStore, stripe_client: StripeBillingClient) -> None:
        self.settings = settings
        self.store = store
        self.stripe_client = stripe_client

    def create_checkout_session(self, *, user: StoredUser, plan_id: str) -> tuple[str, str | None]:
        self.stripe_client.require_configured()
        plan = billable_plan(self.settings, plan_id)
        if plan is None or not plan.stripe_price_id:
            raise AuthBillingError("plan_not_billable")
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer_id = self.stripe_client.create_customer(email=user.email, name=user.name, user_id=user.id)
            user = self.store.set_stripe_customer(user.id, customer_id)
        return self.stripe_client.create_checkout_session(customer_id=customer_id, price_id=plan.stripe_price_id, plan_id=plan.id, user_id=user.id)

    def create_portal_session(self, *, user: StoredUser) -> tuple[str, str | None]:
        self.stripe_client.require_configured()
        if not user.stripe_customer_id:
            raise AuthBillingError("missing_stripe_customer")
        return self.stripe_client.create_portal_session(customer_id=user.stripe_customer_id)

    def handle_webhook(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        event = self.stripe_client.construct_event(payload=payload, signature=signature)
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        event_id = event_dict.get("id")
        event_type = event_dict.get("type")
        if not event_id or not event_type:
            raise AuthBillingError("invalid_stripe_event")
        if not self.store.record_event_once(event_id, event_type):
            return {"received": True, "duplicate": True, "event_type": event_type}

        obj = event_dict.get("data", {}).get("object", {})
        if event_type == "checkout.session.completed":
            self._provision_from_checkout_session(obj)
        elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
            self._provision_from_subscription(obj)
        return {"received": True, "duplicate": False, "event_type": event_type}

    def _provision_from_checkout_session(self, session: dict[str, Any]) -> None:
        customer_id = _as_id(session.get("customer"))
        subscription_id = _as_id(session.get("subscription"))
        metadata = session.get("metadata") or {}
        plan_id = metadata.get("plan_id") or "starter"
        if customer_id:
            self.store.update_subscription(customer_id=customer_id, subscription_id=subscription_id, status="active", plan_id=plan_id)

    def _provision_from_subscription(self, subscription: dict[str, Any]) -> None:
        customer_id = _as_id(subscription.get("customer"))
        subscription_id = _as_id(subscription.get("id"))
        metadata = subscription.get("metadata") or {}
        plan_id = metadata.get("plan_id") or _plan_from_subscription_items(self.settings, subscription) or "starter"
        status = subscription.get("status") or "unknown"
        if customer_id:
            self.store.update_subscription(customer_id=customer_id, subscription_id=subscription_id, status=status, plan_id=plan_id)


def _as_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("id")
        return candidate if isinstance(candidate, str) else None
    return None


def _plan_from_subscription_items(settings: Settings, subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    price_ids = {
        settings.stripe_price_starter: "starter",
        settings.stripe_price_pro: "pro",
    }
    for item in items:
        price_id = _as_id((item.get("price") or {}).get("id"))
        if price_id in price_ids:
            return price_ids[price_id]
    return None


def debug_event_json(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True)

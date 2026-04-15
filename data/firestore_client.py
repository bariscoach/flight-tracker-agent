"""
data/firestore_client.py
Thin wrapper around google-cloud-firestore for reading / writing price history
and detecting price drops.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import config

logger = logging.getLogger(__name__)


class FirestoreClient:
    """Read/write flight price history; detect drops vs stored baseline."""

    def __init__(self):
        self._db = None
        self._init_db()

    def _init_db(self):
        key_path = config.FIRESTORE_KEY_PATH
        if not os.path.exists(key_path):
            logger.warning(
                f"Firestore key not found at {key_path}. "
                "Running without persistent price history."
            )
            return

        try:
            from google.cloud import firestore
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(key_path)
            self._db = firestore.Client(
                project=config.FIRESTORE_PROJECT, credentials=creds
            )
            logger.info("Firestore client initialised.")
        except Exception as exc:
            logger.error(f"Firestore init failed: {exc}")
            self._db = None

    # ── Public API ────────────────────────────────────────────────────────────

    def save_prices(self, flights: list[dict]) -> None:
        """Persist each flight's price so we can track trends over time."""
        if not self._db or not flights:
            return

        batch = self._db.batch()
        now = datetime.now(timezone.utc)

        for f in flights:
            route_key = self._route_key(f)
            date_key = f.get("outbound_date", "unknown")
            doc_id = f"{route_key}_{date_key}_{now.strftime('%Y%m%dT%H%M')}"

            ref = self._db.collection(config.FIRESTORE_COLLECTION).document(doc_id)
            batch.set(ref, {
                "route": route_key,
                "outbound_date": date_key,
                "return_date": f.get("return_date", ""),
                "airline": f.get("airline", ""),
                "price_cad": f.get("price_cad", 0),
                "stops": f.get("stops", -1),
                "duration_minutes": f.get("total_duration_minutes", 0),
                "recorded_at": now,
            })

        try:
            batch.commit()
            logger.info(f"Saved {len(flights)} price records to Firestore.")
        except Exception as exc:
            logger.error(f"Firestore save failed: {exc}")

    def get_all_baselines(self) -> dict:
        """
        Return a dict mapping route_key → minimum historical price (CAD).
        E.g. {"YYZ-IST": 1450.0, "YHM-ESB": 1620.0}
        """
        if not self._db:
            return {}

        baselines: dict[str, float] = {}
        try:
            docs = self._db.collection(config.FIRESTORE_COLLECTION).stream()
            for doc in docs:
                d = doc.to_dict()
                route = d.get("route", "")
                price = d.get("price_cad", 0)
                if route and price:
                    if route not in baselines or price < baselines[route]:
                        baselines[route] = price
        except Exception as exc:
            logger.error(f"Firestore read failed: {exc}")

        return baselines

    def detect_price_drops(
        self,
        current_flights: list[dict],
        baselines: dict,
    ) -> list[dict]:
        """
        Return list of flights whose price is below baseline × threshold.
        Each element includes the flight dict + baseline + saving.
        """
        drops = []
        for f in current_flights:
            route = self._route_key(f)
            baseline = baselines.get(route)
            if baseline and f.get("price_cad"):
                if f["price_cad"] < baseline * config.PRICE_DROP_THRESHOLD:
                    saving = baseline - f["price_cad"]
                    drops.append({
                        **f,
                        "baseline_price_cad": baseline,
                        "saving_cad": round(saving, 2),
                    })
        return drops

    def get_yesterday_prices(self) -> dict:
        """
        Return dict mapping route_key → price from the most recent previous run.
        Used for the ↑↓🟢 indicators in the email table.
        """
        if not self._db:
            return {}

        from datetime import timedelta
        from google.cloud import firestore

        yesterday_start = datetime.now(timezone.utc) - timedelta(hours=30)
        prices: dict[str, float] = {}

        try:
            docs = (
                self._db.collection(config.FIRESTORE_COLLECTION)
                .where("recorded_at", ">=", yesterday_start)
                .order_by("recorded_at", direction=firestore.Query.ASCENDING)
                .stream()
            )
            for doc in docs:
                d = doc.to_dict()
                route = d.get("route", "")
                price = d.get("price_cad", 0)
                if route and price:
                    prices[route] = price  # last seen in window wins
        except Exception as exc:
            logger.error(f"Yesterday-price query failed: {exc}")

        return prices

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _route_key(flight: dict) -> str:
        origin = flight.get("origin", "???")
        dest = flight.get("destination", "???")
        return f"{origin}-{dest}"

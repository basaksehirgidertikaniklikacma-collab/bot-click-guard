"""
Şüpheli IP'leri Google Ads'e yazan senkronizasyon işçisi.

Tasarım kararları (mimari dokümanda konuştuğumuz noktalar):
- BATCH: Tek tek değil, periyodik toplu işlem (kota tasarrufu)
- DEDUP: Aynı IP birden fazla kez yazılmaya çalışılmaz
          (status='PENDING' olanlar işlenir, işlenince 'SYNCED' olur)
- RETRY: Başarısız yazımlar exponential backoff ile tekrar denenir
- ŞEFFAFLIK: Her deneme sync_log tablosuna yazılır -> dashboard'da
             "bu IP tespit edildi ama henüz Google Ads'e yazılamadı"
             gibi durumlar gösterilebilir
"""
import time
from app.database import get_conn, now_iso
from app.google_ads_client import GoogleAdsClient, GoogleAdsAPIError

MAX_RETRIES = 3
DEFAULT_CAMPAIGN_ID = "default"  # gerçek kullanımda account başına campaign eşlemesi gerekir


def sync_pending_ips(client: GoogleAdsClient, batch_size: int = 50) -> dict:
    """
    status='PENDING' olan şüpheli IP'leri toplu halde Google Ads'e yazar.
    Bu fonksiyon periyodik olarak (örn. her 5 dakikada bir) bir
    scheduler/cron tarafından çağrılmalı.
    """
    processed, succeeded, failed = 0, 0, 0

    with get_conn() as conn:
        pending = conn.execute(
            """
            SELECT id, account_id, ip_address, risk_score
            FROM suspicious_ips
            WHERE status = 'PENDING' AND synced_to_google_ads = 0
            ORDER BY risk_score DESC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()

        for row in pending:
            processed += 1
            ok = _write_with_retry(conn, client, row)
            if ok:
                succeeded += 1
            else:
                failed += 1

        conn.commit()

    return {"processed": processed, "succeeded": succeeded, "failed": failed}


def _write_with_retry(conn, client: GoogleAdsClient, row) -> bool:
    account_id = row["account_id"]
    ip_address = row["ip_address"]
    suspicious_id = row["id"]

    attempt = 0
    backoff = 1.0

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            result = client.add_ip_exclusion(account_id, DEFAULT_CAMPAIGN_ID, ip_address)
            conn.execute(
                """
                UPDATE suspicious_ips
                SET status = 'SYNCED', synced_to_google_ads = 1
                WHERE id = ?
                """,
                (suspicious_id,),
            )
            _log(conn, account_id, ip_address, "ADD_IP_EXCLUSION", True,
                 f"Deneme {attempt}: başarılı - {result.get('resource_name')}")
            return True

        except GoogleAdsAPIError as e:
            _log(conn, account_id, ip_address, "ADD_IP_EXCLUSION", False,
                 f"Deneme {attempt}/{MAX_RETRIES}: {e}")
            if not e.retryable or attempt >= MAX_RETRIES:
                conn.execute(
                    "UPDATE suspicious_ips SET status = 'FAILED' WHERE id = ?",
                    (suspicious_id,),
                )
                return False
            time.sleep(backoff)
            backoff *= 2  # exponential backoff

    return False


def _log(conn, account_id: str, ip_address: str, action: str, success: bool, detail: str):
    conn.execute(
        """
        INSERT INTO sync_log (account_id, ip_address, action, success, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (account_id, ip_address, action, int(success), detail, now_iso()),
    )

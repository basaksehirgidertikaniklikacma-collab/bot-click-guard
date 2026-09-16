"""
Kural tabanlı bot/geçersiz tıklama tespit motoru (MVP).

Buradaki eşikler örnek amaçlıdır; gerçek kullanımda müşteri/sektör
bazında ayarlanabilir olmalı (config tablosu üzerinden).

İleride: bu modülün çıktısı (risk_score, reason) aynı formatı koruyacak
şekilde bir ML skorlama modeliyle değiştirilebilir/desteklenebilir —
API sözleşmesi (get_risk_score girdi/çıktı şekli) sabit kalır.
"""
from datetime import datetime, timedelta
from app.database import get_conn

# --- Ayarlanabilir eşikler ---
MAX_CLICKS_PER_WINDOW = 3        # aynı IP'den bu pencerede izin verilen max tıklama
WINDOW_MINUTES = 5               # zaman penceresi
BLOCK_THRESHOLD = 70             # bu skorun üstü -> otomatik engelleme adayı
MONITOR_THRESHOLD = 40           # bu skorun üstü -> izlemeye al

# Bilinen datacenter/proxy IP önekleri (örnek - gerçek kullanımda
# bir IP reputation servisinden (ör. IPQualityScore, MaxMind) beslenmeli)
KNOWN_DATACENTER_PREFIXES = ["34.", "35.", "104.196.", "146.148."]


def evaluate_click(account_id: str, ip_address: str) -> dict:
    """
    Yeni bir tıklama kaydedildikten sonra çağrılır.
    Bu IP için güncel bir risk skoru hesaplar ve gerekiyorsa
    suspicious_ips tablosuna yazar/günceller.
    """
    reasons = []
    score = 0

    with get_conn() as conn:
        window_start = (datetime.utcnow() - timedelta(minutes=WINDOW_MINUTES)).isoformat()
        row = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM clicks
            WHERE account_id = ? AND ip_address = ? AND created_at >= ?
            """,
            (account_id, ip_address, window_start),
        ).fetchone()
        click_count = row["cnt"]

        if click_count > MAX_CLICKS_PER_WINDOW:
            score += 50
            reasons.append(f"{WINDOW_MINUTES} dk içinde {click_count} tıklama (limit: {MAX_CLICKS_PER_WINDOW})")

        if any(ip_address.startswith(p) for p in KNOWN_DATACENTER_PREFIXES):
            score += 40
            reasons.append("Bilinen datacenter/proxy IP aralığı")

        # Çok kısa aralıklarla art arda tıklama (ör. < 2 sn) - bot şüphesi
        recent = conn.execute(
            """
            SELECT created_at FROM clicks
            WHERE account_id = ? AND ip_address = ?
            ORDER BY created_at DESC LIMIT 2
            """,
            (account_id, ip_address),
        ).fetchall()
        if len(recent) == 2:
            t1 = datetime.fromisoformat(recent[0]["created_at"])
            t2 = datetime.fromisoformat(recent[1]["created_at"])
            if (t1 - t2).total_seconds() < 2:
                score += 30
                reasons.append("Art arda 2 saniyeden kısa tıklama aralığı")

        score = min(score, 100)
        reason_text = "; ".join(reasons) if reasons else "Normal davranış"

        if score >= MONITOR_THRESHOLD:
            _upsert_suspicious(conn, account_id, ip_address, score, reason_text)

        conn.commit()

    status = "ALLOW"
    if score >= BLOCK_THRESHOLD:
        status = "BLOCK_CANDIDATE"
    elif score >= MONITOR_THRESHOLD:
        status = "MONITOR"

    return {"ip_address": ip_address, "risk_score": score, "status": status, "reasons": reasons}


def _upsert_suspicious(conn, account_id: str, ip_address: str, score: int, reason: str):
    existing = conn.execute(
        "SELECT id FROM suspicious_ips WHERE account_id = ? AND ip_address = ?",
        (account_id, ip_address),
    ).fetchone()
    now = datetime.utcnow().isoformat()
    if existing:
        conn.execute(
            """
            UPDATE suspicious_ips
            SET risk_score = ?, reason = ?, last_seen = ?
            WHERE id = ?
            """,
            (score, reason, now, existing["id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO suspicious_ips
                (account_id, ip_address, risk_score, reason, status, first_seen, last_seen)
            VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (account_id, ip_address, score, reason, now, now),
        )

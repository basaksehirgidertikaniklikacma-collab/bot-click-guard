"""
Bot Click Guard - MVP API

Çalıştırmak için:
    uvicorn app.main:app --reload --port 8000

Sonra:
    http://localhost:8000/docs  -> interaktif API dokümantasyonu
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.database import init_db, get_conn, now_iso
from app.detection import evaluate_click
from app.sync_worker import sync_pending_ips
from app.google_ads_client import GoogleAdsClient

app = FastAPI(title="Bot Click Guard - MVP")

# Landing page (GoDaddy vb. farklı bir domain) buraya tarayıcıdan istek
# atacağı için CORS'a izin vermemiz gerekiyor. Prod'da allow_origins'i
# kendi site domain'inle sınırlamak daha güvenli olur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


class ClickEvent(BaseModel):
    account_id: str
    campaign_id: str | None = None
    gclid: str | None = None
    landing_page: str | None = None
    # NOT: ip_address burada YOK. Tarayıcı kendi IP'sini bilemez/
    # güvenilir şekilde bildiremez; IP'yi sunucu aşağıda isteğin
    # kendisinden (request.client.host) okuyor.


def _extract_client_ip(request: Request) -> str:
    """
    Gerçek IP'yi bulmaya çalışır. Eğer bir reverse proxy/CDN
    (Cloudflare, nginx vb.) arkasındaysan X-Forwarded-For header'ı
    gerçek istemci IP'sini taşır; yoksa doğrudan bağlantı IP'sini kullan.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/track/click")
def track_click(event: ClickEvent, request: Request):
    """
    Landing page'deki tracking snippet buraya POST atar.
    Her tıklamayı kaydeder ve anında risk değerlendirmesi yapar.
    """
    ip_address = _extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO clicks
                (account_id, campaign_id, ip_address, user_agent, gclid, landing_page, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event.account_id, event.campaign_id, ip_address,
             user_agent, event.gclid, event.landing_page, now_iso()),
        )
        conn.commit()

    result = evaluate_click(event.account_id, ip_address)
    return result


@app.post("/sync/run")
def run_sync():
    """
    Şüpheli IP'leri Google Ads'e yazan senkronizasyonu manuel tetikler.
    Prod'da bu bir cron/scheduler (örn. her 5 dakikada bir) tarafından
    otomatik çağrılır.
    """
    client = GoogleAdsClient()  # developer_token yok -> mock mode
    return sync_pending_ips(client)


@app.get("/accounts/{account_id}/suspicious-ips")
def list_suspicious_ips(account_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ip_address, risk_score, reason, status, first_seen, last_seen
            FROM suspicious_ips
            WHERE account_id = ?
            ORDER BY risk_score DESC
            """,
            (account_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/accounts/{account_id}/sync-log")
def list_sync_log(account_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ip_address, action, success, detail, created_at
            FROM sync_log
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (account_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <h2>Bot Click Guard - MVP</h2>
    <p>API dokümantasyonu için <a href="/docs">/docs</a> adresine git.</p>
    <p>Hızlı test akışı:
        <ol>
            <li>POST /track/click ile birkaç tıklama gönder (aynı IP'den, 5 dk içinde 4+ kez)</li>
            <li>GET /accounts/{account_id}/suspicious-ips ile şüpheli IP'leri gör</li>
            <li>POST /sync/run ile Google Ads'e (mock) yazdır</li>
            <li>GET /accounts/{account_id}/sync-log ile sonucu gör</li>
        </ol>
    </p>
    """

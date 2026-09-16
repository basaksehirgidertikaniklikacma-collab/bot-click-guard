# Bot Click Guard - MVP

Google Ads kampanyalarını bot/geçersiz tıklamalardan koruyan sistemin
çalışan bir prototipi.

## Kurulum

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Sonra tarayıcıda: http://localhost:8000/docs

## Hızlı test akışı

1. `/track/click` endpoint'ine aynı IP'den 5 dakika içinde 4+ istek gönder
   (bot davranışı simülasyonu)
2. `/accounts/{account_id}/suspicious-ips` ile tespit edilen IP'leri gör
3. `/sync/run` ile (mock) Google Ads'e yazdır
4. `/accounts/{account_id}/sync-log` ile senkronizasyon sonucunu gör

## Dosya yapısı

- `app/database.py`      -> SQLite şema ve bağlantı
- `app/detection.py`     -> Kural tabanlı risk skorlama motoru
- `app/google_ads_client.py` -> Google Ads API client (şu an MOCK)
- `app/sync_worker.py`   -> Batch + dedup + retry ile senkronizasyon
- `app/main.py`          -> FastAPI endpoint'leri

## Gerçek Google Ads entegrasyonuna geçiş

Sadece `app/google_ads_client.py` dosyasını değiştirmen yeterli.
Dosyanın içindeki yorum satırlarında adım adım anlatılıyor:
1. Google Ads Developer Token al
2. `pip install google-ads`
3. OAuth2 refresh token oluştur
4. `add_ip_exclusion` fonksiyonunu gerçek API çağrısıyla değiştir

Geri kalan sistem (detection, sync_worker, main) hiç değişmeden çalışmaya devam eder.

## Prod'a geçerken düşünülmesi gerekenler

- SQLite yerine Postgres (multi-tenant, eşzamanlılık için)
- `/sync/run` manuel tetikleme yerine cron/scheduler (örn. her 5 dk)
- Kural motorunun eşikleri (detection.py) hesap/sektör bazında
  config'e taşınmalı
- Risk skorlama motoruna ML katmanı eklenmesi (gri alan vakaları için)

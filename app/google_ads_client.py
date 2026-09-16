"""
Google Ads API client katmanı.

ŞU AN: Mock (taklit) implementasyon - gerçek API çağrısı yapmaz,
sadece davranışı simüle eder (bazen başarısız olur, bazen gecikir).

Developer Token ve OAuth kurulumu tamamlandığında sadece bu dosya
değişecek; geri kalan sistem (detection, sync_worker) bu client'ın
arayüzüne (interface) bağımlı, implementasyonuna değil.

GERÇEK ENTEGRASYON İÇİN YAPILACAKLAR:
1. `pip install google-ads` (resmi Python client kütüphanesi)
2. Google Ads Developer Token al (Google Ads hesabı > Araçlar > API Center)
3. OAuth2 refresh token oluştur (google-ads kütüphanesinin oauth
   yardımcı script'i ile)
4. google-ads.yaml config dosyasını doldur (developer_token,
   client_id, client_secret, refresh_token, login_customer_id)
5. Aşağıdaki `add_ip_exclusion` fonksiyonunu gerçek
   CampaignCriterionService.MutateCampaignCriteria çağrısıyla değiştir.
"""
import random
import time


class GoogleAdsAPIError(Exception):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class GoogleAdsClient:
    def __init__(self, developer_token: str | None = None, customer_id: str | None = None):
        self.developer_token = developer_token
        self.customer_id = customer_id
        self.mock_mode = developer_token is None

    def add_ip_exclusion(self, account_id: str, campaign_id: str, ip_address: str) -> dict:
        """
        Belirtilen IP'yi kampanya seviyesinde negatif kriter (IP hariç
        tutma) olarak ekler.

        Gerçek implementasyonda bu, CampaignCriterionService üzerinden
        bir IpBlockCriterion mutate operasyonu olacak.
        """
        if not self.mock_mode:
            raise NotImplementedError(
                "Gerçek Google Ads API entegrasyonu henüz bağlanmadı. "
                "Developer Token ve OAuth kurulumu tamamlanınca burası "
                "gerçek MutateCampaignCriteria çağrısıyla değiştirilecek."
            )

        # --- MOCK DAVRANIŞ ---
        time.sleep(0.05)  # ağ gecikmesi simülasyonu

        # %15 ihtimalle geçici hata (rate limit vb.) simüle et
        if random.random() < 0.15:
            raise GoogleAdsAPIError(
                "RESOURCE_EXHAUSTED: rate limit aşıldı (mock)", retryable=True
            )

        return {
            "success": True,
            "resource_name": f"customers/{account_id}/campaignCriteria/{campaign_id}~mock-{ip_address}",
            "mock": True,
        }

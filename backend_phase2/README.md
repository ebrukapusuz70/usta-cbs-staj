# USTA CBS Mini Altyapi Envanter Sistemi - 2. Asama Backend

## 1. Amac

Bu proje sadece 2. asama backend API katmanidir. Mevcut PostGIS yapisini degistirmez, GeoServer ayarlarina dokunmaz ve frontend olusturmaz.

Backend, `cbs.vanalar` ve `cbs.borular` tablolarina REST API uzerinden erisim saglar.

## 2. Gerekli Bilgi

Mevcut PostgreSQL bilgileri:

- Host: `localhost`
- Port: `5432`
- Database: `cbs_db`
- User: `usta_admin`
- Password: kullanici tarafindan girilecek

Sifre bu repoda tutulmaz. `.env.example` dosyasini temel alarak yerel `.env` dosyasi olusturun ve sadece `POSTGRES_PASSWORD` degerini doldurun.

## 3. Yapilacak Islem

PowerShell:

```powershell
cd C:\Users\ebruk\OneDrive\Masaüstü\ustabilgisistemleri_staj\outputs\backend_phase2
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python -m uvicorn app.main:app --host localhost --port 8000
```

Swagger:

```text
http://localhost:8000/docs
```

## 4. Kod

Endpointler:

- `GET /api/vanalar`
- `GET /api/vanalar/{id}`
- `POST /api/vanalar`
- `DELETE /api/vanalar/{id}`
- `GET /api/borular`
- `GET /api/borular/{id}`
- `POST /api/borular`
- `DELETE /api/borular/{id}`

POST body:

```json
{
  "malzeme": "celik",
  "cap": 100.00,
  "isletme_durumu": "aktif",
  "geom_wkt": "POINT (3210000 4720000)"
}
```

Boru POST body:

```json
{
  "malzeme": "duktil",
  "cap": 200.00,
  "isletme_durumu": "aktif",
  "geom_wkt": "LINESTRING (3210000 4720000, 3210100 4720100)"
}
```

## 5. Test

Yerel statik test:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
```

Swagger test sirasi:

1. `GET /api/vanalar`
2. `GET /api/borular`
3. `POST /api/vanalar`
4. `POST /api/borular`
5. `DELETE /api/vanalar/{id}`
6. `DELETE /api/borular/{id}`

Database dogrulama sorgulari `scripts/phase2_db_validation.sql` dosyasindadir. Kalici test verisi 2. asama gerekliligi degildir; Swagger POST ile gecici kayit olusturulur ve DELETE ile silinir.

## 6. Beklenen Cikti

- Swagger sayfasi acilir.
- Baslangicta bos tablolar icin `GET` endpointleri bos liste dondurebilir.
- POST sonrasi response icinde `id`, `malzeme`, `cap`, `isletme_durumu`, `geom_wkt`, `srid` alanlari gelir.
- `srid` degeri `3857` olur.
- DELETE sonrasi ilgili kayit silinir.

## 7. Kullanici Onayi

Swagger ve database dogrulamalari basariyla tamamlandiginda 2. asama kilitlenebilir. Bu proje 3. asama, frontend veya harita entegrasyonu icermez.

## 8. 4. Aşama Gas Düzenleme API'si

Mevcut 2. aşama endpointleri korunarak aşağıdaki eklemeli yollar sağlanır:

- `POST /api/gas-pipes`, `GET/PATCH/DELETE /api/gas-pipes/{id}`
- `GET /api/gas-pipes/suggest-code`
- `POST /api/gas-valves`, `GET/PATCH/DELETE /api/gas-valves/{id}`
- `GET /api/gas-valves/suggest-code?related_pipe_id={id}`

İstek geometrileri SRID öneki içermeyen EPSG:3857 WKT'dir. Vana `POINT`, boru
`LINESTRING` kabul eder; LineString, mevcut tablo tipi
nedeniyle backend içinde MultiLineString'e dönüştürülür. Yeni kullanıcı kayıtları
`source=user_created_stage4`, kontrollü test kayıtları `user_created_stage4_e2e`
ile ayrılır. PATCH ve DELETE yalnız bu iki source değerine izin verir; sentetik
demo kayıtları backend tarafından `403 FEATURE_READ_ONLY` ile korunur. Bağlı
vanası bulunan boru cascade silinmez ve bağlı vana sayısıyla birlikte
`409 PIPE_HAS_CONNECTED_VALVES` döner.

Yeni Stage 4 boru ve vana isteklerinde `operator_name` zorunludur. Değerin dış
boşlukları temizlenir ve 2–100 karakter aralığı doğrulanır. Eski kayıtlarda bu
alan `null` olabilir. Boru kodu yalnız harf, rakam ve bölümler arasında kısa
çizgi içerebilir; otomatik öneri bağlantı borusunun bölgesel kodunu, uygun
bağlantı kodu yoksa ağdaki baskın biçimi kullanır. Kullanıcı öneriyi değiştirebilir
ve backend tüm kodları transaction içinde benzersizlik kontrolünden geçirir.
Vana kodu önerisi de bağlı borunun gerçek bölgesel prefix'ini, aynı bölgedeki
mevcut vana kodları bu biçimi doğruladığında kullanır. Otomatik öneri değiştirilebilir;
POST ve PATCH sırasında vana kodu advisory lock altında yeniden doğrulanır.

E2E kaynağı normal frontend tarafından seçilemez. Yalnız backend ortamında
`STAGE4_E2E_TOKEN` tanımlandığında ve test istemcisi aynı değeri
`X-Stage4-E2E-Token` başlığında gönderdiğinde etkinleşir. Gerçek token kaynak
kodda, frontend ortamında veya bu belgede tutulmaz.

Frontend:

```powershell
cd frontend
pnpm run dev
pnpm run typecheck
pnpm run build
```

Haritada **Vana Ekle** veya **Boru Çiz** seçilir, geometri tamamlanır ve açılan
form kaydedilir. İptal veya Escape taslağı siler. Bilgi panelindeki **Düzenle** ve
**Sil** düğmeleri yalnız değiştirilebilir Stage 4 kayıtlarında görünür; silme açık
onay gerektirir. Boru güzergâhı düzenleme mevcut yol/topoloji akışını, vana konumu
düzenleme mevcut snapping ve 10 m aralık akışını yeniden kullanır. Backend ve mevcut
GeoServer `usta_cbs` WMS/WFS servisleri çalışır durumda olmalıdır. Şifre veya
GeoServer kimlik bilgisi frontend'e verilmez.

Backend testleri:

```powershell
cd outputs\backend_phase2
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Vana konumu backend tarafından en yakın boruya taşınır; `related_pipe_id` ve çap
bu borudan türetilir. Boru başlangıcı yalnız bağlı vana, boru ucu veya gerçek
kavşak olabilir. Bağlı vana için `related_pipe_id` mevcut olmalı ve vana
geometrisi bağlı boruya 0,10 m tolerans içinde temas etmelidir.



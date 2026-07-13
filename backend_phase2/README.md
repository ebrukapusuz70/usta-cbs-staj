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



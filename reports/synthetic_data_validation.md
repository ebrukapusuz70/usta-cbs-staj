# 3. Aşama Sentetik Veri Doğrulama Raporu

> Bu veriler gerçek doğalgaz altyapısı değildir. Eğitim ve demo amacıyla oluşturulmuş sentetik verilerdir.

## Kaynak ve yöntem

- İdari sınır: OpenStreetMap `relation/1812356` (Yenimahalle), Nominatim GeoJSON polygonu.
- Yol kaynağı: OpenStreetMap Overpass; gerçek idari polygon içinde kalan taşıt yolu merkez çizgileri.
- İzinli sınıflar: primary, secondary, tertiary, residential, unclassified, living_street ve uygun service.
- Hariç tutulanlar: footway, path, pedestrian, steps, cycleway, bridleway; private/no erişimli service, parking_aisle ve driveway; park, oyun/spor alanı, mezarlık, askeri alan, tarım, çim, su ve orman alanları.
- Analiz CRS: EPSG:32636. Nihai tablo CRS: EPSG:3857.
- Kaynak etiketi: `synthetic_demo_yenimahalle_osm_20260721`.

## Canlı sonuçlar

| Test | Sonuç |
|---|---:|
| gas_pipes | 850 |
| gas_valves | 620 |
| Geçersiz/boş/sıfır uzunluklu boru | 0 |
| Geçersiz/boş vana | 0 |
| Yinelenen boru geometrisi | 0 |
| Yinelenen vana geometrisi | 0 |
| Yinelenen boru/vana kodu | 0 / 0 |
| Yenimahalle polygonu dışındaki boru/vana | 0 / 0 |
| Bağlı borusu olmayan vana | 0 |
| Maksimum vana-boru mesafesi | 0.004679 m |
| En büyük bağlı bileşen | %100 |
| Yol koridoru uyumu | %100 (OSM merkez çizgisinden türetim) |
| Yasak alan ihlali | 0 (1.578 alan geometrisi üretim filtresinde) |

Canlı DB extent (her iki katmanın birleşik kapsamı):
`BOX(3635367.6462277533 4856416.290687872,3655624.5207590996 4875675.667757676)`.

## DB / WFS / rapor karşılaştırması

| Katman | DB | WFS | Rapor |
|---|---:|---:|---:|
| gas_pipes | 850 | 850 | 850 |
| gas_valves | 620 | 620 | 620 |

## GeoServer ve frontend

- Workspace/store korunmuştur: `usta_cbs` / `usta_postgis_store`.
- Native ve declared CRS: EPSG:3857.
- WMS GetCapabilities: 200; WFS GetCapabilities: 200.
- İki katman için GetMap: 200 image/png.
- İki katman için GetFeatureInfo: 200 application/json ve gerçek özellik sonucu.
- Bounds canlı DB geometrisinden yeniden yazılmıştır; 0,0,1,1 veya tahmini bbox kullanılmamıştır.
- Frontend typecheck ve production build başarılıdır.
- Paket içinde lint/test komutu tanımlı değildir.
- 1280×720 ve 390×844 manuel tarayıcı testleri; katman anahtarları, boru/vana paneli ve responsive görünüm başarılı; console hata/uyarı yoktur.

Draw, form, POST, PUT, PATCH veya DELETE frontend işlevi eklenmemiş; 4. aşamaya geçilmemiştir.

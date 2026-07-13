# 1. Asama Dogrulama Kilavuzu

## 1. Amac

Bu dosya, sadece 1. asama kapsaminda olusturulan PostGIS tablolari, GeoServer Store, WMS, WFS ve SLD adimlarini dogrulamak icin kullanilir.

Kullanilan bilgiler:

- PostgreSQL host: `localhost`
- PostgreSQL port: `5432`
- DBeaver PostgreSQL host: `localhost`
- GeoServer Store PostgreSQL host: `usta-postgis`
- Docker PostgreSQL konteyneri: `usta-postgis`
- Database: `cbs_db`
- Schema: `cbs`
- Vanalar tablosu: `cbs.vanalar`
- Borular tablosu: `cbs.borular`
- Geometri kolonu: `geom`
- SRID: `3857`
- GeoServer URL: `http://localhost:8080/geoserver`
- GeoServer Docker konteyneri: `usta-geoserver`
- Workspace: `usta_cbs`
- Store: `usta_postgis_store`
- Layer adlari: `vanalar`, `borular`

## 2. Gerekli Kullanici Bilgileri

Mevcut Docker kurulumundaki PostgreSQL ve GeoServer kullanici adi/sifre bilgileri gerekir. Bu bilgiler guvenlik nedeniyle dosyalara yazilmadi.

DBeaver'da mevcut PostgreSQL baglantiniz varsa ayni baglanti kullanilabilir.

## 3. Yapilacak Islem

### 3.1 Veritabani Olusturma

DBeaver'da `postgres` gibi mevcut bir bakim veritabani baglantisi acin ve `00_create_database.sql` dosyasini calistirin.

Once kontrol sorgusu:

```sql
SELECT datname
FROM pg_database
WHERE datname = 'cbs_db';
```

Sonuc bos ise:

```sql
CREATE DATABASE cbs_db;
```

### 3.2 PostGIS ve Tablolari Olusturma

DBeaver'da `cbs_db` veritabanina baglanin ve `01_postgis_phase1_schema.sql` dosyasini calistirin.

Bu islem sunlari olusturur:

- `postgis` eklentisi
- `cbs` schema
- `cbs.vanalar` tablosu
- `cbs.borular` tablosu
- Her tablo icin `GIST` spatial index

### 3.3 GeoServer Workspace

GeoServer arayuzune girin:

```text
http://localhost:8080/geoserver
```

`Workspaces` bolumunden yeni workspace olusturun:

- Name: `usta_cbs`
- Namespace URI: `http://usta_cbs`

### 3.4 GeoServer Store

`Stores > Add new Store > PostGIS` adimini izleyin.

Store bilgileri:

- Workspace: `usta_cbs`
- Data Source Name: `usta_postgis_store`
- host: `usta-postgis`
- port: `5432`
- database: `cbs_db`
- schema: `cbs`
- user: mevcut PostgreSQL kullaniciniz
- passwd: mevcut PostgreSQL sifreniz

Store kaydetmeden once `Save` ile baglantiyi dogrulayin. DBeaver bilgisayarinizdan baglandigi icin `localhost:5432` kullanir; GeoServer ise Docker konteyneri icinden baglandigi icin host alaninda `usta-postgis` kullanilir.

### 3.5 Layer Yayinlama

Store dogrulandiktan sonra GeoServer `New Layer` ekraninda su tablolari yayinlayin:

- `vanalar`
- `borular`

Her layer icin:

- Declared SRS: `EPSG:3857`
- Native SRS: `EPSG:3857`
- Bounding Boxes: `Compute from data` ve `Compute from native bounds`

Tablolarda veri olmadigi icin bounding box hesabi bos kalabilir. Bu durumda layer kaydi hata vermeden tamamlanmalidir.

### 3.6 SLD Yukleme

`Styles > Add a new style` ekraninda:

- `02_vanalar.sld` dosyasini `vanalar` stili olarak yukleyin.
- `03_borular.sld` dosyasini `borular` stili olarak yukleyin.

Sonra her layer icin `Publishing > Default Style` alaninda ilgili stili secin.

## 4. Kod

Calistirilacak SQL dosyalari:

- `00_create_database.sql`
- `01_postgis_phase1_schema.sql`

GeoServer'a yuklenecek SLD dosyalari:

- `02_vanalar.sld`
- `03_borular.sld`

## 5. Test

### 5.1 PostGIS Testi

`cbs_db` veritabaninda:

```sql
SELECT PostGIS_Version();
```

Beklenen cikti: PostGIS surum bilgisini iceren tek satir.

### 5.2 Tablo Kolon Testi

```sql
SELECT table_schema, table_name, column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_schema = 'cbs'
  AND table_name IN ('vanalar', 'borular')
ORDER BY table_name, ordinal_position;
```

Beklenen cikti:

- Her iki tabloda `id`, `malzeme`, `cap`, `isletme_durumu`, `geom` kolonlari gorunur.
- `geom` kolonu PostGIS geometry tipindedir.

### 5.3 Geometri Tipi ve SRID Testi

```sql
SELECT f_table_schema, f_table_name, f_geometry_column, type, srid
FROM geometry_columns
WHERE f_table_schema = 'cbs'
  AND f_table_name IN ('vanalar', 'borular')
ORDER BY f_table_name;
```

Beklenen cikti:

| f_table_schema | f_table_name | f_geometry_column | type | srid |
| --- | --- | --- | --- | --- |
| cbs | borular | geom | LINESTRING | 3857 |
| cbs | vanalar | geom | POINT | 3857 |

### 5.4 Spatial Index Testi

```sql
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'cbs'
  AND tablename IN ('vanalar', 'borular')
  AND indexname IN ('vanalar_geom_gix', 'borular_geom_gix')
ORDER BY tablename, indexname;
```

Beklenen cikti:

- `borular_geom_gix`
- `vanalar_geom_gix`
- Her iki index taniminda `USING gist` ifadesi

### 5.5 WMS GetCapabilities Testi

Tarayicida acin:

```text
http://localhost:8080/geoserver/usta_cbs/wms?service=WMS&request=GetCapabilities
```

Beklenen cikti:

- XML cevap gelir.
- `vanalar` ve `borular` layer adlari gorunur.

### 5.6 WFS GetCapabilities Testi

Tarayicida acin:

```text
http://localhost:8080/geoserver/usta_cbs/wfs?service=WFS&request=GetCapabilities
```

Beklenen cikti:

- XML cevap gelir.
- `vanalar` ve `borular` feature type adlari gorunur.

## 6. Beklenen Cikti

1. asama sonunda beklenen durum:

- `cbs_db` veritabani vardir.
- `postgis` eklentisi aktiftir.
- `cbs.vanalar` tablosu `POINT,3857` geometriyle vardir.
- `cbs.borular` tablosu `LINESTRING,3857` geometriyle vardir.
- Her iki tabloda `id`, `malzeme`, `cap`, `isletme_durumu`, `geom` alanlari vardir.
- Her iki tabloda spatial index vardir.
- GeoServer'da `usta_cbs` workspace vardir.
- GeoServer'da `usta_postgis_store` PostGIS store vardir.
- `vanalar` ve `borular` layer olarak yayinlanmistir.
- WMS ve WFS GetCapabilities cevaplari alinmistir.
- SLD stilleri layer'lara atanmistir.

## 7. Basarisiz Olursa Olasiliklar

- `CREATE DATABASE cannot run inside a transaction block`: DBeaver'da auto-commit acik degildir veya komut transaction icinde calismistir. `CREATE DATABASE` komutunu tek basina calistirin.
- `database "cbs_db" already exists`: Veritabani zaten vardir. `01_postgis_phase1_schema.sql` adimina gecin.
- `permission denied to create extension postgis`: PostgreSQL kullanicisinin extension olusturma yetkisi yoktur. Yetkili kullanici ile baglanin.
- `type "geometry" does not exist`: `CREATE EXTENSION postgis;` calismamistir veya farkli veritabaninda calistirilmistir.
- GeoServer store baglanti hatasi: GeoServer Docker konteyneri icinden `localhost`, GeoServer konteynerinin kendisini ifade eder. PostGIS host degeri Docker agindaki konteyner adi olan `usta-postgis` olmalidir.
- Layer Preview bos gorunuyor: Tablolara veri eklenmedigi icin normaldir. Hata olmamasi ve layer'in listelenmesi yeterlidir.

## Dosya Agaci

```text
outputs/
  00_create_database.sql
  01_postgis_phase1_schema.sql
  02_vanalar.sld
  03_borular.sld
  04_phase1_validation.md
```

## 7. Devam Etmek Icin Kullanici Onayi

Bu kilavuzdaki adimlari sirayla calistirip test ciktilarini kontrol edin. 1. asama disinda hicbir adim uygulanmamalidir.


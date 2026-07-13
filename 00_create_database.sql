-- 1. Asama - Veritabani olusturma
-- Bu dosyayi DBeaver'da mevcut yetkili PostgreSQL baglantisi uzerinden calistirin.
-- Not: PostgreSQL'de CREATE DATABASE komutu hedef veritabaninin icinden degil,
-- postgres gibi baska bir bakim veritabani baglantisindan calistirilmalidir.

SELECT datname
FROM pg_database
WHERE datname = 'cbs_db';

-- Yukaridaki sorgu sonuc dondurmezse asagidaki komutu calistirin.
CREATE DATABASE cbs_db;


BEGIN;

DO $$
BEGIN
    IF (SELECT count(*) FROM cbs.gas_pipes) <> 852 THEN
        RAISE EXCEPTION 'gas_pipes kayit sayisi 852 degil';
    END IF;
    IF (SELECT count(*) FROM cbs.gas_valves) <> 620 THEN
        RAISE EXCEPTION 'gas_valves kayit sayisi 620 degil';
    END IF;
END
$$;

ALTER TABLE cbs.gas_pipes
    ADD COLUMN operator_name varchar(100) NULL;

ALTER TABLE cbs.gas_valves
    ADD COLUMN operator_name varchar(100) NULL;

DO $$
BEGIN
    IF (SELECT count(*) FROM cbs.gas_pipes) <> 852 THEN
        RAISE EXCEPTION 'gas_pipes kayit sayisi migration sirasinda degisti';
    END IF;
    IF (SELECT count(*) FROM cbs.gas_valves) <> 620 THEN
        RAISE EXCEPTION 'gas_valves kayit sayisi migration sirasinda degisti';
    END IF;
    IF (SELECT count(*) FROM cbs.gas_pipes WHERE operator_name IS NOT NULL) <> 0 THEN
        RAISE EXCEPTION 'gas_pipes mevcut operator_name degerleri NULL degil';
    END IF;
    IF (SELECT count(*) FROM cbs.gas_valves WHERE operator_name IS NOT NULL) <> 0 THEN
        RAISE EXCEPTION 'gas_valves mevcut operator_name degerleri NULL degil';
    END IF;
END
$$;

COMMIT;

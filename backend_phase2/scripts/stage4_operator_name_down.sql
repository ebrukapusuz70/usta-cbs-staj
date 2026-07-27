BEGIN;

ALTER TABLE cbs.gas_valves
    DROP COLUMN operator_name;

ALTER TABLE cbs.gas_pipes
    DROP COLUMN operator_name;

COMMIT;

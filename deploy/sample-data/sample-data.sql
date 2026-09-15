-- Sample data for a demo of the live portal, and the one command that removes it.
--
-- WHY THIS IS SQL AND NOT A PYTHON SCRIPT
-- ---------------------------------------
-- A script under backend/scripts/ would have to be deployed before it could
-- be run, and the point of this is to demo the portal WITHOUT deploying
-- anything. This file talks to the database container directly, so the
-- running application is not touched, restarted or rebuilt.
--
-- It works on the schema the live server has today (through migration 0008)
-- AND on the newer one (0009 and later), because the two disagree about where
-- an order's status lives. Whichever columns are there get filled in.
--
--
-- HOW TO RUN IT   (on the server, in the directory with docker-compose.prod.yml)
-- -----------------------------------------------------------------------------
--   D="docker compose -f docker-compose.prod.yml exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB -q"
--
--   1. See exactly what would be inserted, changing nothing:
--        $D -v mode=dryrun < sample-data.sql
--
--   2. Insert it:
--        $D -v mode=load < sample-data.sql
--
--   3. Remove ALL of it, including the temporary login, in one go:
--        $D -v mode=remove < sample-data.sql
--
-- The dry run is a real one: it performs every insert inside a transaction,
-- reports the result, then rolls back. So it proves the inserts fit this
-- database's actual schema rather than promising that they will.
--
--
-- WHAT MAKES IT SAFE TO REMOVE
-- ----------------------------
-- Every customer created here has a code beginning 'SAMPLE-'. Everything else
-- -- logins, orders, shipments, documents, photos, notification records,
-- sign-in links -- hangs off those customers with ON DELETE CASCADE. Deleting
-- the SAMPLE- customers therefore removes all of it and can reach nothing that
-- was not created here. No real customer or order is read, touched or changed
-- by any mode of this file.
--
-- Two things it cannot undo, worth knowing before you run it:
--
--   * The change history (the Activity tab) is deliberately append-only and
--     has no foreign key to anything, so entries about the sample data remain
--     after removal. That is by design: a record the people it records can
--     tidy is not a record.
--
--   * An email that has actually been sent is sent. Removing a row afterwards
--     does not unsend it. The only addresses here are exports3@alokindia.com
--     and example.com ones, so the worst case is mail to your own inbox and
--     mail that bounces harmlessly.


\set ON_ERROR_STOP on

\if :{?mode}
\else
  \set mode dryrun
\endif

\echo ''
\echo '=================================================================='
\echo 'Alok Ingots customer portal - sample data.  mode:' :mode
\echo '=================================================================='

BEGIN;

-- The mode, put somewhere SQL can see it. psql does not substitute :mode
-- inside a dollar-quoted DO block, so the blocks below read it from here
-- instead of being handed it.
CREATE TEMP TABLE run_mode (m text) ON COMMIT DROP;
INSERT INTO run_mode (m) VALUES (:'mode');

DO $$
DECLARE mode text;
BEGIN
  SELECT m INTO mode FROM run_mode;
  IF mode NOT IN ('dryrun', 'load', 'remove') THEN
    RAISE EXCEPTION 'mode must be dryrun, load or remove (got %)', mode;
  END IF;
END $$;


-- ---------------------------------------------------------------------------
-- Safety check: if a code, address or sales order number used below already
-- belongs to something that is NOT sample data, stop rather than collide.
-- ---------------------------------------------------------------------------
DO $$
DECLARE clash text;
BEGIN
  SELECT string_agg(o.sales_order_no, ', ') INTO clash
  FROM orders o
  WHERE o.sales_order_no LIKE 'SAMPLE/%'
    AND o.customer_id NOT IN (SELECT id FROM customers WHERE code LIKE 'SAMPLE-%');
  IF clash IS NOT NULL THEN
    RAISE EXCEPTION 'Refusing to continue: % is a SAMPLE/ order on a real customer', clash;
  END IF;

  SELECT string_agg(u.email, ', ') INTO clash
  FROM users u
  WHERE lower(u.email) IN ('exports3@alokindia.com',
                           'buyer@example.com',
                           'purchasing@example.com')
    AND u.customer_id NOT IN (SELECT id FROM customers WHERE code LIKE 'SAMPLE-%');
  IF clash IS NOT NULL THEN
    RAISE EXCEPTION 'Refusing to continue: % is already a login on a real customer', clash;
  END IF;
END $$;


-- ---------------------------------------------------------------------------
-- Clear any sample data already present.
--
-- Runs in every mode. In 'load' it makes this file repeatable -- run it twice
-- and you get one copy, not two. In 'remove' it is the entire job. The
-- cascades take the logins, orders, shipments, documents, photos, notification
-- records and sign-in links with their customer.
-- ---------------------------------------------------------------------------
DELETE FROM customers WHERE code LIKE 'SAMPLE-%';


-- ---------------------------------------------------------------------------
-- The sample data.
--
-- Each INSERT ... SELECT carries "WHERE (SELECT m FROM run_mode) <> 'remove'",
-- so in remove mode every one of them selects no rows and inserts nothing.
-- ---------------------------------------------------------------------------

INSERT INTO customers (code, name, country)
SELECT v.code, v.name, v.country
FROM (VALUES
    ('SAMPLE-001', 'Sample Buyer GmbH (DEMO DATA)',     'Germany'),
    ('SAMPLE-002', 'Sample Trading Srl (DEMO DATA)',    'Italy'),
    ('SAMPLE-003', 'Sample Industries Ltd (DEMO DATA)', 'United Kingdom')
) AS v(code, name, country)
WHERE (SELECT m FROM run_mode) <> 'remove';

-- The logins.
--
-- password_hash is deliberately not a real hash. Nobody signs in to these with
-- a password: exports3@alokindia.com signs in with an emailed link, which is
-- how the live portal works anyway. verify_password() returns false for a
-- value it cannot parse, so this is a login with no usable password rather
-- than one with a guessable password.
INSERT INTO users (customer_id, email, password_hash, full_name, is_active)
SELECT c.id, v.email, '!sample-data-no-password-sign-in-by-link', v.full_name, true
FROM (VALUES
    ('SAMPLE-001', 'exports3@alokindia.com', 'Demo Viewer (sample)'),
    ('SAMPLE-002', 'buyer@example.com',      'Sample Buyer'),
    ('SAMPLE-003', 'purchasing@example.com', 'Sample Purchasing')
) AS v(code, email, full_name)
JOIN customers c ON c.code = v.code
WHERE (SELECT m FROM run_mode) <> 'remove';

-- The orders.
INSERT INTO orders (customer_id, sales_order_no, customer_po, grade, description,
                    ordered_qty, unit)
SELECT c.id, v.sales_order_no, v.customer_po, v.grade, v.description,
       v.ordered_qty, v.unit
FROM (VALUES
    ('SAMPLE-001', 'SAMPLE/SO/EXP/001/2025-26', 'PO-SAMPLE-4471',
     '431 / 1.4057',  'Bright bar rounds 20-40 mm, h9',     583.000, 'MT'),
    ('SAMPLE-001', 'SAMPLE/SO/EXP/002/2025-26', 'PO-SAMPLE-4482',
     '304 / 1.4301',  'Bright bar rounds 12-28 mm, h9',     210.000, 'MT'),
    ('SAMPLE-002', 'SAMPLE/SO/EXP/003/2025-26', 'PO-SAMPLE-9901',
     '316L / 1.4404', 'Bright bar hexagons 17-32 mm, h11',  120.500, 'MT'),
    ('SAMPLE-003', 'SAMPLE/SO/EXP/004/2025-26', 'PO-SAMPLE-7730',
     '410 / 1.4006',  'Bright bar rounds 25-50 mm, h9',     340.000, 'MT')
) AS v(code, sales_order_no, customer_po, grade, description, ordered_qty, unit)
JOIN customers c ON c.code = v.code
WHERE (SELECT m FROM run_mode) <> 'remove';

-- The part-shipments, so the progress track and the balances have something to
-- draw. One order is complete, one is part shipped, one has barely started and
-- one has nothing dispatched at all.
INSERT INTO shipments (order_id, shipment_no, dispatched_qty, unit, status,
                       vessel_name, imo_number, container_no, bl_number, etd, eta)
SELECT o.id, v.shipment_no, v.dispatched_qty, v.unit, v.status,
       v.vessel_name, v.imo_number, v.container_no, v.bl_number, v.etd, v.eta
FROM (VALUES
    ('SAMPLE/SO/EXP/001/2025-26', 'SAMPLE/SHP/001-1', 200.000, 'MT', 'Delivered',
     'MV NORDIC STAR',   '9312341', 'CSQU3054383', 'SAMPLE-BL-0011',
     DATE '2025-06-12', DATE '2025-07-08'),
    ('SAMPLE/SO/EXP/001/2025-26', 'SAMPLE/SHP/001-2', 183.000, 'MT', 'In transit',
     'MV BALTIC TRADER', '9487627', 'MSKU6856625', 'SAMPLE-BL-0012',
     DATE '2025-08-21', DATE '2025-09-17'),
    ('SAMPLE/SO/EXP/001/2025-26', 'SAMPLE/SHP/001-3', 200.000, 'MT', 'Shipped',
     'MV ADRIATIC WAVE', '9601235', 'TGHU7649885', 'SAMPLE-BL-0013',
     DATE '2025-09-02', DATE '2025-09-29'),
    ('SAMPLE/SO/EXP/002/2025-26', 'SAMPLE/SHP/002-1', 120.000, 'MT', 'Packed',
     NULL, NULL, NULL, NULL, NULL, NULL),
    ('SAMPLE/SO/EXP/003/2025-26', 'SAMPLE/SHP/003-1',  40.000, 'MT', 'Shipped',
     'MV ADRIATIC WAVE', '9601235', 'FCIU8213470', 'SAMPLE-BL-0031',
     DATE '2025-09-02', DATE '2025-09-29')
) AS v(sales_order_no, shipment_no, dispatched_qty, unit, status,
       vessel_name, imo_number, container_no, bl_number, etd, eta)
JOIN orders o ON o.sales_order_no = v.sales_order_no
WHERE (SELECT m FROM run_mode) <> 'remove';


-- ---------------------------------------------------------------------------
-- The columns that exist on one schema and not the other.
--
-- Before migration 0009 an order carried a typed `status`. After it, the
-- status is worked out from the shipments, the order carries `cancelled`
-- instead, and the last lot of an order is ticked with `is_final`. Filling in
-- whichever is present means one file gives a sensible demo on the build that
-- is live today and on the one waiting to be deployed.
-- ---------------------------------------------------------------------------
DO $$
DECLARE mode text;
BEGIN
  SELECT m INTO mode FROM run_mode;
  IF mode = 'remove' THEN
    RETURN;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'orders' AND column_name = 'status') THEN
    UPDATE orders SET status = 'Part shipped'
     WHERE sales_order_no = 'SAMPLE/SO/EXP/001/2025-26';
    UPDATE orders SET status = 'In production'
     WHERE sales_order_no IN ('SAMPLE/SO/EXP/002/2025-26',
                              'SAMPLE/SO/EXP/004/2025-26');
    UPDATE orders SET status = 'Shipped'
     WHERE sales_order_no = 'SAMPLE/SO/EXP/003/2025-26';
    RAISE NOTICE 'this schema has orders.status (pre-0009): filled it in';
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'shipments' AND column_name = 'is_final') THEN
    -- Order 001 is complete, so its last lot is ticked as the final one and
    -- the order follows the lot furthest behind instead of saying Part
    -- shipped for ever. The rest are genuinely unfinished.
    UPDATE shipments SET is_final = true
     WHERE shipment_no = 'SAMPLE/SHP/001-3';
    RAISE NOTICE 'this schema has shipments.is_final (0009+): ticked the last lot';
  END IF;
END $$;


-- ---------------------------------------------------------------------------
-- What is there now.
-- ---------------------------------------------------------------------------
\echo ''
\echo '--- sample data ---'

SELECT c.code,
       c.name,
       (SELECT count(*) FROM users u  WHERE u.customer_id = c.id) AS logins,
       (SELECT count(*) FROM orders o WHERE o.customer_id = c.id) AS orders,
       (SELECT count(*) FROM shipments s
          JOIN orders o2 ON o2.id = s.order_id
         WHERE o2.customer_id = c.id)                             AS shipments
FROM customers c
WHERE c.code LIKE 'SAMPLE-%'
ORDER BY c.code;

SELECT u.email AS sample_login, c.code AS on_customer
FROM users u JOIN customers c ON c.id = u.customer_id
WHERE c.code LIKE 'SAMPLE-%'
ORDER BY u.email;

\echo '--- real data, untouched ---'

SELECT (SELECT count(*) FROM customers WHERE code NOT LIKE 'SAMPLE-%') AS real_customers,
       (SELECT count(*) FROM orders
         WHERE customer_id NOT IN (SELECT id FROM customers WHERE code LIKE 'SAMPLE-%')
       ) AS real_orders;


-- ---------------------------------------------------------------------------
-- Keep it, or throw it away. A dry run gets here having done every insert,
-- and discards the lot.
-- ---------------------------------------------------------------------------
\echo ''
SELECT CASE WHEN (SELECT m FROM run_mode) IN ('load', 'remove')
            THEN 'COMMIT'  ELSE 'ROLLBACK' END AS finish
\gset
\echo 'finishing with:' :finish

:finish;

\echo 'Done.'
\echo ''

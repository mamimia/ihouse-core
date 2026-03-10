-- Phase 161 — Exchange Rates Table
-- Stores FX rates for optional multi-currency conversion in financial endpoints.
-- Rates are a point-in-time snapshot; management is out-of-scope for Phase 161.

CREATE TABLE IF NOT EXISTS exchange_rates (
    id              BIGSERIAL PRIMARY KEY,
    from_currency   TEXT        NOT NULL,
    to_currency     TEXT        NOT NULL,
    rate            NUMERIC(18, 8) NOT NULL,       -- e.g. 1 USD = 36.50000000 THB
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    source          TEXT,                          -- e.g. 'manual', 'oxr', 'ecb'
    UNIQUE (from_currency, to_currency)
);

-- Commonly-used pairs pre-seeded (1.0 identity rates + real approximations)
INSERT INTO exchange_rates (from_currency, to_currency, rate, source)
VALUES
    ('USD', 'USD', 1.00000000, 'identity'),
    ('THB', 'THB', 1.00000000, 'identity'),
    ('EUR', 'EUR', 1.00000000, 'identity'),
    ('GBP', 'GBP', 1.00000000, 'identity'),
    ('USD', 'THB', 36.50000000, 'manual'),
    ('THB', 'USD', 0.02739726, 'manual'),
    ('USD', 'EUR', 0.92000000, 'manual'),
    ('EUR', 'USD', 1.08695652, 'manual'),
    ('USD', 'GBP', 0.79000000, 'manual'),
    ('GBP', 'USD', 1.26582278, 'manual'),
    ('USD', 'SGD', 1.34000000, 'manual'),
    ('SGD', 'USD', 0.74626866, 'manual'),
    ('USD', 'AUD', 1.55000000, 'manual'),
    ('AUD', 'USD', 0.64516129, 'manual'),
    ('USD', 'JPY', 149.00000000, 'manual'),
    ('JPY', 'USD', 0.00671141, 'manual'),
    ('USD', 'CNY', 7.24000000, 'manual'),
    ('CNY', 'USD', 0.13812155, 'manual'),
    ('USD', 'INR', 83.00000000, 'manual'),
    ('INR', 'USD', 0.01204819, 'manual'),
    ('USD', 'HKD', 7.83000000, 'manual'),
    ('HKD', 'USD', 0.12773109, 'manual'),
    ('USD', 'AED', 3.67000000, 'manual'),
    ('AED', 'USD', 0.27247956, 'manual'),
    ('USD', 'KRW', 1320.00000000, 'manual'),
    ('KRW', 'USD', 0.00075758, 'manual')
ON CONFLICT (from_currency, to_currency) DO NOTHING;

-- Index for fast rate lookup
CREATE INDEX IF NOT EXISTS idx_exchange_rates_pair
    ON exchange_rates (from_currency, to_currency);

CREATE TABLE sellers (seller_id INTEGER PRIMARY KEY, category TEXT, region TEXT);
CREATE TABLE buyers  (buyer_id INTEGER PRIMARY KEY, region TEXT, signup_date TEXT);
CREATE TABLE orders  (
  order_id INTEGER PRIMARY KEY,
  buyer_id INTEGER REFERENCES buyers(buyer_id),
  seller_id INTEGER REFERENCES sellers(seller_id),
  order_date TEXT, quantity INTEGER, amount REAL, status TEXT,
  promised_days INTEGER, actual_days REAL
);

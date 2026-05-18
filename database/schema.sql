CREATE TABLE tariffs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    speed_limit INT NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

INSERT INTO tariffs (name, speed_limit, price) VALUES
('100', 100, 250.00),
('1000', 1000, 350.00);

CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    contract_number VARCHAR(20) UNIQUE NOT NULL,
    address VARCHAR(255) NOT NULL,
    balance NUMERIC(10, 2) DEFAULT 0.00,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'suspended')),
    tariff_id INT REFERENCES tariffs(id) ON DELETE SET NULL
);

INSERT INTO clients (contract_number, address, balance, status, tariff_id) VALUES
('21001', 'вул. Центральна 1, кв. 10', 150.00, 'active', 2),
('21002', 'вул. Садова 5', -50.00, 'active', 1),
('21003', 'пр. Миру 12, кв. 44', 350.00, 'suspended', 2),
('21004', 'вул. Лісна 2', 10.00, 'active', 2),
('21005', 'вул. Польова 8, кв. 1', 500.00, 'active', 2),
('21006', 'вул. Київська 100', 0.00, 'frozen', 1);

CREATE TABLE onu_simulation (
    id SERIAL PRIMARY KEY,
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    phase_state VARCHAR(20) DEFAULT 'working',
    mac_addresses TEXT,
    port_speed VARCHAR(20) DEFAULT 'full-1000',
    rx_power NUMERIC(5, 2) DEFAULT 0.00,
    input_rate INT DEFAULT 50,
    output_rate INT DEFAULT 1500,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO onu_simulation (client_id, phase_state, mac_addresses, port_speed, rx_power, input_rate, output_rate) VALUES
(1, 'working', '6464.4a59.5630', 'full-1000', -19.50, 120, 1500),
(2, 'working', '001a.2b3c.4d5e', 'full-100', -22.10, 40, 800),
(3, 'LOSi', '', 'auto', 0.00, 0, 0),
(4, 'working', 'a1b2.c3d4.e5f6', 'full-1000', -33.40, 5, 10),
(5, 'working', 'a1b2.c3d4.e5f6,001a.2b3c.4d5e,6464.4a59.5630,8674.4a59.5630', 'full-100', -24.00, 15, 45),
(6, 'DyingGasp', '', 'auto', 0.00, 0, 0);

CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    client_id INT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    issue_type VARCHAR(20) NOT NULL CHECK (issue_type IN ('no_internet', 'low_speed')),
    diag_summary TEXT,
    user_indication INT,
    status VARCHAR(20) DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tickets (client_id, issue_type, diag_summary, user_indication, status) VALUES
(4, 'no_internet', 'RX Power: -33.4, Phase: working', 1021, 'open'),
(5, 'low_speed', 'Port: full-100, Tariff: 1000', 0000, 'closed');

CREATE TABLE bot_sessions (
    telegram_id BIGINT PRIMARY KEY,
    contract_number VARCHAR(20),
    current_step VARCHAR(50),
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO bot_sessions (telegram_id, contract_number, current_step) VALUES
(123456789, '21001', 'main_menu'),
(987654321, '21005', 'diag_lamps');

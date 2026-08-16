-- Massa de teste (demo) — base ecommerce
DROP TABLE IF EXISTS pedidos, produtos, clientes CASCADE;

CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    cidade TEXT
);

CREATE TABLE produtos (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    categoria TEXT,
    preco NUMERIC(10,2) NOT NULL
);

CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id),
    produto_id INTEGER REFERENCES produtos(id),
    quantidade INTEGER NOT NULL,
    valor_total NUMERIC(10,2) NOT NULL,
    data_pedido DATE NOT NULL
);

INSERT INTO clientes (nome, email, cidade) VALUES
    ('Ana Souza', 'ana@ex.com', 'São Paulo'),
    ('Bruno Lima', 'bruno@ex.com', 'Rio de Janeiro'),
    ('Carla Dias', 'carla@ex.com', 'Belo Horizonte'),
    ('Diego Alves', 'diego@ex.com', 'São Paulo');

INSERT INTO produtos (nome, categoria, preco) VALUES
    ('Teclado Mecânico', 'Periféricos', 350.00),
    ('Monitor 27"', 'Monitores', 1500.00),
    ('Mouse Gamer', 'Periféricos', 200.00),
    ('Cadeira Ergonômica', 'Móveis', 1200.00);

INSERT INTO pedidos (cliente_id, produto_id, quantidade, valor_total, data_pedido) VALUES
    (1, 1, 1, 350.00, '2026-06-01'),
    (1, 3, 2, 400.00, '2026-06-03'),
    (2, 2, 1, 1500.00, '2026-06-05'),
    (3, 4, 1, 1200.00, '2026-06-10'),
    (4, 2, 2, 3000.00, '2026-06-12'),
    (2, 1, 1, 350.00, '2026-06-15');

-- Massa de teste (demo) — base clinica
DROP TABLE IF EXISTS consultas, medicos, pacientes CASCADE;

CREATE TABLE pacientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    nascimento DATE,
    cidade TEXT
);

CREATE TABLE medicos (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    especialidade TEXT
);

CREATE TABLE consultas (
    id SERIAL PRIMARY KEY,
    paciente_id INTEGER REFERENCES pacientes(id),
    medico_id INTEGER REFERENCES medicos(id),
    data_consulta DATE NOT NULL,
    status TEXT NOT NULL
);

INSERT INTO pacientes (nome, nascimento, cidade) VALUES
    ('Eduardo Reis', '1985-03-12', 'São Paulo'),
    ('Fernanda Melo', '1990-07-25', 'Campinas'),
    ('Gustavo Nunes', '1978-11-02', 'São Paulo'),
    ('Helena Castro', '2000-01-30', 'Santos');

INSERT INTO medicos (nome, especialidade) VALUES
    ('Dra. Paula Rocha', 'Cardiologia'),
    ('Dr. Rafael Pinto', 'Ortopedia'),
    ('Dra. Sofia Braga', 'Dermatologia');

INSERT INTO consultas (paciente_id, medico_id, data_consulta, status) VALUES
    (1, 1, '2026-06-02', 'realizada'),
    (2, 3, '2026-06-04', 'realizada'),
    (3, 1, '2026-06-09', 'agendada'),
    (4, 2, '2026-06-11', 'cancelada'),
    (1, 2, '2026-06-20', 'agendada'),
    (2, 1, '2026-06-22', 'realizada');

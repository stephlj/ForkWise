/* Naming conventions:

tables: plural, lower case, words separated by underscores
primary key: always "id"
foreign keys: x_id, using singular for x

Copyright (c) 2026 Stephanie Johnson

*/

CREATE TABLE unit_conversions(
    id SERIAL PRIMARY key,
    unit_from text NOT NULL,
    unit_to text NOT NULL,
    factor real NOT NULL,
    UNIQUE (unit_from, unit_to, factor)
);

CREATE TABLE ingredients(
    id SERIAL PRIMARY KEY,
    name text NOT NULL,
    unitary_amount real NOT NULL, /* Basic unit of measure for this ingredient, e.g. 28 for one 28 oz can */
    units text NOT NULL, /* for one 28 oz can unitary_amount, this would be oz */
    cal real NOT NULL, /* calories per unitary_amount */
    fat_grams real NOT NULL, /* per unitary_amount */
    protein_grams real NOT NULL, /* per unitary_amount */
    fiber_grams real NOT NULL, /* per unitary_amount */
    sugar_grams real NOT NULL, /* per unitary_amount */
    animal_grams real NOT NULL /* grams of animal-sourced products, per unitary_amount */
);

CREATE TABLE recipes(
    id SERIAL PRIMARY KEY,
    name text NOT NULL,
    ingredient_id integer NOT NULL REFERENCES ingredients(id),
    ingredient_amt real NOT NULL,
    ingredient_units text NOT NULL
);

CREATE TABLE meals(
    id SERIAL PRIMARY KEY,
    date date NOT NULL,
    recipe_id integer NOT NULL REFERENCES recipe(id),
    recipe_amt real NOT NULL
);
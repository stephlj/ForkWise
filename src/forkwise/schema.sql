/* Naming conventions:

tables: plural, lower case, words separated by underscores
primary key: always "id"
foreign keys: x_id, using singular for x

Copyright (c) 2026 Stephanie Johnson

*/

/* Unit conversion:
For units that can be converted into each other,
ie weight units vs volume units,
pick one to normalize to: e.g., for lbs and oz, 
pick oz as normalized (=1). Then lbs factor = 16.
For tsp, Tbsp, cups, pints, quarts, and gallons: 
pick tsp as 1. Everything else is a multiple of tsp.
*/
CREATE TABLE unit_conversions(
    id SERIAL PRIMARY key,
    unit text NOT NULL,
    category text NOT NULL CHECK (category IN ('weight','volume','unit')), /* 'unit' is unitary like one carrot */
    factor real NOT NULL,
    UNIQUE (unit, category, factor)
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
    carb_grams real NOT NULL, /* per unitary_amount */
    white_flour boolean NOT NULL, /* if a white flour product, total g per unitary_amount */
    animal boolean NOT NULL, /* is this an animal-derived product or not */
    UNIQUE (name, unitary_amount, units)
);

CREATE TABLE recipes(
    id SERIAL PRIMARY KEY,
    name text UNIQUE NOT NULL,
    servings integer NOT NULL,
    servings_amt real NOT NULL,
    servings_units text NOT NULL
);

CREATE TABLE components(
    /* components of recipies, ie specific amounts of ingredients to add */
    id SERIAL PRIMARY KEY,
    recipe_id integer NOT NULL references recipes(id),
    ingredient_id integer NOT NULL REFERENCES ingredients(id),
    ingredient_amt real NOT NULL,
    ingredient_units text NOT NULL
);

CREATE TABLE meals(
    id SERIAL PRIMARY KEY,
    date date NOT NULL,
    recipe_id integer NOT NULL REFERENCES recipes(id),
    recipe_servings real NOT NULL
);
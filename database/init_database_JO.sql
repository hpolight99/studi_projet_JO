--	Schéma JO Réservation

---------- UTILISATEUR -----------
CREATE TABLE IF NOT EXISTS users (
	id				SERIAL PRIMARY KEY,
	first_name		TEXT NOT NULL,
	last_name		TEXT NOT NULL,
	email			TEXT UNIQUE NOT NULL,
	password		TEXT NOT NULL,
	key1			TEXT NOT NULL,		   	-- Clé 1 (générée à l'inscription, non exposée)
	created_at		TIMESTAMPTZ DEFAULT NOW()
);

------------ OFFRE ----------------
CREATE TABLE IF NOT EXISTS offers (
	id				SERIAL PRIMARY KEY,
	name			TEXT NOT NULL,
	nbr_ticket		INT	 NOT NULL,			-- nb de personnes incluses (1/2/4/...)
	prix			INT	 NOT NULL			-- prix en euro
);

------------- COMMANDE ------------
CREATE TABLE IF NOT EXISTS orders (
	id				SERIAL PRIMARY KEY,
	user_id			INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
	offer_id   		INT NOT NULL REFERENCES offers(id),
	quantity		INT NOT NULL DEFAULT 1,
	status			TEXT NOT NULL DEFAULT 'draft',  -- draft | paid | canceled 
	created_at 		TIMESTAMPTZ DEFAULT NOW(),
	CONSTRAINT orders_status_chk CHECK (status IN ('draft','paid','canceled'))
);

------------ PAIEMENT -------------
CREATE TABLE IF NOT EXISTS payments (
	id				SERIAL PRIMARY KEY,
	order_id		INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
	amount_cents 	INT NOT NULL,
	status			TEXT NOT NULL,			-- success | failed | refunded (selon besoins)
	key2			TEXT,
	final_key		TEXT,
	created_at		TIMESTAMPTZ DEFAULT NOW()
);

------------ INDEX/CONTRAINTES -------------
-- 1 seul panier 'draft' par utilisateur
--CREATE UNIQUE INDEX IF NOT EXISTS one_draft_per_user
--ON orders(user_id)
--WHERE status = 'draft';

-- éviter plusieurs paiements 'success' pour la même commande
CREATE UNIQUE INDEX IF NOT EXISTS payments_one_success_per_order
ON payments(order_id)
WHERE status = 'success';

-- Index pratiques
CREATE INDEX IF NOT EXISTS idx_orders_user	  ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_offer	  ON orders(offer_id);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);

------------- DONNEES ORGANISATEUR --------- 
INSERT INTO offers(name, nbr_ticket, prix)
SELECT 'Solo', 1, 50
WHERE NOT EXISTS (SELECT 1 FROM offers WHERE name = 'Solo');

INSERT INTO offers(name, nbr_ticket, prix)
SELECT 'Duo', 2, 90
WHERE NOT EXISTS (SELECT 1 FROM offers WHERE name = 'Duo');

INSERT INTO offers(name, nbr_ticket, prix)
SELECT 'Famille', 4, 160
WHERE NOT EXISTS (SELECT 1 FROM offers WHERE name = 'Famille');


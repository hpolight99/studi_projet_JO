#----------------------------------------------------------------------------------------------------------------------#
import os, secrets
from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import psycopg2
import psycopg2.extras
#----------------------------------------------------------------------------------------------------------------------#
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/database_JO")
app = FastAPI(title="JO Reservation")
app.mount("/static", StaticFiles(directory="static"), name="static")
#----------------------------------------------------------------------------------------------------------------------#
def get_connection_database():
	return psycopg2.connect(DATABASE_URL)
#----------------------------------------------------------------------------------------------------------------------#
def get_current_user_id(request: Request) -> int | None:
	"""Récupère l'id utilisateur à partir du cookie, ou None si non connecté / invalide."""
	user_id = request.cookies.get("user_id")
	if not user_id:
		return None
	try:
		return int(user_id)
	except ValueError:
		return None
#----------------------------------------------------------------------------------------------------------------------#
def secure_password(pw: str) -> str:
	import hashlib
	salt = "SALT1234"
	return hashlib.sha256((salt + pw).encode()).hexdigest()
#----------------------------------------------------------------------------------------------------------------------#
def check_password(password: str):
	return len(password) >= 8 and any(charactere.isdigit() for charactere in password)
#----------------------------------------------------------------------------------------------------------------------#
def layout(body_html: str, title: str = "JO France", request: Request = None):
    user_email = None
    if request is not None:
        user_email = request.cookies.get("user_email")

    if user_email:
        menu = f"""
        <a href="/">🏅 JO France</a>
        <a href="/offers">Offres</a>
        <a href="/my/orders">Mes commandes</a>
        <div class="user-box">
          <a href="/logout">Déconnexion</a><br>
          <span class="user-email">{user_email}</span>
        </div>
        """
    else:
        menu = """
        <a href="/">🏅 JO France</a>
        <a href="/offers">Offres</a>
        <a href="/login">Connexion</a>
        <a href="/register">Inscription</a>
        """

    with open("static/layout.html", "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("<!--PAGE_TITLE-->", title)
    html = html.replace("<!--MENU_HTML-->", menu)
    html = html.replace("<!--BODY_HTML-->", body_html)

    return HTMLResponse(html)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/", response_class=HTMLResponse)
def home():
	with open("static/index.html", "r", encoding="utf-8") as fichier:
		return HTMLResponse(fichier.read())
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/login", response_class=HTMLResponse)
def login_page():
	with open("static/login.html", "r", encoding="utf-8") as fichier:
		return HTMLResponse(fichier.read())
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/register", response_class=HTMLResponse)
def register_page():
	with open("static/register.html", "r", encoding="utf-8") as fichier:
		return HTMLResponse(fichier.read())
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/auth/register")
def register(first_name: str = Form(...),last_name: str = Form(...),email: str = Form(...), password: str = Form(...)):
	#------------------------------------------------------------------------------#
	# message d'erreur si mot de passe au minimum 8 characteres et 1 chiffre
	if not check_password(password):
		return layout("""
		<div class="card">
		  <h2>Mot de passe trop faible</h2>
		  <p class="muted">Minimum 8 caractères et 1 chiffre.</p>
		  <a href="/register"><button>← Revenir à l’inscription</button></a>
		</div>
		""", "Erreur d’inscription")

	key1 = secrets.token_hex(16)

	try:
		with get_connection_database() as database:
			with database.cursor() as cursor:
				cursor.execute(
					"INSERT INTO users(first_name, last_name, email, password, key1) "
					"VALUES (%s, %s, %s, %s, %s) RETURNING id",
					(first_name, last_name, email, secure_password(password), key1)
				)
				user_id = cursor.fetchone()[0]

		# ICI on connecte automatiquement l'utilisateur
		resp = RedirectResponse(url="/my/orders", status_code=303)
		resp.set_cookie("user_id", str(user_id), httponly=True, samesite="lax")
		resp.set_cookie("user_email", email, httponly=True, samesite="lax")	 # nouvelle ligne
		return resp
	#------------------------------------------------------------------------------#
	# message d'erreur
	except Exception as e:
		return layout(f"""
		<div class="card">
		  <h2>Erreur d’inscription</h2>
		  <p class="muted">{e}</p>
		  <a href="/register"><button>← Revenir à l’inscription</button></a>
		</div>
		""", "Erreur d’inscription")
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/auth/login")
def login(request: Request, response: Response, email: str = Form(...), password: str = Form(...)):
	passwordXXX = secure_password(password)
	with get_connection_database() as database:
		with database.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
			cursor.execute("SELECT id FROM users WHERE email=%s AND password=%s", (email, passwordXXX))
			row = cursor.fetchone()
			if not row:
				return PlainTextResponse("Identifiants incorrects", status_code=401)
			user_id = row["id"]

	selected_offer_id = request.cookies.get("selected_offer_id")
	#------------------------------------------------------------------------------#
	# si offre choisie avant de se connecter alors on crée une commande 'draft'
	if selected_offer_id:
		with get_connection_database() as database:
			with database.cursor() as cursor:
				#------------------------------------------------------------------#
				# annuler tous les anciens paniers "draft" de cet utilisateur
				cursor.execute(
					"UPDATE orders SET status='canceled' WHERE user_id=%s AND status='draft'",
					(int(user_id),)
				)
				#------------------------------------------------------------------#
				# récupérer le nombre de places de l'offre
				cursor.execute("SELECT nbr_ticket FROM offers WHERE id=%s", (int(selected_offer_id),))
				row = cursor.fetchone()
				if row:
					nbr_ticket = row[0]
					cursor.execute(
						"INSERT INTO orders(user_id,offer_id,quantity,status) VALUES(%s,%s,%s,'draft')",
						(int(user_id), int(selected_offer_id), nbr_ticket)
					)
	#------------------------------------------------------------------------------#
	resp = RedirectResponse(url="/my/orders", status_code=303)
	resp.set_cookie("user_id", str(user_id), httponly=True, samesite="lax")
	resp.set_cookie("user_email", email, httponly=True, samesite="lax")	 # nouvelle ligne
	if selected_offer_id:
		resp.delete_cookie("selected_offer_id")
	return resp
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/logout")
def logout():
	resp = RedirectResponse(url="/", status_code=303)
	# On supprime les cookies liés à la session
	resp.delete_cookie("user_id")
	resp.delete_cookie("selected_offer_id")
	resp.delete_cookie("user_email")  # pour effacer l’email du header
	return resp
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/my/cart")
def cart_add(request: Request, offer_id: int = Form(...), quantity: int = Form(1)):
	user_id = request.cookies.get("user_id")
	if not user_id:
		# Simple : on demande de se connecter avant d'ajouter au panier
		body = """
		<div class="card">
		  <h2>Connexion requise</h2>
		  <p class="muted">Vous devez être connecté pour ajouter une offre au panier.</p>
		  <a href="/login"><button>Se connecter</button></a>
		</div>
		"""
		return layout(body, "Connexion requise", request)

	if quantity < 1:
		quantity = 1

	with get_connection_database() as conn:
		with conn.cursor() as cur:
			# Vérifier que l'offre existe
			cur.execute("SELECT nbr_ticket, prix FROM offers WHERE id=%s", (offer_id,))
			row = cur.fetchone()
			if not row:
				return PlainTextResponse("Offre inconnue", status_code=400)

			# On ne touche pas à nbr_ticket ici, quantity = nombre de "packs"
			cur.execute(
				"INSERT INTO orders(user_id, offer_id, quantity, status) "
				"VALUES(%s, %s, %s, 'draft')",
				(int(user_id), offer_id, quantity)
			)

	# On renvoie l'utilisateur vers son panier
	return RedirectResponse(url="/my/orders", status_code=303)	
#----------------------------------------------------------------------------------------------------------------------#
def create_offers_cards(offers):
	cards=[]
	#------------------------------------------------------------------------------#
	for choix in offers:
		prix_euro=choix["prix"]
		card=f"""
		<label class="offer-select">
		  <input type="radio" name="offer_id" value="{choix['id']}" data-offer-name="{choix['name']}" required>
		  <div class="offer-card card">
			<h3>{choix['name']}</h3>
			<p class="muted">{choix['nbr_ticket']} personne(s)</p>
			<p class="prix">{int(prix_euro)} €</p>
		  </div>
		</label>
		"""
		cards.append(card)
	#------------------------------------------------------------------------------#
	return (cards)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/offers", response_class=HTMLResponse)
def offers(request: Request):
    # Récupération des offres
    with get_connection_database() as database:
        with database.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SELECT id, name, nbr_ticket, prix FROM offers ORDER BY id")
            offers = cursor.fetchall()

    # Génération des cartes HTML 
    cards = create_offers_cards(offers)
    cards_html = "".join(cards)

    # On ne met PAS de f-string ici pour éviter les problèmes avec le JavaScript
    body = """
    <h2>Choisissez votre offre</h2>
    <form method="post" action="/my/cart" class="offer-form">
      <div class="grid">
        ___CARDS___
      </div>

	  <!-- La quantité personnalisée est désactivée.
      <div class="card" style="margin-top:12px;">
        <label for="quantity"><strong>Quantité :</strong></label>
        <input type="number" id="quantity" name="quantity" value="1" min="1" style="max-width:80px;">
      </div>
	  -->	

      <div class="validate-bar">
        <button id="addToCartButton" type="submit" disabled style="display:block;width:100%;">Mettre au panier</button>
      </div>
    </form>

    <script>
      const radios = document.querySelectorAll("input[name='offer_id']");
      const button = document.getElementById("addToCartButton");

      radios.forEach(function(r) {
        r.addEventListener("change", function() {
          const offerName = r.getAttribute("data-offer-name");
          button.textContent = "Mettre au panier : " + offerName;
          button.disabled = false;
        });
      });
    </script>
    """

    body = body.replace("___CARDS___", cards_html)
    return layout(body, "Offres", request)
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/offers/validate")
def offers_validate(request: Request, offer_id: int | None = Form(None)):
	# 1) Aucun choix -> page gentille au lieu d'une 500/422
	if not offer_id:
		body = """
		<div class="card">
		  <h2>Aucune offre sélectionnée</h2>
		  <p class="muted">Merci de choisir une offre avant de valider.</p>
		  <a href="/offers"><button>← Retour aux offres</button></a>
		</div>
		"""
		return layout(body, "Sélection requise",request)

	# 2) Vérifier si l'utilisateur est déjà connecté
	user_id = request.cookies.get("user_id")

	# 👉 CAS 1 : pas connecté → on garde l'ancien comportement : redirection vers /login
	if not user_id:
		resp = RedirectResponse(url="/login", status_code=303)
		# On mémorise l'offre choisie pour après la connexion
		resp.set_cookie("selected_offer_id", str(offer_id), httponly=False, samesite="lax")
		return resp

	# 👉 CAS 2 : déjà connecté → on crée directement une commande 'draft' et on envoie vers /pay
	with get_connection_database() as database:
		with database.cursor() as cursor:
			# Annuler d'anciens paniers 'draft' pour cet utilisateur
			cursor.execute(
				"UPDATE orders SET status='canceled' WHERE user_id=%s AND status='draft'",
				(int(user_id),)
			)

			# Récupérer le nombre de places de l'offre
			cursor.execute("SELECT nbr_ticket FROM offers WHERE id=%s", (int(offer_id),))
			row = cursor.fetchone()
			if not row:
				# Offre introuvable → petit message propre
				return layout("""
				<div class="card">
				  <h2>Offre introuvable</h2>
				  <p class="muted">Merci de choisir une offre valide.</p>
				  <a href="/offers"><button>← Retour aux offres</button></a>
				</div>
				""", "Erreur",request)

			nbr_ticket = row[0]

			# Créer la commande en 'draft'
			cursor.execute(
				"INSERT INTO orders(user_id, offer_id, quantity, status) "
				"VALUES(%s, %s, %s, 'draft') RETURNING id",
				(int(user_id), int(offer_id), int(nbr_ticket))
			)
			order_id = cursor.fetchone()[0]

	# On envoie l'utilisateur directement sur la page de paiement
	return RedirectResponse(url=f"/pay?order_id={order_id}", status_code=303)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/my/orders", response_class=HTMLResponse)
def my_orders(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    cart_orders = []
    paid_orders = []

    with get_connection_database() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Toutes les commandes en "draft" = le panier
            cur.execute("""
                SELECT 
                    o.id AS order_id,
                    o.quantity,
                    o.status,
                    of.name AS offer_name, 
                    of.nbr_ticket,
                    of.prix
                FROM orders AS o
                JOIN offers AS of ON of.id = o.offer_id
                WHERE o.user_id = %s AND o.status = 'draft'
                ORDER BY o.id ASC
            """, (int(user_id),))
            cart_orders = cur.fetchall()
            
            # Commandes payées
            cur.execute("""
                SELECT 
                    o.id AS order_id, 
                    o.quantity, 
                    o.status, 
                    o.created_at,
                    of.name AS offer_name,
                    of.nbr_ticket,
                    of.prix,
                    p.final_key
                FROM orders AS o
                JOIN offers AS of ON of.id = o.offer_id
                JOIN payments p ON p.order_id = o.id
                WHERE o.user_id = %s AND o.status = 'paid'
                ORDER BY o.id ASC
            """, (int(user_id),))
            paid_orders = cur.fetchall()

    blocks = []
    #------------------------------------------------------------------------------#
    # Bloc "Panier"
    if cart_orders:
        rows = []
        for o in cart_orders:
            price_eur = o["prix"] or 0
            qty = o["quantity"] or 1
            total = price_eur * qty
            rows.append(f"""
              <tr>
                <td>{o['offer_name']}</td>
                <td>{o['nbr_ticket']}</td>
                <td>{qty}</td>
                <td>{total:.2f} €</td>
                <td>
                  <a href="/pay?order_id={o['order_id']}"><button>Payer</button></a>
                </td>
                <td>
                  <form method="post" action="/payments/cancel" style="margin:0">
                    <input type="hidden" name="order_id" value="{o['order_id']}">
                    <button class="secondary" type="submit">Retirer</button>
                  </form>
                </td>
              </tr>
            """)

        cart_block = f"""
        <div class="hero">
          <h2>Votre panier</h2>
          <div class="card">
            <table>
              <thead>
                <tr>
                  <th>Offre</th>
                  <th>Pers.</th>
                  <th>Qté</th>
                  <th>Total</th>
                  <th colspan="2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </div>
        </div>
        """
    else:
        cart_block = """
        <div class="hero">
          <h2>Votre panier</h2>
          <div class="card">
            <p class="muted">Aucun article dans votre panier.</p>
            <a href="/offers"><button>Voir les offres</button></a>
          </div>
        </div>
        """

    blocks.append(cart_block)
    #------------------------------------------------------------------------------#
    # Bloc billets payés
    if paid_orders:
        rows = []
        for p in paid_orders:
            price_eur = p["prix"] or 0
            qty = p["quantity"] or 1
            total = price_eur * qty

            # Récupération / formatage de la date d'achat
            purchase_dt = p.get("created_at")
            if purchase_dt:
                purchase_str = purchase_dt.strftime("%d/%m/%Y %H:%M")
            else:
                purchase_str = "-"

            rows.append(f"""
              <tr>
                <td>{p['offer_name']}</td>
                <td>{p['nbr_ticket']}</td>
                <td>{qty}</td>
                <td>{total:.2f} €</td>
                <td><code style="font-size:.9em">{p['final_key']}</code></td>
                <td>{purchase_str}</td>
              </tr>
            """)

        paid_block = f"""
        <div class="hero" style="margin-top:16px">
          <h2>Vos billets payés</h2>
          <div class="card">
            <table>
              <thead>
                <tr>
                  <th>Offre</th>
                  <th>Pers.</th>
                  <th>Qté</th>
                  <th>Total</th>
                  <th>Clé finale</th>
                  <th>Date d'achat</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </div>
        </div>
        """

    else:
        paid_block = """
        <div class="hero" style="margin-top:16px">
          <h2>Vos billets payés</h2>
          <div class="card">
            <p class="muted">Aucun billet payé pour le moment.</p>
          </div>
        </div>
        """

    blocks.append(paid_block)
   #------------------------------------------------------------------------------#
    return layout("".join(blocks), "Mes commandes", request)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/pay", response_class=HTMLResponse)
def pay_page(request: Request, order_id: int):
	#------------------------------------------------------------------------------#
	# 1) Vérifier que l'utilisateur est bien connecté
	user_id = get_current_user_id(request)
	if user_id is None:
		return RedirectResponse(url="/login", status_code=303)
	#------------------------------------------------------------------------------#
	# 2) Récupérer le nom + prix de l'offre choisie
	with get_connection_database() as conn:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			cur.execute("""
				SELECT of.name AS offer_name, of.prix
				FROM orders o
				JOIN offers of ON of.id = o.offer_id
				WHERE o.id = %s AND o.user_id = %s
			""", (order_id, user_id))
			row = cur.fetchone()
	#------------------------------------------------------------------------------#
	if not row:
		return PlainTextResponse("Commande introuvable.", status_code=404)

	offer_name = row["offer_name"]
	price_eur = row["prix"]			

	#------------------------------------------------------------------------------#
	# 3) Affichage de la page de paiement
	body = f"""
	<div class="card">
	  <h2>Paiement</h2>
	  <p class="muted">Vous avez choisi : <strong>{offer_name}</strong></p>
	  <p><strong>Prix :</strong> {price_eur:.2f} €</p>
	  <p class="muted">Le paiement est simulé (aucune transaction réelle).</p>

	  <!-- Bouton payer -->
	  <form method="post" action="/payments/confirm" style="margin-bottom:10px;">
		<input type="hidden" name="order_id" value="{order_id}">
		<button type="submit">Payer maintenant (mock)</button>
	  </form>

	  <!-- Ligne de boutons "retour" + "supprimer" -->
	  <div style="display:flex; justify-content:space-between; margin-top:15px;">
	    <!-- Bouton gauche -->
        <a href="/my/orders">
          <button class="secondary" type="button">← Retour à mes commandes</button>
        </a>

        <!-- Bouton droite -->
        <form method="post" action="/payments/cancel" style="margin:0;">
          <input type="hidden" name="order_id" value="{order_id}">
          <button class="secondary" type="submit" style="background:#d9534f; color:white;">
            Supprimer cette commande du panier
          </button>
        </form>
      </div>
	</div>
	"""
	return layout(body, "Paiement", request)
#----------------------------------------------------------------------------------------------------------------------#
# @app.post("/payments/cancel")
# def payment_cancel(order_id: int = Form(...)):
	# with get_connection_database() as conn:
		# with conn.cursor() as cur:
			# cur.execute("UPDATE orders SET status='canceled' WHERE id=%s", (order_id,))
	# return RedirectResponse(url="/offers", status_code=303)
	
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/payments/cancel")
def payment_cancel(order_id: int = Form(...)):
    with get_connection_database() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE orders SET status='canceled' WHERE id=%s", (order_id,))
    return RedirectResponse(url="/my/orders", status_code=303)
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/payments/confirm", response_class=HTMLResponse)
def payment_confirm(request: Request, order_id: int = Form(...)):
	user_id = get_current_user_id(request)
	#------------------------------------------------------------------------------#
	if user_id is None:
		return RedirectResponse(url="/login", status_code=303)
	#------------------------------------------------------------------------------#
	key2 = secrets.token_hex(16)
	with get_connection_database() as conn:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			cur.execute("""
				SELECT u.key1, of.name, of.nbr_ticket, of.prix
				FROM orders o
				JOIN users u ON o.user_id = u.id
				JOIN offers of ON o.offer_id = of.id
				WHERE o.id=%s AND o.user_id=%s
			""", (order_id, user_id))
			row = cur.fetchone()
			if not row:
				return PlainTextResponse("Commande introuvable", status_code=404)
			key1 = row["key1"]
			final_key = key1 + key2

			amount_cents = int(row["prix"] * 100)

			cur.execute("UPDATE orders SET status='paid' WHERE id=%s", (order_id,))
			cur.execute(
				"INSERT INTO payments(order_id, amount_cents, status, key2, final_key) VALUES(%s,%s,%s,%s,%s) RETURNING id",
				(order_id, amount_cents, 'success', key2, final_key)
			)
			
			#----------------------------------------------------------------------#
			# on nettoie d'éventuels brouillons restants pour cet utilisateur
			# cur.execute(
				# "UPDATE orders SET status='canceled' WHERE user_id=%s AND status='draft'",
				# (user_id,)
			# )
	#------------------------------------------------------------------------------#
	body = f"""
	<div class="hero">
	  <h2>Confirmation — E-billet</h2>
	  <p class="ok">Paiement validé. Votre billet est sécurisé.</p>
	  <p><strong>Clé finale (QR simulé) :</strong></p>
	  <div class="card"><code>{final_key}</code></div>
	  <p class="muted">Dans une version avancée, cette clé est encodée en QR code image.</p>
	  <a href="/my/orders">← Voir mes commandes</a>
	</div>
	"""
	return layout(body, "E-billet",request)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    # 1) Récupérer les offres en base
    with get_connection_database() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, nbr_ticket, prix FROM offers ORDER BY id ASC")
            offers = cur.fetchall()

            # 2) Récupérer aussi les stats par offre (billets vendus, personnes, CA)
            cur.execute("""
                SELECT 
                    of.id,
                    of.name,
                    of.nbr_ticket,
                    of.prix,
                    COALESCE(SUM(o.quantity), 0) AS total_packs,
                    COALESCE(SUM(o.quantity) * of.nbr_ticket, 0) AS total_persons,
                    COALESCE(SUM(o.quantity * of.prix), 0) AS total_turnover
                FROM offers of
                LEFT JOIN orders o 
                    ON o.offer_id = of.id
                   AND o.status = 'paid'
                GROUP BY of.id, of.name, of.nbr_ticket, of.prix
                ORDER BY of.id ASC
            """)
            stats = cur.fetchall()

    # 3) Construire UNIQUEMENT les lignes du tableau des offres
    if offers:
        offers_rows_html = ""
        for o in offers:
            offers_rows_html += f"""
            <tr>
              <td>{o['id']}</td>
              <td>{o['name']}</td>
              <td>{o['nbr_ticket']}</td>
              <td>{o['prix']:.2f} €</td>
              <td>
                <form method="post" action="/admin/offers/delete" style="margin:0"
                      onsubmit="return confirm('Supprimer cette offre ?');">
                  <input type="hidden" name="offer_id" value="{o['id']}">
                  <button type="submit" class="secondary">Supprimer</button>
                </form>
              </td>
            </tr>
            """
    else:
        # 5 colonnes visibles -> colspan=5
        offers_rows_html = """
        <tr>
          <td colspan="5" class="muted">Aucune offre pour le moment.</td>
        </tr>
        """

    # 4) Construire les lignes du tableau des stats
    if stats:
        stats_rows_html = ""
        for s in stats:
            total_packs = s["total_packs"] or 0
            total_persons = s["total_persons"] or 0
            ca = float(s["total_turnover"] or 0)
            prix = float(s["prix"] or 0)

            stats_rows_html += f"""
            <tr>
              <td>{s['id']}</td>
              <td>{s['name']}</td>
              <td>{s['nbr_ticket']}</td>
              <td>{prix:.2f} €</td>
              <td>{total_packs}</td>
              <td>{total_persons}</td>
              <td>{ca:.2f} €</td>
            </tr>
            """
    else:
        # 7 colonnes visibles -> colspan=7
        stats_rows_html = """
        <tr>
          <td colspan="7" class="muted">Aucune statistique disponible.</td>
        </tr>
        """

    # 5) Charger le HTML de base et remplacer les marqueurs
    with open("static/admin.html", "r", encoding="utf-8") as fichier:
        html = fichier.read()

    html = html.replace("<!--OFFERS_ROWS-->", offers_rows_html)
    html = html.replace("<!--STATS_ROWS-->", stats_rows_html)

    return HTMLResponse(html)
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/admin/offers/new")
def admin_add_offer(name: str = Form(...), nbr_ticket: int = Form(...), prix: float = Form(...)):
	with get_connection_database() as conn:
		with conn.cursor() as cur:
			cur.execute("INSERT INTO offers(name,nbr_ticket,prix) VALUES(%s,%s,%s)", (name, nbr_ticket, prix))
    # On revient sur la page admin pour voir la liste à jour
	return RedirectResponse(url="/admin", status_code=303)
#----------------------------------------------------------------------------------------------------------------------#
@app.post("/admin/offers/delete")
def admin_delete_offer(offer_id: int = Form(...)):
    with get_connection_database() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM offers WHERE id=%s", (offer_id,))
    # On revient sur la page admin pour voir la liste à jour
    return RedirectResponse(url="/admin", status_code=303)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/admin/users/list", response_class=HTMLResponse)
def admin_list_users(request: Request, page: int = 1):
    page = max(1, page)

    page_size = 10
    offset = (page - 1) * page_size

    with get_connection_database() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, first_name, last_name, email
                FROM users
                ORDER BY id ASC
                LIMIT %s OFFSET %s
            """, (page_size + 1, offset))
            rows = cur.fetchall()

    has_next = len(rows) > page_size
    users = rows[:page_size]

    # Lignes du tableau
    if users:
        html_rows = ""
        for u in users:
            html_rows += f"""
            <tr>
              <td>{u['id']}</td>
              <td>{u['first_name']} {u['last_name']}</td>
              <td>{u['email']}</td>
            </tr>
            """
    else:
        # 3 colonnes → colspan=3
        html_rows = """
        <tr>
          <td colspan="3" class="muted">Aucun utilisateur trouvé.</td>
        </tr>
        """

    # Pagination
    nav = []
    if page > 1:
        nav.append(f'<a href="/admin/users/list?page={page-1}">← Page précédente</a>')
    if has_next:
        nav.append(f'<a href="/admin/users/list?page={page+1}">Page suivante →</a>')

    if nav:
        pagination_html = f"<div style='margin-top:12px; display:flex; gap:10px;'>{' '.join(nav)}</div>"
    else:
        pagination_html = ""

    # Charger le template HTML
    with open("static/admin_users.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Remplacer les marqueurs
    html = html.replace("<!--ROWS_HERE-->", html_rows)
    html = html.replace("<!--PAGINATION_HERE-->", pagination_html)

    return HTMLResponse(html)
#----------------------------------------------------------------------------------------------------------------------#
@app.get("/admin/orders", response_class=HTMLResponse)
def admin_orders(request: Request, status: str = "paid", page: int = 1):
    # Normaliser le statut
    allowed_status = {"paid", "draft", "canceled"}
    if status not in allowed_status:
        status = "paid"

    page = max(1, page)
    page_size = 10
    offset = (page - 1) * page_size

    with get_connection_database() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    o.id AS order_id,
                    o.quantity,
                    o.status,
                    o.created_at,
                    u.email,
                    of.name AS offer_name,
                    of.nbr_ticket,
                    of.prix,
                    p.final_key
                FROM orders o
                JOIN users u ON u.id = o.user_id
                JOIN offers of ON of.id = o.offer_id
                LEFT JOIN payments p ON p.order_id = o.id
                WHERE o.status = %s
                ORDER BY o.id ASC
                LIMIT %s OFFSET %s
            """, (status, page_size + 1, offset))
            rows = cur.fetchall()

    has_next = len(rows) > page_size
    orders = rows[:page_size]

    # Construction des lignes du tableau
    if orders:
        html_rows = ""
        for o in orders:
            price_eur = o["prix"] or 0
            qty = o["quantity"] or 1
            total = price_eur * qty
            # final_key = o.get("final_key") or "-"  # pour plus tard si tu veux la réactiver
            dt = o.get("created_at")
            date_str = dt.strftime("%d/%m/%Y %H:%M") if dt else "-"

            html_rows += f"""
            <tr>
              <td>{o['order_id']}</td>
              <td>{o['email']}</td>
              <td>{o['offer_name']}</td>
              <td>{o['nbr_ticket']}</td>
              <td>{qty}</td>
              <td>{total:.2f} €</td>
              <!-- <td>{o['status']}</td> -->
              <!-- <td><code style="font-size:.7em">{o.get('final_key') or '-'}</code></td> -->
              <td>{date_str}</td>
            </tr>
            """
    else:
        # 7 colonnes visibles => colspan=7
        html_rows = """
        <tr>
          <td colspan="7" class="muted">Aucun billet pour ce statut.</td>
        </tr>
        """

    # Liens de filtre (paid / draft / canceled)
    labels = {
        "paid": "Payés",
        "draft": "Brouillons",
        "canceled": "Annulés",
    }
    status_links = []
    for s, label in labels.items():
        if s == status:
            status_links.append(f"<strong>{label}</strong>")
        else:
            status_links.append(f'<a href="/admin/orders?status={s}">{label}</a>')
    status_html = " | ".join(status_links)

    # Label pour le titre
    status_label = labels.get(status, "").lower()

    # Pagination
    nav = []
    if page > 1:
        nav.append(f'<a href="/admin/orders?status={status}&page={page-1}">← Page précédente</a>')
    if has_next:
        nav.append(f'<a href="/admin/orders?status={status}&page={page+1}">Page suivante →</a>')
    pagination_html = ""
    if nav:
        pagination_html = f"<div style='margin-top:12px; display:flex; gap:10px;'>{' '.join(nav)}</div>"

    # Charger le template HTML
    with open("static/admin_orders.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Remplacer les marqueurs
    html = html.replace("<!--STATUS_LABEL-->", f"({status_label})")
    html = html.replace("<!--STATUS_FILTERS-->", status_html)
    html = html.replace("<!--ROWS_HERE-->", html_rows)
    html = html.replace("<!--PAGINATION_HERE-->", pagination_html)

    return HTMLResponse(html)
#----------------------------------------------------------------------------------------------------------------------#
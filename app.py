import sqlite3, os, json
from flask import Flask, request, render_template, redirect, url_for, flash, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

# Initialisation de l'application Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Clé secrète pour sécuriser les sessions utilisateur

# Configuration de Flask-Login pour la gestion des utilisateurs
login_manager = LoginManager()
login_manager.init_app(app)  # Lier le gestionnaire de login à l'application
login_manager.login_view = 'login'  # Vue utilisée pour la page de connexion

# Classe représentant un utilisateur du système
class Utilisateur(UserMixin):
    def __init__(self, id, nom, email):
        self.id = id
        self.nom = nom
        self.email = email

# Classe représentant une cave à vin
class Cave:
    def __init__(self, id, nom, utilisateur_id):
        self.id = id
        self.nom = nom
        self.utilisateur_id = utilisateur_id  # Identifiant de l'utilisateur propriétaire de la cave

# Classe représentant une étagère dans une cave
class Etagere:
    def __init__(self, id, numero, emplacements_disponibles, nombre_bouteilles, cave_id):
        self.id = id
        self.numero = numero  # Numéro de l'étagère
        self.emplacements_disponibles = emplacements_disponibles  # Nombre d'emplacements libres sur l'étagère
        self.nombre_bouteilles = nombre_bouteilles  # Nombre de bouteilles présentes sur l'étagère
        self.cave_id = cave_id  # Référence à la cave à laquelle appartient l'étagère

# Classe représentant une bouteille
class Bouteille:
    def __init__(self, id, domaine, nom, type_vin, annee, region, commentaires, note_personnelle, note_moyenne, photo, prix, etagere_id):
        self.id = id
        self.domaine = domaine  # Domaine viticole de la bouteille
        self.nom = nom  # Nom du vin
        self.type_vin = type_vin  # Type de vin (ex. : rouge, blanc, rosé)
        self.annee = annee  # Année de production
        self.region = region  # Région de production
        self.commentaires = commentaires  # Commentaires personnels sur la bouteille
        self.note_personnelle = note_personnelle  # Note attribuée par l'utilisateur
        self.note_moyenne = note_moyenne  # Note moyenne de la bouteille (calculée à partir des notes personnelles)
        self.photo = photo  # URL de la photo de l'étiquette
        self.prix = prix  # Prix de la bouteille
        self.etagere_id = etagere_id  # Référence à l'étagère où se trouve la bouteille

# Classe représentant une bouteille archivée
class BouteilleArchivee:
    def __init__(self, id, domaine, nom, type_vin, annee, region, commentaires, note_personnelle, note_moyenne, photo, prix, date_archive):
        self.id = id
        self.domaine = domaine
        self.nom = nom
        self.type_vin = type_vin
        self.annee = annee
        self.region = region
        self.commentaires = commentaires
        self.note_personnelle = note_personnelle
        self.note_moyenne = note_moyenne
        self.photo = photo
        self.prix = prix
        self.date_archive = date_archive  # Date à laquelle la bouteille a été archivée

# Fonction Flask-Login pour charger un utilisateur à partir de son ID
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()  # Connexion à la base de données
    user = conn.execute('SELECT * FROM Utilisateur WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return Utilisateur(user['id'], user['nom'], user['email'])  # Créer un objet Utilisateur avec les informations récupérées
    return None

# Fonction utilitaire pour se connecter à la base de données SQLite
def get_db_connection():
    conn = sqlite3.connect('cave_a_vin.db')  # Connexion à la base de données
    conn.row_factory = sqlite3.Row  # Retourner les résultats sous forme de dictionnaire
    return conn

# Fonction pour initialiser la base de données (création des tables si elles n'existent pas)
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Création de la table Utilisateur
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Utilisateur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mot_de_passe TEXT NOT NULL
    )
    ''')
    # Création de la table Cave
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Cave (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        utilisateur_id INTEGER NOT NULL,
        FOREIGN KEY (utilisateur_id) REFERENCES Utilisateur (id)
    )
    ''')
    # Création de la table Etagere
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Etagere (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero INTEGER NOT NULL,
        emplacements_disponibles INTEGER NOT NULL,
        nombre_bouteilles INTEGER DEFAULT 0,
        cave_id INTEGER NOT NULL,
        FOREIGN KEY (cave_id) REFERENCES Cave (id)
    )
    ''')
    # Création de la table Bouteille
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Bouteille (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domaine TEXT NOT NULL,
        nom TEXT NOT NULL,
        type TEXT NOT NULL,
        annee INTEGER NOT NULL,
        region TEXT NOT NULL,
        photo TEXT,
        prix REAL NOT NULL,
        etagere_id INTEGER NOT NULL,
        FOREIGN KEY (etagere_id) REFERENCES Etagere (id)
    )
    ''')
    # Création de la table BouteilleArchivee
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS BouteilleArchivee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domaine TEXT NOT NULL,
        nom TEXT NOT NULL,
        type TEXT NOT NULL,
        annee INTEGER NOT NULL,
        region TEXT NOT NULL,
        commentaires TEXT,
        note_personnelle REAL NOT NULL,
        note_moyenne REAL,
        photo TEXT,
        prix REAL NOT NULL,
        date_archive DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

# Définition de la page d'accueil (index.html)
@app.route('/')
def index():
    if current_user.is_authenticated:  # Redirection vers la liste des caves si l'utilisateur est connecté
        return redirect(url_for('caves'))
    return render_template('index.html')  # Affichage de la page d'accueil pour les utilisateurs non connectés

# Route pour l'inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        conn = get_db_connection()
        # Insertion du nouvel utilisateur dans la base de données
        conn.execute('INSERT INTO Utilisateur (nom, email, mot_de_passe) VALUES (?, ?, ?)', (nom, email, mot_de_passe))
        conn.commit()
        conn.close()
        flash('Inscription réussie !')
        return redirect(url_for('login'))  # Redirection vers la page de connexion après inscription
    return render_template('register.html')

# Route pour la connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        mot_de_passe = request.form['mot_de_passe']
        conn = get_db_connection()
        # Vérification des informations de connexion
        user = conn.execute('SELECT * FROM Utilisateur WHERE email = ? AND mot_de_passe = ?', (email, mot_de_passe)).fetchone()
        conn.close()
        if user:
            login_user(Utilisateur(user['id'], user['nom'], user['email']))  # Connexion de l'utilisateur
            flash('Connexion réussie !')
            return redirect(url_for('caves'))
        else:
            flash('Email ou mot de passe incorrect.')
    return render_template('login.html')

# Route pour la déconnexion
@app.route('/logout')
@login_required  # Nécessite que l'utilisateur soit connecté
def logout():
    logout_user()  # Déconnexion de l'utilisateur
    flash('Déconnexion réussie !')
    return redirect(url_for('login'))

# Route pour afficher les caves de l'utilisateur connecté
@app.route('/caves')
@login_required
def caves():
    conn = get_db_connection()
    # Récupérer les caves et le nombre d'étagères par cave pour l'utilisateur connecté
    caves = conn.execute('''
        SELECT Cave.*, COUNT(Etagere.id) AS nombre_etageres
        FROM Cave
        LEFT JOIN Etagere ON Cave.id = Etagere.cave_id
        WHERE Cave.utilisateur_id = ?
        GROUP BY Cave.id
    ''', (current_user.id,)).fetchall()
    conn.close()
    return render_template('caves.html', caves=caves)

# Route pour ajouter une nouvelle cave
@app.route('/cave', methods=['POST'])
@login_required
def add_cave():
    nom_cave = request.form['nom']
    conn = get_db_connection()
    # Insertion de la nouvelle cave dans la base de données
    conn.execute('INSERT INTO Cave (nom, utilisateur_id) VALUES (?, ?)', (nom_cave, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('caves'))

# Route pour supprimer une cave et ses étagères et bouteilles associées
@app.route('/cave/<int:cave_id>/delete', methods=['POST'])
@login_required
def delete_cave(cave_id):
    conn = get_db_connection()
    # Récupérer toutes les étagères associées à cette cave
    etageres = conn.execute('SELECT id FROM Etagere WHERE cave_id = ?', (cave_id,)).fetchall()
    # Pour chaque étagère, supprimer les bouteilles associées
    for etagere in etageres:
        conn.execute('DELETE FROM Bouteille WHERE etagere_id = ?', (etagere['id'],))
    # Ensuite, supprimer toutes les étagères associées à la cave
    conn.execute('DELETE FROM Etagere WHERE cave_id = ?', (cave_id,))
    # Enfin, supprimer la cave elle-même
    conn.execute('DELETE FROM Cave WHERE id = ?', (cave_id,))
    conn.commit()
    conn.close()
    flash('Cave supprimée avec succès !')
    return redirect(url_for('caves'))

# Route pour exporter les données d'une cave en format JSON
@app.route('/cave/<int:cave_id>/export', methods=['GET'])
@login_required
def export_cave_json(cave_id):
    conn = get_db_connection()
    # Récupérer les informations de la cave
    cave = conn.execute('SELECT * FROM Cave WHERE id = ?', (cave_id,)).fetchone()
    etageres = conn.execute('SELECT * FROM Etagere WHERE cave_id = ?', (cave_id,)).fetchall()
    # Préparer les données à exporter
    cave_data = {
        "id": cave['id'],
        "nom": cave['nom'],
        "utilisateur_id": cave['utilisateur_id'],
        "etageres": []
    }
    for etagere in etageres:
        etagere_data = {
            "id": etagere['id'],
            "numero": etagere['numero'],
            "emplacements_disponibles": etagere['emplacements_disponibles'],
            "nombre_bouteilles": etagere['nombre_bouteilles'],
            "bouteilles": []
        }
        bouteilles = conn.execute('SELECT * FROM Bouteille WHERE etagere_id = ?', (etagere['id'],)).fetchall()
        for bouteille in bouteilles:
            bouteille_data = {
                "id": bouteille['id'],
                "domaine": bouteille['domaine'],
                "nom": bouteille['nom'],
                "type": bouteille['type'],
                "annee": bouteille['annee'],
                "region": bouteille['region'],
                "photo": bouteille['photo'],
                "prix": bouteille['prix']
            }
            etagere_data["bouteilles"].append(bouteille_data)
        cave_data["etageres"].append(etagere_data)
    conn.close()
    nom_cave = cave['nom'].replace(' ', '_').replace('/', '_')
    response = make_response(json.dumps(cave_data, indent=4))
    response.headers['Content-Disposition'] = f'attachment;filename={nom_cave}.json'
    response.headers['Content-Type'] = 'application/json'
    return response

# Route pour afficher les étagères dans une cave
@app.route('/cave/<int:cave_id>')
@login_required
def view_cave(cave_id):
    conn = get_db_connection()
    cave = conn.execute('SELECT * FROM Cave WHERE id = ?', (cave_id,)).fetchone()
    etageres = conn.execute('SELECT * FROM Etagere WHERE cave_id = ?', (cave_id,)).fetchall()
    conn.close()
    return render_template('etageres.html', cave=cave, etageres=etageres)

# Route pour ajouter une nouvelle étagère à une cave
@app.route('/etagere', methods=['POST'])
@login_required
def add_etagere():
    cave_id = request.form['cave_id']
    numero = request.form['numero']
    emplacements_disponibles = request.form['emplacements_disponibles']
    conn = get_db_connection()
    # Insertion de l'étagère dans la base de données
    conn.execute('INSERT INTO Etagere (numero, emplacements_disponibles, cave_id) VALUES (?, ?, ?)', (numero, emplacements_disponibles, cave_id))
    conn.commit()
    conn.close()
    flash('Étagère ajoutée avec succès !')
    return redirect(url_for('view_cave', cave_id=cave_id))

# Route pour supprimer une étagère et ses bouteilles associées
@app.route('/etagere/<int:etagere_id>/delete', methods=['POST'])
@login_required
def delete_etagere(etagere_id):
    conn = get_db_connection()
    cave_id = conn.execute('SELECT cave_id FROM Etagere WHERE id = ?', (etagere_id,)).fetchone()['cave_id']
    # Suppression des bouteilles associées à l'étagère
    conn.execute('DELETE FROM Bouteille WHERE etagere_id = ?', (etagere_id,))
    # Suppression de l'étagère elle-même
    conn.execute('DELETE FROM Etagere WHERE id = ?', (etagere_id,))
    conn.commit()
    conn.close()
    flash('Étagère supprimée avec succès !')
    return redirect(url_for('view_cave', cave_id=cave_id))

# Vérification si une photo a une extension autorisée
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route pour gérer les bouteilles sur une étagère (affichage et ajout)
@app.route('/etagere/<int:etagere_id>/bouteilles', methods=['GET', 'POST'])
@login_required
def manage_bottles(etagere_id):
    conn = get_db_connection()
    etagere = conn.execute('SELECT * FROM Etagere WHERE id = ?', (etagere_id,)).fetchone()
    # Gestion du tri des bouteilles
    sort_by = request.args.get('sort_by', 'nom')  # Tri par défaut par nom
    sort_order = request.args.get('sort_order', 'ASC')  # Ordre de tri par défaut croissant
    query = f'SELECT * FROM Bouteille WHERE etagere_id = ? ORDER BY {sort_by} {sort_order}'
    bouteilles = conn.execute(query, (etagere_id,)).fetchall()
    # Vérification si l'étagère est pleine
    etagere_pleine = etagere['emplacements_disponibles'] == 0
    if request.method == 'POST':
        # Récupération des données du formulaire
        domaine = request.form['domaine']
        nom = request.form['nom']
        type_vin = request.form['type']
        annee = int(request.form['annee'])
        region = request.form['region']
        prix = float(request.form['prix'])
        image = request.files['image']
        # Vérification et sauvegarde de l'image si elle est valide
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join('static/uploads', filename)
            image.save(os.path.join(app.root_path, image_path))
            image_url = f'uploads/{filename}'
        else:
            image_url = None  # Si aucune image n'est fournie, enregistrer None
        # Insertion de la bouteille dans la base de données
        conn.execute('''
        INSERT INTO Bouteille (domaine, nom, type, annee, region, photo, prix, etagere_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (domaine, nom, type_vin, annee, region, image_url, prix, etagere_id))
        # Mise à jour des informations sur l'étagère (nombre de bouteilles et emplacements)
        conn.execute('UPDATE Etagere SET nombre_bouteilles = nombre_bouteilles + 1 WHERE id = ?', (etagere_id,))
        conn.execute('UPDATE Etagere SET emplacements_disponibles = emplacements_disponibles - 1 WHERE id = ?', (etagere_id,))
        conn.commit()
        conn.close()
        flash('Bouteille ajoutée avec succès et emplacement mis à jour !')
        return redirect(url_for('manage_bottles', etagere_id=etagere_id))
    conn.close()
    next_order = 'DESC' if sort_order == 'ASC' else 'ASC'
    return render_template('bouteilles.html', etagere=etagere, bouteilles=bouteilles, next_order=next_order, sort_by=sort_by, etagere_pleine=etagere_pleine)

# Route pour supprimer une bouteille
@app.route('/bouteille/<int:bouteille_id>/delete', methods=['POST'])
@login_required
def delete_bottle(bouteille_id):
    conn = get_db_connection()
    etagere_id = conn.execute('SELECT etagere_id FROM Bouteille WHERE id = ?', (bouteille_id,)).fetchone()['etagere_id']
    # Suppression de la bouteille de la base de données
    conn.execute('DELETE FROM Bouteille WHERE id = ?', (bouteille_id,))
    # Mise à jour de l'étagère
    conn.execute('UPDATE Etagere SET nombre_bouteilles = nombre_bouteilles - 1 WHERE id = ?', (etagere_id,))
    conn.execute('UPDATE Etagere SET emplacements_disponibles = emplacements_disponibles + 1 WHERE id = ?', (etagere_id,))
    conn.commit()
    conn.close()
    flash('Bouteille supprimée et emplacement mis à jour !')
    return redirect(url_for('manage_bottles', etagere_id=etagere_id))

# Route pour archiver une bouteille
@app.route('/bouteille/<int:bouteille_id>/archive', methods=['POST'])
@login_required
def archive_bottle(bouteille_id):
    conn = get_db_connection()
    # Récupérer les informations de la bouteille à archiver
    etagere_id = conn.execute('SELECT etagere_id FROM Bouteille WHERE id = ?', (bouteille_id,)).fetchone()['etagere_id']
    bouteille = conn.execute('SELECT * FROM Bouteille WHERE id = ?', (bouteille_id,)).fetchone()
    note_perso = float(request.form['note_perso'])
    commentaires = request.form['commentaires']
    commentaires_complet = f"{current_user.nom} : {commentaires}" if commentaires else f"{current_user.nom} : Pas de commentaire"
    # Archiver la bouteille
    conn.execute('''
    INSERT INTO BouteilleArchivee (domaine, nom, type, annee, region, commentaires, note_personnelle, note_moyenne, photo, prix, date_archive)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        bouteille['domaine'], bouteille['nom'], bouteille['type'], bouteille['annee'], bouteille['region'],
        commentaires_complet, note_perso, note_perso, bouteille['photo'], bouteille['prix']
    ))
    # Calcul de la note moyenne pour les bouteilles archivées similaires
    note_moyenne = conn.execute('''
        SELECT AVG(note_personnelle) AS note_moyenne
        FROM BouteilleArchivee
        WHERE domaine = ? AND nom = ? AND type = ? AND annee = ? AND region = ?
    ''', (bouteille['domaine'], bouteille['nom'], bouteille['type'], bouteille['annee'], bouteille['region'])).fetchone()['note_moyenne']
    # Mise à jour de la note moyenne pour les bouteilles archivées similaires
    conn.execute('''
        UPDATE BouteilleArchivee
        SET note_moyenne = ?
        WHERE domaine = ? AND nom = ? AND type = ? AND annee = ? AND region = ?
    ''', (note_moyenne, bouteille['domaine'], bouteille['nom'], bouteille['type'], bouteille['annee'], bouteille['region']))
    # Suppression de la bouteille de la cave
    conn.execute('DELETE FROM Bouteille WHERE id = ?', (bouteille_id,))
    # Mise à jour de l'étagère
    conn.execute('UPDATE Etagere SET nombre_bouteilles = nombre_bouteilles - 1 WHERE id = ?', (etagere_id,))
    conn.execute('UPDATE Etagere SET emplacements_disponibles = emplacements_disponibles + 1 WHERE id = ?', (etagere_id,))
    conn.commit()
    conn.close()
    flash('Bouteille archivée avec succès et emplacement mis à jour !')
    return redirect(url_for('manage_bottles', etagere_id=etagere_id))

# Route pour afficher les bouteilles archivées
@app.route('/archive')
def view_archive():
    conn = get_db_connection()
    sort_by = request.args.get('sort_by', 'nom')  # Tri par défaut par nom
    sort_order = request.args.get('sort_order', 'ASC')  # Ordre de tri par défaut croissant
    query = f'SELECT * FROM BouteilleArchivee ORDER BY {sort_by} {sort_order}'
    bouteilles = conn.execute(query).fetchall()
    conn.close()
    next_order = 'DESC' if sort_order == 'ASC' else 'ASC'
    return render_template('bouteillesarchivees.html', bouteilles=bouteilles, next_order=next_order, sort_by=sort_by)

# Point d'entrée de l'application
if __name__ == '__main__':
    init_db()  # Initialiser la base de données au démarrage de l'application
    app.run(debug=True)  # Démarrer l'application en mode débogage
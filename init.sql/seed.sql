-- ============================================================
-- HealthAI Coach — Seeds de développement
-- ============================================================

-- Utilisateur de test
INSERT INTO utilisateur (nom, prenom, email, date_de_naissance, genre, mot_de_passe_hash)
VALUES ('Dupont', 'Jean', 'jean.dupont@healthai.dev', '1995-06-15', 'Masculin', '$2b$10$placeholder_bcrypt_hash');

-- Profil santé associé
INSERT INTO profil_sante (id_utilisateur, poids_kg, taille_cm, imc, niveau_activite, objectif_principal)
VALUES (1, 85.5, 180, 26.4, 'Modéré', 'Perte de poids');

-- Aliments de test
INSERT INTO aliment (nom, calories, proteines, lipides, glucides, type_repas)
VALUES
    ('Pomme',          52.0,  0.3,  0.2, 14.0, 'collation'),
    ('Poulet grillé', 165.0, 31.0,  3.6,  0.0, 'déjeuner'),
    ('Riz blanc cuit', 130.0,  2.7,  0.3, 28.0, 'déjeuner'),
    ('Oeuf entier',   155.0, 13.0, 11.0,  1.1, 'petit-déjeuner');

-- Exercices de test
INSERT INTO exercice (nom, type_exercice, muscles_principaux, equipement, difficulte)
VALUES
    ('Pompes',        'Force',  'Pectoraux',  'Aucun', 'Débutant'),
    ('Squat',         'Force',  'Quadriceps', 'Aucun', 'Débutant'),
    ('Course à pied', 'Cardio', NULL,         'Aucun', 'Intermédiaire'),
    ('Planche',       'Gainage','Abdominaux', 'Aucun', 'Débutant');

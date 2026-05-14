-- ============================================================
-- HealthAI Coach — Schéma PostgreSQL
-- Source de vérité : healthai-etl/src/data_pipeline/models.py
-- Les entités TypeORM (healthai-api) s'y conforment également.
-- NE PAS modifier sans mettre à jour models.py en parallèle.
-- ============================================================

-- ========================
-- TABLES RÉFÉRENTIELS
-- ========================

CREATE TABLE utilisateur (
    id_utilisateur    SERIAL PRIMARY KEY,
    nom               VARCHAR(50)  NOT NULL,
    prenom            VARCHAR(50)  NOT NULL,
    email             VARCHAR(255) NOT NULL UNIQUE,
    date_de_naissance DATE         NOT NULL,
    genre             VARCHAR(50)  NOT NULL,
    mot_de_passe_hash VARCHAR(255) NOT NULL,
    type_abonnement   VARCHAR(50)  DEFAULT 'Freemium',
    date_inscription  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_utilisateur_id_utilisateur ON utilisateur (id_utilisateur);
CREATE UNIQUE INDEX ix_utilisateur_email ON utilisateur (email);

CREATE TABLE profil_sante (
    id_profil                  SERIAL PRIMARY KEY,
    id_utilisateur             INTEGER UNIQUE NOT NULL REFERENCES utilisateur (id_utilisateur) ON DELETE CASCADE,
    poids_kg                   NUMERIC(5, 2),
    taille_cm                  INTEGER,
    imc                        NUMERIC(4, 1),
    niveau_activite            VARCHAR(100),
    type_maladie               VARCHAR(255),
    severite                   VARCHAR(50),
    restrictions_alimentaires  TEXT,
    allergies                  TEXT,
    objectif_principal         VARCHAR(200),
    experience_sportive        VARCHAR(100),
    frequence_entrainement     INTEGER
);
CREATE INDEX ix_profil_sante_id_profil ON profil_sante (id_profil);

CREATE TABLE aliment (
    id_aliment     SERIAL PRIMARY KEY,
    nom            VARCHAR(255)   NOT NULL,
    categorie      VARCHAR(100),
    type_repas     VARCHAR(50),
    calories       NUMERIC(6, 1)  NOT NULL,
    proteines      NUMERIC(5, 2)  NOT NULL,
    lipides        NUMERIC(5, 2)  NOT NULL,
    glucides       NUMERIC(5, 2)  NOT NULL,
    fibres         NUMERIC(5, 2),
    sucres         NUMERIC(5, 2),
    sodium_mg      NUMERIC(7, 2),
    cholesterol_mg NUMERIC(7, 2),
    eau_ml         NUMERIC(7, 2),
    unite_mesure   VARCHAR(50)    DEFAULT 'portion'
);
CREATE INDEX ix_aliment_id_aliment ON aliment (id_aliment);

CREATE TABLE exercice (
    id_exercice   SERIAL PRIMARY KEY,
    nom                 VARCHAR(150) NOT NULL,
    type_exercice       VARCHAR(100) NOT NULL,
    muscles_principaux  VARCHAR(100),
    muscles_secondaires VARCHAR(100),
    equipement          VARCHAR(100),
    difficulte    VARCHAR(50),
    instructions  TEXT
);
CREATE INDEX ix_exercice_id_exercice ON exercice (id_exercice);

-- ========================
-- TABLES DE LOGS
-- ========================

CREATE TABLE log_aliment (
    id_log_aliment SERIAL PRIMARY KEY,
    log_date       TIMESTAMP     NOT NULL,
    repas          VARCHAR(50)   NOT NULL,
    quantite       NUMERIC(7, 2) NOT NULL,
    unite          VARCHAR(20)   DEFAULT 'g',
    id_aliment     INTEGER       NOT NULL REFERENCES aliment (id_aliment),
    id_utilisateur INTEGER       NOT NULL REFERENCES utilisateur (id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX ix_log_aliment_id_log_aliment ON log_aliment (id_log_aliment);

CREATE TABLE log_seance (
    id_seance_log  SERIAL PRIMARY KEY,
    log_date       TIMESTAMP     NOT NULL,
    type_seance    VARCHAR(50),
    duree_minutes  NUMERIC(5, 1) NOT NULL,
    calorie_brulee NUMERIC(6, 1) NOT NULL,
    bpm_moyen      INTEGER,
    id_exercice    INTEGER       REFERENCES exercice (id_exercice),
    id_utilisateur INTEGER       NOT NULL REFERENCES utilisateur (id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX ix_log_seance_id_seance_log ON log_seance (id_seance_log);

CREATE TABLE log_sante (
    id_log_sante        SERIAL PRIMARY KEY,
    date_log            TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    poids_kg            NUMERIC(5, 2),
    pourcentage_gras    NUMERIC(4, 1),
    imc_actuel          NUMERIC(4, 1),
    bpm_repos           INTEGER,
    bpm_moyen_journee   INTEGER,
    heures_sommeil      NUMERIC(4, 2),
    nb_pas              INTEGER,
    hydratation_litres  NUMERIC(4, 2),
    id_utilisateur      INTEGER NOT NULL REFERENCES utilisateur (id_utilisateur) ON DELETE CASCADE
);
CREATE INDEX ix_log_sante_id_log_sante ON log_sante (id_log_sante);

-- ========================
-- TABLES DATASETS ETL
-- ========================

CREATE TABLE dataset_recommendations_regime (
    id_dataset_recommendations_regime SERIAL PRIMARY KEY,
    age                               INTEGER,
    sexe                              VARCHAR(50),
    poids_kg                          NUMERIC(5, 2),
    taille_cm                         INTEGER,
    type_maladie                      VARCHAR(255),
    gravite                           VARCHAR(50),
    niveau_activite_physique          VARCHAR(100),
    apport_calorique_journalier       INTEGER,
    cholesterol_mg_dl                 NUMERIC(6, 2),
    tension_arterielle_mmhg           NUMERIC(6, 2),
    glucose_mg_dl                     NUMERIC(6, 2),
    restrictions_alimentaires         VARCHAR(255),
    allergies                         VARCHAR(255),
    cuisine_preferee                  VARCHAR(100),
    heures_exercice_semaine           NUMERIC(4, 2),
    adherence_regime                  NUMERIC(4, 2),
    score_desiquilibre_nutriment      NUMERIC(4, 1),
    recommendation_regime             VARCHAR(255)
);
CREATE INDEX ix_dataset_recommendations_regime_id ON dataset_recommendations_regime (id_dataset_recommendations_regime);

CREATE TABLE dataset_historique_seance_exercice (
    id_dataset_historique_seance_exercice SERIAL PRIMARY KEY,
    age                                   INTEGER,
    sexe                                  VARCHAR(50),
    poids_kg                              NUMERIC(5, 2),
    taille_cm                             INTEGER,
    bpm_max                               INTEGER,
    bpm_moyen                             INTEGER,
    bpm_repos                             INTEGER,
    duree_seance_minutes                  NUMERIC(5, 1),
    calories_brulees                      NUMERIC(6, 1),
    type_sport                            VARCHAR(100),
    pourcentage_gras                      NUMERIC(4, 1),
    consommation_eau_l                    NUMERIC(4, 1),
    frequence_sport_jour_semaine          INTEGER,
    niveau_experience                     INTEGER
);
CREATE INDEX ix_dataset_historique_seance_exercice_id ON dataset_historique_seance_exercice (id_dataset_historique_seance_exercice);

-- ========================
-- TABLES CONFIG ETL PIPELINE
-- ========================

CREATE TYPE file_extension_enum AS ENUM ('csv', 'json');
CREATE TYPE file_name_variable_enum AS ENUM ('YYYY', 'YYYYMMDD', 'YYYYMMDD_HHmm');
CREATE TYPE column_type_enum AS ENUM ('INT', 'DECIMAL', 'STRING', 'DATE', 'BOOLEAN', 'TIMESTAMP');

CREATE TABLE etl_pipeline (
    id_etl_pipeline      SERIAL PRIMARY KEY,
    libelle              VARCHAR(255) NOT NULL UNIQUE,
    table_nom            VARCHAR(100) NOT NULL,
    dossier_emplacement  VARCHAR(512) NOT NULL,
    nom_fichier_fixe     VARCHAR(100) NOT NULL,
    nom_fichier_variable file_name_variable_enum,
    extension_fichier    file_extension_enum NOT NULL,
    active               BOOLEAN      DEFAULT true,
    date_creation        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_etl_pipeline_table_nom ON etl_pipeline (table_nom);

CREATE TABLE etl_column_mapping (
    id_etl_column_mapping SERIAL PRIMARY KEY,
    id_etl_pipeline       INTEGER      NOT NULL REFERENCES etl_pipeline (id_etl_pipeline) ON DELETE CASCADE,
    colonne_bdd           VARCHAR(100) NOT NULL,
    colonne_fichier       VARCHAR(100),
    in_file               BOOLEAN      DEFAULT true,
    type_donnees          column_type_enum NOT NULL,
    nullable              BOOLEAN      DEFAULT false,
    valeur_defaut         VARCHAR(500),
    unique_constraint     BOOLEAN      DEFAULT false,
    date_creation         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_etl_column_mapping_pipeline ON etl_column_mapping (id_etl_pipeline);

CREATE TABLE etl_column_string_constraints (
    id_string_constraint  SERIAL PRIMARY KEY,
    id_etl_column_mapping INTEGER NOT NULL UNIQUE REFERENCES etl_column_mapping (id_etl_column_mapping) ON DELETE CASCADE,
    caract_min_lenght     INTEGER DEFAULT 0,
    caract_max_lenght     INTEGER NOT NULL
);

CREATE TABLE etl_column_numeric_constraints (
    id_numeric_constraint SERIAL PRIMARY KEY,
    id_etl_column_mapping INTEGER      NOT NULL UNIQUE REFERENCES etl_column_mapping (id_etl_column_mapping) ON DELETE CASCADE,
    nb_min                NUMERIC(20, 4),
    nb_max                NUMERIC(20, 4),
    nb_decimal            INTEGER
);

CREATE TABLE etl_column_date_constraints (
    id_date_constraint    SERIAL PRIMARY KEY,
    id_etl_column_mapping INTEGER   NOT NULL UNIQUE REFERENCES etl_column_mapping (id_etl_column_mapping) ON DELETE CASCADE,
    date_min              TIMESTAMP,
    date_max              TIMESTAMP
);

CREATE TABLE etl_log (
    id_etl_log          SERIAL PRIMARY KEY,
    id_etl_pipeline     INTEGER      NOT NULL REFERENCES etl_pipeline (id_etl_pipeline) ON DELETE CASCADE,
    fichier_nom         VARCHAR(255) NOT NULL,
    date_execution      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    nb_lignes_total     INTEGER      DEFAULT 0,
    nb_lignes_valides   INTEGER      DEFAULT 0,
    nb_lignes_anomalies INTEGER      DEFAULT 0,
    statut              VARCHAR(50)  DEFAULT 'PENDING',
    message_erreur      TEXT
);
CREATE INDEX ix_etl_log_pipeline ON etl_log (id_etl_pipeline);

-- ========================
-- TABLES ANOMALIES IMPORT
-- ========================

CREATE TABLE utilisateur_import_anomalies (
    id                SERIAL PRIMARY KEY,
    nom               VARCHAR(1000),
    prenom            VARCHAR(1000),
    email             VARCHAR(1000),
    date_de_naissance VARCHAR(1000),
    genre             VARCHAR(1000),
    mot_de_passe_hash VARCHAR(1000),
    type_abonnement   VARCHAR(1000),
    date_inscription  VARCHAR(1000),
    erreur            TEXT         NOT NULL,
    est_corrige       BOOLEAN      NOT NULL DEFAULT false,
    date_import       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE profil_sante_import_anomalies (
    id                            SERIAL PRIMARY KEY,
    id_profil                     VARCHAR(1000),
    id_utilisateur                VARCHAR(1000),
    poids_kg                      VARCHAR(1000),
    taille_cm                     VARCHAR(1000),
    imc                           VARCHAR(1000),
    niveau_activite               VARCHAR(1000),
    type_maladie                  VARCHAR(1000),
    severite                      VARCHAR(1000),
    restrictions_alimentaires     VARCHAR(1000),
    allergies                     VARCHAR(1000),
    objectif_principal            VARCHAR(1000),
    experience_sportive           VARCHAR(1000),
    frequence_entrainement        VARCHAR(1000),
    erreur                        TEXT         NOT NULL,
    est_corrige                   BOOLEAN      NOT NULL DEFAULT false,
    date_import                   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aliment_import_anomalies (
    id             SERIAL PRIMARY KEY,
    nom            VARCHAR(1000),
    categorie      VARCHAR(1000),
    type_repas     VARCHAR(1000),
    calories       VARCHAR(1000),
    proteines      VARCHAR(1000),
    lipides        VARCHAR(1000),
    glucides       VARCHAR(1000),
    fibres         VARCHAR(1000),
    sucres         VARCHAR(1000),
    sodium_mg      VARCHAR(1000),
    cholesterol_mg VARCHAR(1000),
    unite_mesure   VARCHAR(1000),
    erreur         TEXT         NOT NULL,
    est_corrige    BOOLEAN      NOT NULL DEFAULT false,
    date_import    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exercice_import_anomalies (
    id            SERIAL PRIMARY KEY,
    nom           VARCHAR(1000),
    type_exercice VARCHAR(1000),
    muscle_cible  VARCHAR(1000),
    equipement    VARCHAR(1000),
    difficulte    VARCHAR(1000),
    instructions  VARCHAR(1000),
    erreur        TEXT         NOT NULL,
    est_corrige   BOOLEAN      NOT NULL DEFAULT false,
    date_import   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_recommendations_regime_import_anomalies (
    id                               SERIAL PRIMARY KEY,
    age                              VARCHAR(1000),
    sexe                             VARCHAR(1000),
    poids_kg                         VARCHAR(1000),
    taille_cm                        VARCHAR(1000),
    type_maladie                     VARCHAR(1000),
    gravite                          VARCHAR(1000),
    niveau_activite_physique         VARCHAR(1000),
    apport_calorique_journalier      VARCHAR(1000),
    cholesterol_mg_dl                VARCHAR(1000),
    tension_arterielle_mmhg          VARCHAR(1000),
    glucose_mg_dl                    VARCHAR(1000),
    restrictions_alimentaires        VARCHAR(1000),
    allergies                        VARCHAR(1000),
    cuisine_preferee                 VARCHAR(1000),
    heures_exercice_semaine          VARCHAR(1000),
    adherence_regime                 VARCHAR(1000),
    score_desiquilibre_nutriment     VARCHAR(1000),
    recommendation_regime            VARCHAR(1000),
    erreur                           TEXT         NOT NULL,
    est_corrige                      BOOLEAN      NOT NULL DEFAULT false,
    date_import                      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dataset_historique_seance_exercice_import_anomalies (
    id                                    SERIAL PRIMARY KEY,
    age                                   VARCHAR(1000),
    sexe                                  VARCHAR(1000),
    poids_kg                              VARCHAR(1000),
    taille_cm                             VARCHAR(1000),
    bpm_max                               VARCHAR(1000),
    bpm_moyen                             VARCHAR(1000),
    bpm_repos                             VARCHAR(1000),
    duree_seance_minutes                  VARCHAR(1000),
    calories_brulees                      VARCHAR(1000),
    type_sport                            VARCHAR(1000),
    pourcentage_gras                      VARCHAR(1000),
    consommation_eau_l                    VARCHAR(1000),
    frequence_sport_jour_semaine          VARCHAR(1000),
    niveau_experience                     VARCHAR(1000),
    erreur                                TEXT         NOT NULL,
    est_corrige                           BOOLEAN      NOT NULL DEFAULT false,
    date_import                           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

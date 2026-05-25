"""Schémas des endpoints IA Ollama : generate-session, evaluate-sessions, explain-exercises.

Convention : en ENTRÉE les champs d'exercice sont optionnels (le front peut envoyer des
valeurs partielles) ; en SORTIE (réponse du LLM) on attend des champs renseignés.
"""

from datetime import datetime

from pydantic import BaseModel, Field

# --- Exercice (forme commune) ---------------------------------------------------

class ExerciceIn(BaseModel):
    """Exercice fourni en entrée : tout est optionnel sauf le nom."""

    nom: str = Field(..., max_length=200)
    type: str | None = Field(None, max_length=50)
    series: int | None = None
    repetitions: int | None = None
    duree_secondes: int | None = None
    repos_secondes: int | None = None
    muscles_cibles: str | None = Field(None, max_length=200)


class ExerciceOut(BaseModel):
    """Exercice produit par le LLM : on attend les champs principaux renseignés."""

    nom: str
    type: str | None = None
    series: int | None = None
    repetitions: int | None = None
    duree_secondes: int | None = None
    repos_secondes: int | None = None
    muscles_cibles: str | None = None


# --- generate-session -----------------------------------------------------------

class GenerateSessionRequest(BaseModel):
    duree_souhaitee_minutes: int | None = Field(None, gt=0, le=180)  # 3 h max
    equipement_disponible: list[str] | None = Field(None, max_length=30)
    focus_musculaire: str | None = Field(None, max_length=100)


class GenerateSessionResponse(BaseModel):
    # Renseignés seulement si la séance a été sauvegardée en base (sauvegarder=true)
    id_seance_log: int | None = None
    log_date: datetime | None = None
    statut: str | None = None

    # Champs secondaires : valeurs par défaut pour rester robuste aux petits modèles
    # (clé manquante ou mal orthographiée côté LLM). Seuls les `exercices` sont exigés.
    type_seance: str = "Non précisé"
    titre_seance: str = "Séance personnalisée"
    duree_minutes: int = 45
    difficulte: str = "Intermédiaire"
    objectif: str = ""
    conseils_generaux: str = ""
    exercices: list[ExerciceOut] = Field(..., min_length=1)


# --- evaluate-sessions ----------------------------------------------------------

class EvaluateSessionsRequest(BaseModel):
    # On évalue des séances déjà enregistrées : on ne transmet que leurs ids.
    ids_seances: list[int] = Field(..., min_length=1, max_length=20)


class AvisSeance(BaseModel):
    index: int = 0
    points_positifs: list[str] = Field(default_factory=list)
    points_amelioration: list[str] = Field(default_factory=list)
    suggestion: str = ""


class EvaluateSessionsResponse(BaseModel):
    avis_global: str = ""
    note_globale: int = Field(default=3, ge=1, le=5)
    avis_par_seance: list[AvisSeance] = Field(..., min_length=1)


# --- explain-exercises ----------------------------------------------------------

class ExplainExercisesRequest(BaseModel):
    exercices: list[ExerciceIn] = Field(..., min_length=1, max_length=20)


class ExplicationExercice(BaseModel):
    nom: str
    description: str = ""
    muscles_cibles: str = ""
    technique: str = ""
    erreurs_courantes: list[str] = Field(default_factory=list)
    variantes: list[str] | None = None
    conseils_securite: str = ""


class ExplainExercisesResponse(BaseModel):
    explications: list[ExplicationExercice] = Field(..., min_length=1)

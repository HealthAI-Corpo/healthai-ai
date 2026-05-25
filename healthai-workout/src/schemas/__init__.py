from pydantic import BaseModel, Field


class ModelInfoResponse(BaseModel):
    model_name: str = Field(default="CaloriesIA_1_0_0")
    model_version: str = Field(default="1.0.0")
    features_required: list[str] = Field(...)
    model_type: str = Field(default="RandomForest")
    training_date: str = Field(default="2026-05-22")
    status: str = Field(default="PRODUCTION")
    n_samples_test: int = Field(default=491)


class MetricsResponse(BaseModel):
    r2_score: float = Field(...)
    mae: float = Field(...)
    rmse: float = Field(...)
    mape: float = Field(...)
    model_version: str = Field(default="1.0.0")


class CalorieEstimationRequest(BaseModel):
    imc: float = Field(..., gt=0, description="Indice de Masse Corporelle")
    age: int = Field(..., gt=0, lt=150, description="Âge du pratiquant")
    sexe: str = Field(..., pattern="^[MFmf]$", description="Sexe: M ou F")
    bpm_max: float = Field(..., gt=0, description="BPM maximal pendant la séance")
    bpm_moyen: float = Field(..., gt=0, description="BPM moyen pendant la séance")
    bpm_repos: float = Field(..., gt=0, description="BPM au repos")
    duree_seance_minutes: float = Field(..., gt=0, description="Durée de la séance en minutes")
    type_sport: str = Field(..., description="Type de sport: Cardio/HIIT ou Strength/Yoga")
    pourcentage_gras: float = Field(
        ..., ge=0, le=100, description="Pourcentage de graisse corporelle"
    )  # noqa: E501
    consommation_eau_ml: float = Field(..., ge=0, description="Eau consommée en ml")
    niveau_experience: int = Field(..., ge=0, le=5, description="Niveau d'expérience (0-5)")


class CalorieEstimationResponse(BaseModel):
    prediction: float = Field(...)
    model_version: str = Field(default="1.0.0")
    features_used: int = Field(default=11)
    model_name: str = Field(default="CaloriesIA_1_0_0")


class CalorieEstimationWithDefaultsRequest(BaseModel):
    imc: float | None = Field(None, gt=0)
    age: int | None = Field(None, gt=0, lt=150)
    sexe: str | None = Field(None, pattern="^[MFmf]$")
    bpm_max: float | None = Field(None, gt=0)
    bpm_moyen: float | None = Field(None, gt=0)
    bpm_repos: float | None = Field(None, gt=0)
    duree_seance_minutes: float | None = Field(None, gt=0)
    type_sport: str | None = Field(None)
    pourcentage_gras: float | None = Field(None, ge=0, le=100)
    consommation_eau_ml: float | None = Field(None, ge=0)
    niveau_experience: int | None = Field(None, ge=0, le=5)


class CalorieEstimationWithDefaultsResponse(BaseModel):
    prediction: float = Field(...)
    model_version: str = Field(default="1.0.0")
    features_used: int = Field(default=11)
    model_name: str = Field(default="CaloriesIA_1_0_0")
    imputed_features: dict = Field(default_factory=dict)
    original_values: dict = Field(default_factory=dict)

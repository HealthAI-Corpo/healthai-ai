import io

from PIL import Image
from ultralytics import YOLO


class AIService:
    def __init__(self):
        # Charge le modèle Nano (le plus rapide pour le CPU)
        # Il sera téléchargé automatiquement dans le conteneur lors du premier appel
        self.model = YOLO("yolov8n.pt")

    def analyze_image(self, image_bytes: bytes):
        img = Image.open(io.BytesIO(image_bytes))
        results = self.model(img)

        detections = []

        for r in results:
            for box in r.boxes:
                # 1. On récupère d'abord la confiance
                confidence = round(float(box.conf), 2)

                # 2. On vérifie le seuil (Threshold)
                if confidence > 0.5:
                    detections.append(
                        {
                            "label": r.names[int(box.cls)],
                            "confidence": confidence,
                            "box": [round(x, 1) for x in box.xyxy[0].tolist()],
                        }
                    )

        return detections


# On crée une instance unique
ai_service = AIService()

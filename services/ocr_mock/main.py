from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="OCR Mock")


@app.post("/ocr")
async def perform_ocr(payload: dict):
    return {
        "merchant": "Pharmacy UA",
        "purchase_ts": "2025-11-30T10:00:00+00:00",
        "total": 2500,
        "line_items": [
            {"name": "Darnitsa Citramon", "quantity": 1, "price": 1000, "confidence": 0.95},
            {"name": "Water", "quantity": 1, "price": 1500, "confidence": 0.7},
        ],
    }


def run():
    import uvicorn

    uvicorn.run("services.ocr_mock.main:app", host="0.0.0.0", port=8081)


if __name__ == "__main__":
    run()


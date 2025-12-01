from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI

app = FastAPI(title="EasyPay Mock")


@app.post("/topup")
async def topup(payload: dict):
    return {"status": "success", "transaction_id": str(uuid4())}


def run():
    import uvicorn

    uvicorn.run("services.easypay_mock.main:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()


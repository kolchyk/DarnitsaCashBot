from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request, Response

app = FastAPI(title="PortmoneDirect Mock")


@app.post("/api/directcash/")
async def directcash(request: Request) -> Response:
    form = await request.form()
    method = form.get("method")

    if method == "bills.create":
        bill_id = str(uuid4())
        contract_number = form.get("contractNumber", "")
        payload = (
            "<rsp status=\"ok\">"
            f"<bill><billId>{bill_id}</billId><contractNumber>{contract_number}</contractNumber></bill>"
            "</rsp>"
        )
        return Response(content=payload, media_type="application/xml")

    error_xml = '<rsp status="fail"><error code="400">Unknown method</error></rsp>'
    return Response(content=error_xml, media_type="application/xml", status_code=400)


def run():  # pragma: no cover - dev helper
    import uvicorn

    uvicorn.run("services.portmone_mock.main:app", host="0.0.0.0", port=8082)


if __name__ == "__main__":
    run()


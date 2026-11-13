import os
import time
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI(
    title="Sample Payment Service",
    description="Mock target microservice used for testing Chaos Probe fault injection.",
    version="1.0.0",
)

service_name = os.getenv("SERVICE_NAME", "sample-payment-service")
simulated_delay = float(os.getenv("SIMULATED_DELAY_SECONDS", "0.0"))
is_degraded = False


class PaymentRequest(BaseModel):
    amount: float
    currency: str = "USD"
    customer_id: str


@app.get("/health")
def health() -> dict[str, str]:
    if is_degraded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is currently experiencing internal degraded health",
        )
    return {
        "status": "HEALTHY",
        "service": service_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/payments")
async def process_payment(req: PaymentRequest) -> dict[str, str | float]:
    if simulated_delay > 0:
        time.sleep(simulated_delay)
    if is_degraded:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processor connection failed",
        )
    return {
        "status": "PROCESSED",
        "amount": req.amount,
        "currency": req.currency,
        "customer_id": req.customer_id,
        "transaction_id": f"tx_{int(time.time() * 1000)}",
    }


@app.post("/simulate/degrade")
def set_degraded(degrade: bool = True) -> dict[str, bool]:
    global is_degraded
    is_degraded = degrade
    return {"degraded": is_degraded}

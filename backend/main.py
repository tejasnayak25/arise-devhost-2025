from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": " AI-Powered Carbon Compliance & ESG Reporting Automation"}


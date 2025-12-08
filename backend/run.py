import uvicorn

if __name__ == "__main__":
    # Отключаем reload для стабильности с sqladmin
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)

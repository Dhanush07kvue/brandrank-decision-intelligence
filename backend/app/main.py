from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request
import duckdb
from app.api.routes import router

app = FastAPI(title='Brand Activation Intelligence API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(router, prefix='/api')


@app.exception_handler(duckdb.IOException)
async def handle_duckdb_io_exception(request: Request, exc: duckdb.IOException):
    message = str(exc)
    if 'Could not set lock on file' in message:
        return JSONResponse(
            status_code=503,
            content={
                'error': 'database_locked',
                'message': 'The data store is temporarily locked by another Python process. Stop the other process and retry.',
                'details': message,
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            'error': 'database_io_error',
            'message': 'A database IO error occurred.',
            'details': message,
        },
    )

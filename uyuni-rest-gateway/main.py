#!/usr/bin/env python3
#
# Copyright (c) 2026  SUSE, LLC 
#
# This software is licensed under the GNU General Public License Version 2 (GPL-2.0).
# Please see the LICENSE file for details.
#
"""
Uyuni / SUSE Manager FastAPI REST Gateway
A modern OpenAPI 3.1 compliant wrapper for the legacy XML-RPC API.
"""

import os
import xmlrpc.client
import ssl
from fastapi import FastAPI, HTTPException, Depends
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- CONFIGURATION ---
# Fetches the URL from the environment, defaulting to localhost if not set
UYUNI_URL = os.getenv("UYUNI_URL", "https://localhost/rpc/api")

# Note: In a true production deployment, certificate verification should be enforced.
context = ssl._create_unverified_context()

app = FastAPI(
    title="Uyuni / SUSE Manager REST Gateway",
    version="2.0.0",
)

# --- UTILS ---
def sanitize_xmlrpc_types(data: Any) -> Any:
    """Recursively converts XML-RPC types to standard Python types for Swagger."""
    if isinstance(data, xmlrpc.client.DateTime):
        return data.value
    elif isinstance(data, dict):
        return {k: sanitize_xmlrpc_types(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_xmlrpc_types(item) for item in data]
    return data

# --- DEPENDENCIES ---
def get_xmlrpc_client():
    client = xmlrpc.client.ServerProxy(UYUNI_URL, context=context)
    try:
        yield client
    finally:
        pass

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def require_token(token: str = Depends(oauth2_scheme)):
    return token

# --- PYDANTIC MODELS (Schemas) ---
class UniversalRequest(BaseModel):
    method: str = Field(..., description="The exact API method from the Uyuni docs (e.g., 'api.getVersion')")
    params: List[Any] = Field(default=[], description="List of parameters to pass.")

# --- ENDPOINTS ---
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.post("/auth/login", tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), client: xmlrpc.client.ServerProxy = Depends(get_xmlrpc_client)):
    try:
        token = client.auth.login(form_data.username, form_data.password)
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/auth/logout", tags=["Authentication"])
async def logout(token: str = Depends(require_token), client: xmlrpc.client.ServerProxy = Depends(get_xmlrpc_client)):
    try:
        client.auth.logout(token)
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/systems", tags=["Systems"])
async def list_systems(token: str = Depends(require_token), client: xmlrpc.client.ServerProxy = Depends(get_xmlrpc_client)):
    try:
        return sanitize_xmlrpc_types(client.system.listSystems(token))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/universal-execute", tags=["Universal API Executor"], summary="Run ANY API Method")
async def universal_executor(
    request: UniversalRequest, 
    token: str = Depends(require_token), 
    client: xmlrpc.client.ServerProxy = Depends(get_xmlrpc_client)
):
    try:
        method_parts = request.method.split(".")
        api_func = client
        for part in method_parts:
            api_func = getattr(api_func, part)
            
        result = api_func(token, *request.params)
        return sanitize_xmlrpc_types(result)
    except AttributeError:
        raise HTTPException(status_code=404, detail=f"The method '{request.method}' does not exist.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- OPENAPI 3.1 COMPLIANCE ---
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Uyuni / SUSE Manager API Gateway",
        version="2.0.0",
        description="RESTful Gateway compliant with OpenAPI v3.1 for XML-RPC endpoints.",
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.1.0"
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

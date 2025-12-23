"""
LSP REST API Server

A FastAPI-based REST API server for accessing LSP diagnostic services.
Supports Python (jedi-language-server) and Java (Eclipse JDT.LS).

Usage:
    uvicorn multilspy.server:app --host 127.0.0.1 --port 8000
"""

import os
import uuid
import time
import threading
from typing import Dict, List, Optional
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig, Language
from multilspy.multilspy_logger import MultilspyLogger


# ============================================================================
# Pydantic Models
# ============================================================================

class InitSessionRequest(BaseModel):
    """Request body for initializing an LSP session."""
    language: str = Field(..., description="Language: 'python' or 'java'")
    project_path: str = Field(..., description="Absolute path to project root")


class InitSessionResponse(BaseModel):
    """Response for session initialization."""
    session_id: str
    status: str
    language: str
    project_path: str


class DiagnosticRange(BaseModel):
    """Range of a diagnostic."""
    start: Dict[str, int]
    end: Dict[str, int]


class DiagnosticItem(BaseModel):
    """A single diagnostic item."""
    range: DiagnosticRange
    message: str
    severity: Optional[int] = None
    code: Optional[str] = None
    source: Optional[str] = None


class DiagnosticsResponse(BaseModel):
    """Response for diagnostics request."""
    file_path: str
    diagnostics: List[DiagnosticItem]
    count: int


class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    message: Optional[str] = None


# ============================================================================
# Session Manager
# ============================================================================

class LSPSession:
    """Represents an active LSP session."""
    
    def __init__(self, session_id: str, language: str, project_path: str):
        self.session_id = session_id
        self.language = language
        self.project_path = project_path
        self.lsp: Optional[SyncLanguageServer] = None
        self.server_context = None
        self.created_at = time.time()
        self._lock = threading.Lock()
    
    def start(self) -> None:
        """Start the LSP server."""
        lang_enum = Language.PYTHON if self.language == "python" else Language.JAVA
        config = MultilspyConfig.from_dict({"code_language": lang_enum})
        logger = MultilspyLogger()
        self.lsp = SyncLanguageServer.create(config, logger, self.project_path)
        self.server_context = self.lsp.start_server()
        self.server_context.__enter__()
    
    def stop(self) -> None:
        """Stop the LSP server."""
        if self.server_context:
            try:
                self.server_context.__exit__(None, None, None)
            except Exception:
                pass
        self.lsp = None
        self.server_context = None
    
    def get_diagnostics(self, file_path: str) -> List[dict]:
        """Get diagnostics for a file."""
        if not self.lsp:
            raise RuntimeError("LSP server not started")
        
        with self._lock:
            # Open file to trigger diagnostics
            with self.lsp.open_file(file_path):
                # Wait for language server to analyze
                time.sleep(2.0 if self.language == "python" else 5.0)
                return self.lsp.request_diagnostics(file_path)


class SessionManager:
    """Manages multiple LSP sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, LSPSession] = {}
        self._lock = threading.Lock()
    
    def create_session(self, language: str, project_path: str) -> LSPSession:
        """Create and start a new LSP session."""
        if language not in ("python", "java"):
            raise ValueError(f"Unsupported language: {language}")
        
        if not os.path.isabs(project_path):
            raise ValueError("project_path must be an absolute path")
        
        if not os.path.isdir(project_path):
            raise ValueError(f"project_path does not exist: {project_path}")
        
        session_id = uuid.uuid4().hex[:12]
        session = LSPSession(session_id, language, project_path)
        session.start()
        
        with self._lock:
            self._sessions[session_id] = session
        
        return session
    
    def get_session(self, session_id: str) -> Optional[LSPSession]:
        """Get an existing session by ID."""
        with self._lock:
            return self._sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Stop and remove a session."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        
        if session:
            session.stop()
            return True
        return False
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="LSP REST API Server",
    description="REST API for Language Server Protocol diagnostic services",
    version="1.0.0",
)

# Global session manager
session_manager = SessionManager()


@app.get("/", response_model=StatusResponse)
async def root():
    """Health check endpoint."""
    return StatusResponse(status="ok", message="LSP REST API Server is running")


@app.post("/api/sessions", response_model=InitSessionResponse)
async def create_session(request: InitSessionRequest):
    """
    Initialize a new LSP session.
    
    - **language**: "python" or "java"
    - **project_path**: Absolute path to the project root directory
    """
    try:
        session = session_manager.create_session(
            language=request.language,
            project_path=request.project_path
        )
        return InitSessionResponse(
            session_id=session.session_id,
            status="ready",
            language=session.language,
            project_path=session.project_path
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start LSP server: {e}")


@app.get("/api/sessions/{session_id}/diagnostics", response_model=DiagnosticsResponse)
async def get_diagnostics(
    session_id: str,
    file_path: str = Query(..., description="Relative path to the file within the project")
):
    """
    Get diagnostics for a file in an active session.
    
    - **session_id**: The session ID returned from /api/sessions
    - **file_path**: Relative path to the file (e.g., "src/main.py")
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    try:
        diagnostics = session.get_diagnostics(file_path)
        return DiagnosticsResponse(
            file_path=file_path,
            diagnostics=[DiagnosticItem(**d) for d in diagnostics],
            count=len(diagnostics)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting diagnostics: {e}")


@app.delete("/api/sessions/{session_id}", response_model=StatusResponse)
async def delete_session(session_id: str):
    """
    Shutdown and remove an LSP session.
    
    - **session_id**: The session ID to shutdown
    """
    if session_manager.delete_session(session_id):
        return StatusResponse(status="shutdown", message=f"Session {session_id} has been shutdown")
    else:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


@app.get("/api/sessions", response_model=List[str])
async def list_sessions():
    """List all active session IDs."""
    return session_manager.list_sessions()


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Run the server using uvicorn."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

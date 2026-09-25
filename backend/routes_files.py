import os
import uuid
from datetime import datetime, timezone
from fastapi import Depends, File, HTTPException, Header, Query, Request, Response, UploadFile
from core import (
    APP_NAME,
    CONTENT_ID,
    MAX_UPLOAD_BYTES,
    MIME_TYPES,
    ROLE_LEVEL,
    active_member_from_token,
    api_router,
    db,
    get_object,
    logger,
    put_object,
    require_admin,
    required_level_for_file,
)

@api_router.post("/files/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    ext = (file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max 25 MB).")
    content_type = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    file_id = str(uuid.uuid4())
    path = f"{APP_NAME}/uploads/{file_id}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=400, detail="Storage upload failed. Please try again.")
    doc = {
        "id": file_id, "storage_path": result["path"], "original_filename": file.filename,
        "content_type": content_type, "size": result.get("size", len(data)),
        "is_deleted": False, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(doc)
    backend_base = os.environ.get("FRONTEND_URL", "")
    return {"id": file_id, "filename": file.filename, "size": doc["size"],
            "content_type": content_type, "url": f"{backend_base}/api/files/{file_id}"}


@api_router.get("/files/{file_id}")
async def download_file(file_id: str, request: Request, authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token and auth:
        token = auth
    if not token:
        token = request.cookies.get("access_token")
    member = await active_member_from_token(token)
    if member is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.files.find_one({"id": file_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    # Role-based access control: resolve required level from the document listing that references this file.
    content_doc = await db.settings.find_one({"_id": CONTENT_ID})
    content = (content_doc or {}).get("content", {})
    required = required_level_for_file(content, file_id)
    if ROLE_LEVEL.get(member.get("role"), 1) < required:
        raise HTTPException(status_code=403, detail="You don't have permission to open this document.")
    try:
        data, content_type = get_object(record["storage_path"])
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=400, detail="Storage download failed.")
    filename = record.get("original_filename", "file")
    return Response(content=data, media_type=record.get("content_type", content_type),
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
